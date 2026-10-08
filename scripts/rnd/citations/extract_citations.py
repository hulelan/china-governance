"""Extract and persist cross-document citations.

Scans all documents with body text, extracts formal (文号) and named (《》)
references, resolves them against the corpus, and populates the citations table.

Usage:
    python3 scripts/extract_citations.py              # Extract and save
    python3 scripts/extract_citations.py --dry-run    # Show stats without saving
    python3 scripts/extract_citations.py --force      # Drop and rebuild
"""

import argparse
import csv
import html
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
from analyze import (
    REF_PATTERN, get_admin_level,
    NAMED_REF_PATTERN, is_policy_document, classify_named_ref_level, POLICY_KEYWORDS,
    build_known_abbrevs, canonicalize_formal_ref,
    looks_like_body_run, recover_named_heads,
)

DB_PATH = Path(__file__).parents[3] / "documents.db"

# Normalize site-level "department" to "municipal" for 4-level hierarchy
LEVEL_NORMALIZE = {"department": "municipal"}

_NG = 4  # n-gram size for the title substring index

# Resolver-recall upgrade (2026-08): the old exact-substring matcher missed docs
# we DO hold whenever the cited reference and the stored title differed only in
# punctuation / brackets / whitespace / the 中华人民共和国 prefix (a ~14% false-missing
# rate on top-cited refs). Normalizing BOTH sides before matching recovers those.
_TITLE_STRIP = re.compile(
    r'[\s《》〈〉「」『』【】〔〕\[\]()（）“”‘’"\'、，,。．\.·・:：;；／/　<>]')
_PRC_PREFIX = "中华人民共和国"


def _clean_ref(s):
    """HTML-entity fix (2026-10, a6-recoverable-head): some bodies keep the inner
    title brackets entity-encoded (广东省实施&lt;…土地管理法&gt;办法, 42 citers), so the
    ref never matched the stored 《》 title. Unescape, and turn the resulting <X> into
    《X》 so the inner-title core logic sees it. No-op for refs without an '&'."""
    if not s or '&' not in s:
        return s
    return html.unescape(s).replace('<', '《').replace('>', '》')


def _norm_title(s):
    """Fold punctuation/bracket/whitespace variants + the PRC prefix so that e.g.
    '城市、镇控制性详细规划编制审批办法' and '城市镇...办法', or '《中华人民共和国网络安全法》'
    and '网络安全法', normalize to the same key. HTML entities are unescaped first."""
    s = _TITLE_STRIP.sub('', _clean_ref(s) or '')
    if s.startswith(_PRC_PREFIX):
        s = s[len(_PRC_PREFIX):]
    return s


_DOCNUM_STRIP = re.compile(r'[\s〔〕\[\]()（）【】　]')


def _norm_docnum(s):
    """Normalize a 文号 for matching: unify bracket styles (〔〕[]（）) + strip spaces,
    so a cited ref matches a stored document_number that used a different bracket."""
    return _DOCNUM_STRIP.sub('', s or '')


# --- Resolver-recall upgrade (2026-08, round 2) -----------------------------
# Diagnosis of the ~49% unresolved edges (see docs/ / the sample study) found that
# the vast majority are genuine COVERAGE GAPS (the cited doc isn't in the corpus:
# other-city municipal docs, historical/central docs we never crawled, foreign
# laws, non-document refs like "中央经济工作会议"). But a fixable minority miss docs
# we DO hold because of two representable variations:
#   (1) 文号 that differ only by full-width digits or stray non-〔〕 punctuation, and
#   (2) a named/LLM ref shaped "《CoreTitle》（文号）" or "…发布的《CoreTitle》" whose stored
#       doc is titled "<agency>印发《CoreTitle》的通知" / "<文号> CoreTitle" — reordered,
#       so neither string substring-contains the other, yet the bare 《》 CORE is a
#       clean substring of the stored title.
# These helpers recover exactly those, conservatively (length-gated to avoid
# matching a short generic core to the wrong doc).

_FULLWIDTH_DIGITS = {ord('０') + i: chr(ord('0') + i) for i in range(10)}


def _agg_docnum(s):
    """Aggressive 文号 key: map full-width digits to ASCII and keep only CJK, ASCII
    digits and 号 — folds every remaining punctuation/space/bracket variant."""
    s = (s or "").translate(_FULLWIDTH_DIGITS)
    return re.sub(r'[^一-鿿0-9号]', '', s)


_CORE_DOCNUM = re.compile(
    r'([一-鿿]{1,10})'
    r'[〔〈《（‘〚\[(]'
    r'((?:19|20)\d{2})'
    r'[〕〉》）’〛\])]'
    r'\s*(\d+)\s*号'
)


def _core_docnum(s):
    """Extract the canonical issuer+〔year〕+num号 core from a noisy ref (last match),
    dropping any prepended agency/sentence fragment the canonicalizer missed."""
    ms = list(_CORE_DOCNUM.finditer(s or ""))
    if not ms:
        return None
    m = ms[-1]
    return f"{m.group(1)}{m.group(2)}{m.group(3)}号"


# --- Resolver-recall upgrade (2026-08, round 3) -----------------------------
# Two more representable formal-ref misses, both proven on the live unresolved set:
#   (1) ZERO-PADDING. A heavily-cited ref like 财库〔2022〕4号 (demand 130) is held in
#       the corpus as 财库〔2022〕004号. Every existing docnum key keeps the sequence
#       number verbatim, so 4号 != 004号 and the ref never resolves. _core_zs_key
#       strips the number's leading zeros so the two collide.
#   (2) EMPTY document_number (75% of docs). A formal 文号 citation can't reach a held
#       doc via the docnum indices when that doc stored no document_number — but the
#       文号 usually lives in the TITLE. We index title-embedded 文号 (zero-strip core)
#       so such refs resolve. To keep precision we prefer the "own-number position"
#       (right after a 发文字号/文号 label, or trailing in （…） at the end) over a mere
#       mid-title mention of some OTHER doc's number.
# Both are added as FINAL tiers of resolve_formal that fire ONLY after the whole
# existing chain misses (existing indices untouched), so the currently-resolved
# edge set stays a strict subset — no regression by construction.

def _core_zs_key(s):
    """Zero-padding-insensitive 文号 key: like _core_docnum but strips leading zeros
    from the sequence number, so 财库〔2022〕4号 and 财库〔2022〕004号 (same document,
    padded differently) map to one key. Returns None when no 文号 core is present."""
    ms = list(_CORE_DOCNUM.finditer(s or ""))
    if not ms:
        return None
    m = ms[-1]
    num = m.group(3).lstrip("0") or "0"
    return f"{m.group(1)}{m.group(2)}{num}号"


# 发文字号/文号/字号 label immediately preceding a title-embedded 文号 → it is the
# document's OWN number (not a reference to a different doc).
_OWN_NUM_MARK = re.compile(r'(?:发文字号|文\s*号|字\s*号)[：:\s]{0,3}$')


def _title_docnums(title):
    """Yield (zs_key, is_own_number) for each 文号 core found in a title. is_own_number
    is True when the 文号 sits in an own-number position — right after a 发文字号/文号
    label, or trailing at the very end inside （…） — which distinguishes a doc's own
    number from an in-title mention of some OTHER doc's number (e.g. '…（X号批次）')."""
    for m in _CORE_DOCNUM.finditer(title or ""):
        k = _core_zs_key(m.group(0))
        if not k:
            continue
        pre = title[max(0, m.start() - 8):m.start()]
        tail = title[m.end():]
        is_own = bool(_OWN_NUM_MARK.search(pre)) or all(
            ch in ')）]】〕 ' for ch in tail)
        yield k, is_own


# 《...》 inner title (>=8 chars) and an END-anchored trailing qualifier group.
# The trailing set is deliberately limited to qualifiers that do NOT change a
# document's identity (试行/暂行/征求意见稿/…); we intentionally do NOT strip a bare
# trailing (YYYY)/(YYYY年版) because that would cross-link different editions, nor a
# MID-title parenthetical (text after it) because that changes what the doc is.
_INNER_TITLE = re.compile(r'《([^《》]{8,})》')
_TRAIL_QUAL = re.compile(
    r'[（(【\[〔](?:试行|暂行|修订|修正|草案|送审稿|征求意见稿|征求意见|讨论稿)[)）】\]〕]$')
_CORE_MIN_LEN = 10  # normalized length floor for a title core to be trustworthy


def _title_cores(raw_ref):
    """Alternate title strings to try when the whole ref doesn't resolve: the text
    inside 《》, and the ref with an end-anchored qualifier group removed."""
    out = []
    for m in _INNER_TITLE.finditer(raw_ref):
        out.append(m.group(1))
    s = raw_ref.strip()
    s2 = _TRAIL_QUAL.sub('', s)
    if s2 != s and s2:
        out.append(s2)
    return out


# --- Proxy-target fix (2026-10) ---------------------------------------------
# docs/research/citation-network-structure.md §1.3 measured that 27% of resolved
# edges (68,880) landed on PROXY targets: a doc whose title merely CONTAINS the cited
# instrument's name. Root cause: resolve() gated its exact/substring tier (a) on
# len(normalized ref) >= min_len (8), but national laws normalize SHORT
# (中华人民共和国城乡规划法 -> 城乡规划法, 5 chars), so tier (a) — the only path that
# can hit the law's own title — was skipped and tier (b) (containment, floor on the
# TITLE) returned the first title containing the name: 河南省实施《…城乡规划法》办法
# took 2,139 inbound while the law itself took 0. PRIORITY RULE: a candidate whose
# normalized title EXACTLY equals the normalized reference (or one of its title
# cores) wins over any containment match; containment is only a fallback. Every
# existing recall path is kept — this re-keys edges, it does not drop them.
_EXACT_MIN_LEN = 3  # floor for the exact-title tier (min_len still gates containment)

# Among mirror copies that normalize to the same title, prefer the highest-level
# host (the law on npc/gov over a bureau's re-post); build_diffusion_events pools
# mirrors downstream anyway, so this only picks the representative id.
_LEVEL_PREF = {"central": 0, "provincial": 1, "municipal": 2, "department": 2,
               "district": 3}

# --- Proxy-target fix, round 2 (2026-10; consistency-review H1) ---------------
# The exact tier above only keyed BARE titles, so an instrument whose canonical
# copy is titled with a promulgation wrapper (中共中央办公厅 国务院办公厅印发《提振消费
# 专项行动方案》) had NO exact candidate and the ref fell through to containment,
# which returned an arbitrary (set-ordered) containing title — a Beijing news page
# took 113 edges while both central copies held 0. Two changes:
#   (1) TITLE CORES: a title is also indexed under its instrument core — the 《X》
#       inside a promulgation wrapper (印发/发布/公布《X》的通知), the X of a bare
#       "关于印发X的通知", and the 关于… body after an issuer masthead — so wrapper
#       and bare copies collide on one key. Non-promulgation wrappers (贯彻落实/
#       实施/转发《X》…) are NOT cores: they are documents ABOUT X, not X.
#   (2) PRIORITY among exact-core candidates: promulgation genre (algo_doc_type)
#       over neutral over news/explainer/解答, then higher admin level, then a bare
#       title over a wrapper, then lowest id. A news page never beats a promulgation
#       of the same instrument.
#   (3) CONTAINMENT is gated: with no exact-core candidate, a containing title only
#       resolves if it is a promulgation-genre document (机动车驾驶证申领和使用规定 no
#       longer lands on a provincial 热点问题解答 page; 百千万工程 not on a news item).
#       Otherwise the ref stays UNRESOLVED (a virtual target) — more honest than a
#       wrong target. Candidates with no genre info (callers that pass none, or docs
#       not yet scored) are not gated, so build_diffusion_events' stem matching and
#       day-0 docs keep the old recall.
_GENRE_PROMUL = frozenset({
    "regulation", "law", "decree", "policy_issuance", "notice", "circular",
    "action_plan", "work_plan", "plan", "strategy", "opinion", "decision",
    "subsidy", "standard", "administrative", "measures", "rule",
})
_GENRE_NEWS = frozenset({
    "explainer", "publicity", "commentary", "interview", "review", "report",
})
# title markers of an explainer / Q&A / news item (独立 of algo_doc_type, which is
# 'other' for most of them)
_NEWS_TITLE_RE = re.compile(
    r"解读|解答|问答|答问|答记者问|一图|图解|图读|发布会|新闻|动态|速递|要闻|快讯|播报|"
    r"访谈|专访|评论|述评|解析|热点|划重点|微视频|视频|海报|漫画|聚焦|观察|综述|盘点|"
    r"亮点|看点|干货|有啥关系|怎么看|怎么办|看懂|读懂|权威解|专家|负责人就|记者|"
    r"会议召开|召开.{0,12}会议|常务会议|党组会议|座谈会|会议纪要|调研|考察|强调|指出")


def _genre_rank(genre, title=""):
    """0 = promulgation, 1 = neutral/unknown, 2 = news/explainer. `genre` None/''
    means 'no information' (rank 1, and NOT gated in containment)."""
    if genre in _GENRE_NEWS or _NEWS_TITLE_RE.search(title or ""):
        return 2
    if genre in _GENRE_PROMUL:
        return 0
    return 1


_STATUS_TAG = re.compile(r'^[（(【\[〔](?:已废止|已失效|失效|废止|有效|现行有效|已修订|部分失效)[)）】\]〕]\s*')
_NEWS_LEAD = re.compile(r'^(?:受权发布|授权发布|权威发布|全文)\s*[丨|｜:：]\s*')
# trailing own-文号 group: （珠府办〔2025〕6号） / （公安部令第162号） / （第12号）
_DOCNUM_TAIL = re.compile(
    r'[（(【\[]\s*[^（()）]*?(?:(?:19|20)\d{2}[^（()）]*?\d+|(?:令|第)\s*\d+)\s*号\s*[)）】\]]\s*$')
_INST_SUFFIX = (r'(?:中共中央|国务院|中央军委|办公厅|办公室|人民政府|委员会|管理局|总局|分局|'
                r'部|局|署|厅|院|委|会|省|市|区|县|党委|党组|集团)')
# promulgation wrapper around 《X》: optional issuer masthead + 关于? + verb + 《X》 + tail
_WRAP_QUOTED = re.compile(
    r'^(?P<pre>[一-鿿\s丨·、]*?)(?:关于)?(?P<verb>印发|发布|公布|颁布)?\s*'
    r'《(?P<core>[^《》]{4,})》(?:的通知|的决定|的公告|的函|的通告|的命令|的令)?$')
_WRAP_PLAIN = re.compile(
    r'^(?P<pre>[一-鿿\s丨·、]*?)关于(?:印发|发布|公布|颁布)(?P<core>[^《》]{6,}?)的通知$')
_MASTHEAD_PRE = re.compile(r'^[一-鿿\s丨·、]{2,40}' + _INST_SUFFIX + r'[\s丨·、]*$')
_WRAP_CORE_MIN = 6  # normalized floor for a wrapper-derived core

# --- Organization-name-only titles: exact-only targets (2026-10-07) -------------
# Some crawled "documents" are masthead stubs: the whole title is an AGENCY NAME
# (广东省自然资源厅, 深圳市住房和建设局, 江门市自然资源局), algo_doc_type 'other', usually
# an empty body. Containment tier (a) — "a stored title is a substring of the cited
# name" — let ANY reference that merely embeds the agency name resolve onto that stub
# whenever the real instrument is not held: 《广东省自然资源厅关于推进征收农村集体土地留用地
# 高效开发利用的通知》 → 广东省自然资源厅. Measured 2026-10-07 on the live corpus: 150 such
# stubs held 4,604 resolved edges (广东省自然资源厅 alone 692, citation_rank #20), a
# 15-edge hand-check found every one a mis-resolution of an unheld instrument, and
# ZERO resolved refs equalled a bare organization name.
# Rule: an org-name-only title is NOT a containment candidate (tiers (a) and (b));
# it stays an EXACT-tier candidate, so a ref that genuinely names the bare
# organization still resolves to it. The ref then falls through to the remaining
# tiers / title cores, or stays honestly unresolved (a crawl-queue entry).
# "Org-name-only" = the module's existing masthead shape (a CJK run ending in an
# _INST_SUFFIX, as _MASTHEAD_PRE, plus 中心 for 深圳市疾病预防控制中心-type public
# institutions) with NO instrument genre word (analyze.POLICY_KEYWORDS, 关于) and not
# an action/news title — 成立深圳市减灾委员会 / 授予…先进小区 are decisions, 我市召开
# …通报会 is a news readout; both keep today's behaviour. A genre word that is part
# of the agency's NAME (规划和自然资源局, 自然资源规划局, 计划生育协会, 标准化研究院) is
# masked before the genre check, or 广州市规划和自然资源局 (63 edges) would escape.
_ORG_NAME = re.compile(r'^[一-鿿\s丨·、]{2,40}(?:' + _INST_SUFFIX + r'|中心)[\s丨·、]*$')
_AGENCY_GENRE_WORD = re.compile(r'(?:规划|计划|标准)(?=和|局|院|委|化|生育|学会|协会|研究)')
_ORG_ONLY_NOT = re.compile(
    '关于|' + '|'.join(POLICY_KEYWORDS) +
    r'|^(?:成立|调整|设立|撤销|组建|授予|创建|命名|表彰|撤并|变更)'   # a decision ABOUT a body
    r'|召开|举行|举办|出席|参加|(?:格|新|大|布|开|全)局$')            # an event / headline


def _is_org_only_title(nt):
    """True for a NORMALIZED title that is just an organization name (exact-only)."""
    return (bool(_ORG_NAME.match(nt))
            and not _ORG_ONLY_NOT.search(_AGENCY_GENRE_WORD.sub('', nt))
            and not _NEWS_TITLE_RE.search(nt))


def _title_cores_of_title(title):
    """Instrument cores a STORED title should also be keyed under, as
    (core, wrapper_flag) pairs — wrapper_flag 1 = institutional promulgation
    wrapper, 2 = non-institutional lead (e.g. a news masthead '北京发布《X》').
    Returns [] for a title that is not a promulgation of its 《X》 (贯彻落实《X》…,
    河南省实施《X》办法)."""
    t = _STATUS_TAG.sub('', title or '').strip()
    t = _NEWS_LEAD.sub('', t)
    t = _DOCNUM_TAIL.sub('', t).strip()
    out = []
    if t != (title or '').strip() and len(_norm_title(t)) >= _WRAP_CORE_MIN:
        out.append((t, 1))  # the title minus its status tag / news lead / 文号 tail
    m = _WRAP_QUOTED.match(t)
    if m:
        pre = m.group('pre').strip()
        core = m.group('core')
        # a bare 《X》 title, or a promulgation VERB right before 《X》 (so a lazy
        # `pre` can't swallow 贯彻落实/实施/转发 — those are documents ABOUT X)
        verb_ok = (pre == '' and m.group('verb') is None) or m.group('verb') is not None
        if verb_ok and len(_norm_title(core)) >= _WRAP_CORE_MIN:
            inst = pre == '' or _MASTHEAD_PRE.match(pre) is not None
            out.append((core, 1 if inst else 2))
    m = _WRAP_PLAIN.match(t)
    if m and len(_norm_title(m.group('core'))) >= _WRAP_CORE_MIN:
        out.append((m.group('core'), 1))
    i = t.find('关于')
    if i > 0 and _MASTHEAD_PRE.match(t[:i]) and len(t) - i >= 8:
        out.append((t[i:], 1))
    return out


# --- Instrument aliases (2026-10, a6-recoverable-head zero-crawl fixes) ---------
# A cited instrument can be held under a slightly different official name (广东省
# 控制性详细规划管理条例, 340 distinct citers, is held as 广东省城市控制性详细规划管理条例):
# the exact/core tiers miss a one-word difference and containment can't bridge it
# either (neither normalized string contains the other). Rather than loosen the
# matcher, a small data-driven table maps `cited_as` -> `canonical_title`; the alias
# is applied to the NORMALIZED ref right before the exact tier, so it only ever
# redirects a ref that would otherwise have no exact candidate under its own name.
ALIASES_PATH = Path(__file__).parents[3] / "data" / "instrument_aliases.csv"


def load_aliases(path=ALIASES_PATH):
    """{norm(cited_as): norm(canonical_title)} from the CSV (cited_as,canonical_title,why).
    Missing file -> {} so callers (tests, build_diffusion_events) never break."""
    out = {}
    try:
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                a = _norm_title((row.get("cited_as") or "").strip())
                c = _norm_title((row.get("canonical_title") or "").strip())
                if a and c and a != c:
                    out[a] = c
    except FileNotFoundError:
        pass
    return out


class TitleMatcher:
    """Indexed fuzzy title resolver — replaces an O(docs x titles) per-ref scan.

    resolve(name, min_len) returns a doc id for some stored title t with
    len(t) >= min_len and (t in name OR name in t), else None — the same
    RESOLVED/UNRESOLVED partition as the old brute-force loop (parity-tested),
    but O(len(name)^2) via substring generation + an n-gram inverted index
    instead of scanning every title. Drops the full rebuild from ~2h to minutes.
    Tie-break differs (prefers the longest 't in name' match — strictly better).
    An EXACT normalized-title match (>= _EXACT_MIN_LEN) is tried FIRST, before
    any containment tier, so a cited law resolves to the law, not to a measure
    whose title contains the law's name (see the proxy-target note above).

    MIRROR SELECTION is this class's own responsibility and is deterministic:
    among documents whose titles normalize identically, (genre_rank, level_rank,
    id) picks the representative — promulgation over news, highest-level host,
    then LOWEST id, so a newly ingested mirror can never flip an established
    target. Callers must therefore pass EVERY copy (use the pair form below);
    de-duplicating by title upstream hands the decision to insertion order.
    """

    def __init__(self, title_to_doc, site_levels=None, aliases=None, org_only_exact=False):
        # title_to_doc: either {title: value} or an ITERABLE OF (title, value) PAIRS.
        # The pair form exists so callers holding several documents under the SAME
        # title (mirror promulgations) can hand all of them over instead of letting a
        # dict silently keep whichever one was inserted last — the ranking below, not
        # insertion order, then decides which copy represents the instrument.
        # aliases: {norm cited_as -> norm canonical title}; default = data/instrument_aliases.csv
        # org_only_exact: make organization-name-only titles exact-tier-only (see
        #   _is_org_only_title). OFF by default because build_diffusion_events also
        #   builds TitleMatchers over topic STEMS, and stems such as 国家认定企业技术中心 /
        #   承接产业转移示范区 share the masthead shape without being organizations —
        #   gating them would silently change title_reissue matching. The citation
        #   resolver (extract_all) turns it on.
        self.aliases = load_aliases() if aliases is None else dict(aliases)
        # Index on NORMALIZED titles (punctuation/prefix folded). When two titles
        # normalize identically (mirror copies), keep the promulgation-genre copy,
        # then the highest-level host, then the lowest id (deterministic).
        # A second index keys each title under its instrument CORE(S) as well
        # (see the round-2 note above), ranked (genre, level, bare-before-wrapper, id).
        site_levels = site_levels or {}
        self.exact = {}  # norm-title -> id
        self.core = {}   # norm-core  -> id   (bare titles + promulgation-wrapper cores)
        self.meta = {}   # id -> (genre_rank or None, level_rank, norm-title length)
        best = {}        # norm-title -> (genre_rank, level_rank, id)
        best_core = {}   # norm-core  -> (genre_rank, level_rank, wrapper_flag, id)
        items = title_to_doc.items() if hasattr(title_to_doc, "items") else title_to_doc
        for t, v in items:
            nt = _norm_title(t)
            if not nt:
                continue
            # values may be (id, site_key, algo_doc_type), (id, site_key), (id,)
            # (build_diffusion_events) or a bare id
            if isinstance(v, (tuple, list)):
                did = v[0]
                sk = v[1] if len(v) > 1 else ""
                genre = v[2] if len(v) > 2 else None
            else:
                did, sk, genre = v, "", None
            genre = genre or None  # '' (unscored) == no information
            lvl = _LEVEL_PREF.get(site_levels.get(sk, ""), 9)
            grank = _genre_rank(genre, t) if genre is not None else 1
            self.meta[did] = (grank if genre is not None else None, lvl, len(nt))
            key = (grank, lvl, did)
            cur = best.get(nt)
            if cur is None or key < cur:
                best[nt] = key
            cands = [(nt, 0)] + [(_norm_title(c), f) for c, f in _title_cores_of_title(t)]
            for nc, flag in cands:
                if not nc:
                    continue
                ck = (grank, lvl, flag, did)
                cur = best_core.get(nc)
                if cur is None or ck < cur:
                    best_core[nc] = ck
        for nt, (_, _, did) in best.items():
            self.exact[nt] = did
        for nc, (_, _, _, did) in best_core.items():
            self.core[nc] = did
        self.titles = list(self.exact.keys())
        # org-name-only titles: exact-tier only, never containment (see _is_org_only_title)
        self.org_only = (frozenset(t for t in self.titles if _is_org_only_title(t))
                         if org_only_exact else frozenset())
        self.index = {}  # gram -> set of title indices
        for idx, t in enumerate(self.titles):
            for g in self._grams(t):
                self.index.setdefault(g, set()).add(idx)

    def _containment_ok(self, did):
        """Containment gate: a doc with KNOWN genre must be promulgation-genre
        (never a news/explainer/解答 page, nor a permit notice); no-info docs pass."""
        m = self.meta.get(did)
        return m is None or m[0] is None or m[0] == 0

    def _rank(self, did):
        m = self.meta.get(did) or (1, 9, 0)
        return (1 if m[0] is None else m[0], m[1], m[2], did)

    @staticmethod
    def _grams(s):
        if len(s) < _NG:
            return {s}
        return {s[i:i + _NG] for i in range(len(s) - _NG + 1)}

    def _containing(self, name):
        """Titles that contain `name` (n-gram intersection, then verify)."""
        posting = None
        for g in self._grams(name):
            s = self.index.get(g)
            if not s:
                return ()
            posting = set(s) if posting is None else (posting & s)
            if not posting:
                return ()
        return (self.titles[i] for i in posting if name in self.titles[i])

    def resolve_exact(self, name):
        """PRIORITY tier: the doc whose normalized title equals the normalized ref
        (the cited instrument itself), regardless of the containment min_len."""
        name = _norm_title(name)
        name = self.aliases.get(name, name)  # data-driven alias BEFORE exact matching
        if len(name) >= _EXACT_MIN_LEN:
            return self.core.get(name)
        return None

    def resolve(self, name, min_len):
        did = self.resolve_exact(name)  # exact title/core beats every containment tier
        if did is not None:
            return did
        name = _norm_title(name)  # match on the normalized form (both sides folded)
        L = len(name)
        # (a) a stored title is a substring of the cited name (longest-first; L==exact)
        if L >= min_len:
            for length in range(L, min_len - 1, -1):
                for i in range(L - length + 1):
                    sub = name[i:i + length]
                    if sub in self.org_only:  # an agency name inside the ref is not the ref
                        continue
                    did = self.exact.get(sub)
                    if did is not None:
                        return did
        # (b) the cited name is a substring of a longer stored title (floor is on title).
        # Gated to promulgation-genre candidates; best = (genre, level, shortest, id)
        # rather than set-iteration order. No candidate -> unresolved (virtual target).
        best = None
        for t in self._containing(name):
            if len(t) < min_len or t in self.org_only:
                continue
            did = self.exact[t]
            if not self._containment_ok(did):
                continue
            r = self._rank(did)
            if best is None or r < best[0]:
                best = (r, did)
        return best[1] if best else None

    def resolve_ref(self, raw_ref, min_len=8):
        """resolve() on the whole ref, then (only on a miss) on its title cores —
        the bare 《》 inner title / an end-anchored-qualifier-stripped form — so a
        "《Core》（文号）" ref still links to a stored "<agency>印发《Core》的通知"
        (reordered; the core is a clean substring of the stored title).
        PRIORITY: an exact normalized-title hit on the whole ref OR any title core
        wins before any containment tier is consulted."""
        base = _norm_title(raw_ref)
        cores = _title_cores(raw_ref)
        for cand in [raw_ref] + cores:
            did = self.resolve_exact(cand)
            if did is not None:
                return did
        did = self.resolve(raw_ref, min_len)
        if did is not None:
            return did
        for core in cores:
            nc = _norm_title(core)
            if len(nc) >= _CORE_MIN_LEN and nc != base:
                did = self.resolve(core, max(min_len, _CORE_MIN_LEN))
                if did is not None:
                    return did
        return None


def _nested_nonself(name, title):
    """Nested 《X》 titles inside a capture, minus any X that is the citing document's
    OWN instrument core (so 印发《X》的通知 does not cite X, but 关于废止〈省实施《X》办法〉
    的决定 does cite X)."""
    own = {_norm_title(c) for c, _ in _title_cores_of_title(title)}
    own.add(_norm_title(title))
    return [x for x in _INNER_TITLE.findall(name)
            if is_policy_document(x) and _norm_title(x) not in own]


def named_ref_candidates(body, title):
    """The 《》 reference strings to resolve for one document, in emission order.

    Three sources, see docs/working/qa-ref-pattern-precision.md:
      1. NAMED_REF_PATTERN — balanced one level deep, so a capture is either a title
         or a title quoting a title, never a run of prose spanning a stray 《.
      2. recover_named_heads — the head of a run whose closing 》 the body genuinely
         dropped (the only reference the balanced pattern cannot see).
      3. the nested 《X》 of any capture that quotes another instrument: such a capture
         cites BOTH documents, and the old truncating pattern reached X only by
         accident (it cut the capture at X's closing bracket and lost the wrapper).
    Drops prose captures and self-references. Nested titles carry the PRECISE
    self-reference test (own title / own instrument core) and are therefore exempt
    from the loose substring test, which they routinely trip: 关于废止《省实施〈X〉办法》
    的决定 contains X in its own title and still cites X.
    """
    refs = [_clean_ref(n) for n in NAMED_REF_PATTERN.findall(body or "")]
    refs += list(recover_named_heads(body or ""))
    nested = {x for n in refs if '《' in n for x in _nested_nonself(n, title or "")}
    out, seen = [], set()
    for name in refs + sorted(nested):
        if not is_policy_document(name):
            continue
        if looks_like_body_run(name):  # prose, not an instrument title
            continue
        if name not in nested and (name in title or title in name):
            continue  # self-reference
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def get_source_level(doc_number: str, site_admin_level: str) -> str:
    """Determine admin level for a source document."""
    if doc_number:
        level = get_admin_level(doc_number)
        if level != "unknown":
            return level
    # Fall back to site's admin level
    return LEVEL_NORMALIZE.get(site_admin_level, site_admin_level) or "unknown"


def extract_all(conn: sqlite3.Connection, dry_run: bool = False):
    """Extract citations from all documents with body text."""
    t0 = time.time()

    # --- Build lookup tables ---

    # document_number -> doc_id (for formal ref resolution)
    docnum_to_id = {}
    docnum_agg = {}   # aggressive key (full-width digits + all punctuation folded)
    docnum_core = {}  # canonical issuer+year+num号 core key
    docnum_core_zs = {}  # zero-padding-insensitive core key (round-3)
    for row in conn.execute(
        "SELECT id, document_number FROM documents WHERE document_number <> ''"
    ).fetchall():
        did, dn = row[0], row[1 + 0]
        docnum_to_id[dn] = did  # raw docnum -> id
        nd = _norm_docnum(dn)   # + bracket-normalized key (don't clobber a raw match)
        if nd and nd != dn:
            docnum_to_id.setdefault(nd, did)
        ad = _agg_docnum(dn)
        if ad:
            docnum_agg.setdefault(ad, did)
        cd = _core_docnum(dn)
        if cd:
            docnum_core.setdefault(_agg_docnum(cd), did)
        zk = _core_zs_key(dn)
        if zk:
            docnum_core_zs.setdefault(zk, did)

    # title-embedded 文号 index (round-3): key -> id, own-number positions winning
    # over mere in-title mentions. Populated after title_to_doc is built, below.
    title_docnum_zs = {}

    def resolve_formal(ref):
        """docnum resolution: raw -> bracket-norm -> aggressive -> canonical core, then
        (round-3 FINAL tiers, only on a miss) zero-strip core over document_number, then
        the zero-strip core embedded in a stored TITLE. The round-3 tiers fire strictly
        after the existing chain, so already-resolved refs are unchanged."""
        did = (docnum_to_id.get(ref)
               or docnum_to_id.get(_norm_docnum(ref))
               or docnum_agg.get(_agg_docnum(ref))
               or docnum_core.get(_agg_docnum(_core_docnum(ref) or "")))
        if did:
            return did
        zk = _core_zs_key(ref)
        if zk:
            return docnum_core_zs.get(zk) or title_docnum_zs.get(zk)
        return None

    # (title, (id, site_key, algo_doc_type)) PAIRS for named ref resolution. Floor
    # was 10, then 8 (excluded 9-char provincial 条例); now 5 (2026-10): 广东省公路条例
    # (7 chars) was held x4 yet never indexed, so 41 citers stayed unresolved. Short
    # titles are reachable ONLY through the exact tier (containment tiers keep their
    # min_len=8 floor on both sides), so lowering the floor cannot create new
    # fuzzy/proxy matches.
    #
    # A LIST, not a dict (2026-10-07, docs/working/qa-cxgh-citer-drop.md §4.2): this
    # used to be `title_to_doc[row[1]] = ...` over an UNORDERED SELECT, so when several
    # documents shared a byte-identical title the LAST row scanned silently clobbered
    # its predecessors and only that one reached TitleMatcher. The winner was therefore
    # decided by scan order, not by the documented (genre_rank, level_rank, id)
    # tie-break — 中华人民共和国城乡规划法 is held 3× and all 2,158 edges landed on the
    # HIGHEST id purely because rowid order put it last, so ingesting a higher-id mirror
    # would silently move them again. Passing every row through lets TitleMatcher's
    # existing ranking be the single arbiter (it is order-independent: a strict `<` over
    # (grank, lvl, id)), and lowest-id-wins means a newly ingested mirror can never flip
    # an established target. The 5-char floor widened exactly this query, so the
    # exposure had grown.
    #
    # Why not read `doc_identity.instrument_id` (the corpus's other "which copy is the
    # instrument" authority) instead: it is rebuilt in daily_sync Phase 2b AFTER this
    # script, so the resolver would consume a day-stale table and brand-new documents
    # would have no row at all on the night they are ingested; TitleMatcher is also
    # constructed from ad-hoc title indexes by build_diffusion_events, where no
    # doc_identity rows exist. And for this very case doc_identity is not authoritative:
    # it leaves all three 城乡规划法 copies `instrument_role='unique'` (its title-core
    # pooling misses them). The ranking here stays the resolver's own source of truth.
    title_rows = []
    _title_dn_strong = {}  # own-number-position 文号 in a title
    _title_dn_weak = {}    # mid-title mention of a 文号 (fallback only)
    # (algo_doc_type feeds the resolver's genre priority + containment gate; a doc
    #  not yet scored has NULL/'' and is treated as "no information" — ungated)
    for row in conn.execute(
        # ORDER BY id so the 文号 indexes below (setdefault = first-wins) are
        # reproducible too, independent of storage/rowid order.
        "SELECT id, title, site_key, algo_doc_type FROM documents "
        "WHERE LENGTH(title) >= 5 ORDER BY id"
    ).fetchall():
        title_rows.append((row[1], (row[0], row[2], row[3])))
        for zk, is_own in _title_docnums(row[1]):
            (_title_dn_strong if is_own else _title_dn_weak).setdefault(zk, row[0])
    # own-number positions win over mere in-title mentions of another doc's number
    title_docnum_zs.update(_title_dn_weak)
    title_docnum_zs.update(_title_dn_strong)

    # site_key -> admin_level
    site_levels = {}
    for row in conn.execute("SELECT site_key, admin_level FROM sites").fetchall():
        site_levels[row[0]] = row[1] or "unknown"

    # indexed fuzzy title resolver (fast); agency-name-only titles are exact-only targets
    matcher = TitleMatcher(title_rows, site_levels, org_only_exact=True)
    print(f"Lookup tables: {len(docnum_to_id)} doc numbers, {len(title_rows)} title rows "
          f"({len(matcher.exact)} distinct normalized titles), {len(site_levels)} sites")

    # --- Fetch all documents with body text OR references_json ---
    docs = conn.execute(
        """SELECT id, site_key, title, document_number, body_text_cn, references_json
           FROM documents
           WHERE (body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 20)
              OR (references_json IS NOT NULL AND references_json != '' AND references_json != '[]')"""
    ).fetchall()
    print(f"Documents with body text or references: {len(docs)}")

    # --- Pre-scan: build the issuer-abbreviation vocabulary for 文号 normalization ---
    # (held doc numbers are authoritative; short standalone ref prefixes fill gaps)
    raw_formal = []
    for _d in docs:
        raw_formal.extend(REF_PATTERN.findall(_d[4] or ""))
    known_abbrevs = build_known_abbrevs(docnum_to_id.keys(), raw_formal)
    print(f"Known issuer abbreviations: {len(known_abbrevs)} (from {len(docnum_to_id)} held numbers + short refs)")

    # --- Extract citations ---
    citations = []  # list of (source_id, target_ref, target_id, citation_type, source_level, target_level)
    stats = Counter()
    missing_formal_refs = set()  # distinct unresolved 文号 (for dedup-impact metric)

    for doc_id, site_key, title, doc_number, body, refs_json in docs:
        source_level = get_source_level(doc_number, site_levels.get(site_key, ""))
        body = body or ""

        # Formal 文号 citations (normalized: strip lead-ins + prepended agency names)
        formal_refs = REF_PATTERN.findall(body)
        seen_formal = set()
        for ref in formal_refs:
            ref = canonicalize_formal_ref(ref, known_abbrevs)
            if ref == doc_number:  # skip self-reference
                continue
            if ref in seen_formal:
                continue
            seen_formal.add(ref)

            target_id = resolve_formal(ref)
            target_level = get_admin_level(ref)
            citations.append((doc_id, ref, target_id, "formal", source_level, target_level))
            stats["formal"] += 1
            if target_id:
                stats["formal_resolved"] += 1
            else:
                missing_formal_refs.add(ref)

        # Named 《》 citations (candidate construction + self-reference / prose
        # filtering live in named_ref_candidates)
        seen_named = set()  # also consulted by the LLM-reference tier below
        for name in named_ref_candidates(body, title):
            seen_named.add(name)
            # Try to resolve to corpus (indexed fuzzy title match + title cores)
            target_id = matcher.resolve_ref(name, 8)

            target_level = classify_named_ref_level(name)
            citations.append((doc_id, name, target_id, "named", source_level, target_level))
            stats["named"] += 1
            if target_id:
                stats["named_resolved"] += 1

        # LLM-extracted references (from references_json column)
        if refs_json and refs_json not in ('', '[]'):
            try:
                import json as _json
                llm_refs = _json.loads(refs_json)
            except (ValueError, TypeError):
                llm_refs = []
            for ref_name in llm_refs:
                if not isinstance(ref_name, str) or len(ref_name) < 4:
                    continue
                ref_name = _clean_ref(ref_name)
                # Self-reference check: skip only if ref is essentially the same as the title.
                # Don't skip when the ref is PART of the title (common for explainers:
                # "一图读懂《X》" references X, which is a substring of the title but NOT self)
                if ref_name == title or title == ref_name:
                    continue
                # Skip if already found by regex
                if ref_name in seen_formal or ref_name in seen_named:
                    continue

                # Try to resolve to corpus by title match (indexed + cores), then doc number
                target_id = matcher.resolve_ref(ref_name, 8)
                if not target_id:
                    target_id = resolve_formal(ref_name)

                target_level = classify_named_ref_level(ref_name)
                citations.append((doc_id, ref_name, target_id, "llm", source_level, target_level))
                stats["llm"] += 1
                if target_id:
                    stats["llm_resolved"] += 1

    elapsed = time.time() - t0

    # --- Report ---
    print(f"\nExtracted {len(citations)} citations in {elapsed:.1f}s:")
    print(f"  Formal (文号): {stats['formal']} ({stats['formal_resolved']} resolved, "
          f"{len(missing_formal_refs)} distinct missing after normalization)")
    print(f"  Named  (《》): {stats['named']} ({stats['named_resolved']} resolved)")
    print(f"  LLM  (refs):   {stats['llm']} ({stats['llm_resolved']} resolved)")
    total_resolved = stats['formal_resolved'] + stats['named_resolved'] + stats['llm_resolved']
    print(f"  Total resolved: {total_resolved}/{len(citations)}")

    # Level breakdown
    level_counts = Counter()
    cross_level = 0
    for _, _, _, _, src_lvl, tgt_lvl in citations:
        level_counts[f"{src_lvl} → {tgt_lvl}"] += 1
        if src_lvl != tgt_lvl and src_lvl != "unknown" and tgt_lvl != "unknown":
            cross_level += 1

    print(f"\n  Cross-level citations: {cross_level}")
    print(f"\n  Citation flow:")
    for flow, count in sorted(level_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"    {flow}: {count}")

    if dry_run:
        print("\n[DRY RUN — nothing saved]")
        return

    # --- Save (with retry for busy DB) ---
    for save_attempt in range(5):
        try:
            conn.execute("DELETE FROM citations")
            break
        except sqlite3.OperationalError:
            wait = (save_attempt + 1) * 10
            print(f"  DB locked, retrying in {wait}s (attempt {save_attempt + 1}/5)...")
            time.sleep(wait)
    else:
        print("ERROR: Could not acquire write lock after 5 attempts")
        return
    conn.executemany(
        """INSERT OR REPLACE INTO citations
           (source_id, target_ref, target_id, citation_type, source_level, target_level)
           VALUES (?, ?, ?, ?, ?, ?)""",
        citations,
    )
    conn.commit()
    final_count = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    print(f"\nSaved {final_count} citations to database")


def main():
    parser = argparse.ArgumentParser(description="Extract and persist cross-document citations")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without saving")
    parser.add_argument("--force", action="store_true", help="Drop and recreate citations table first")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = None  # use tuples for speed

    if args.force:
        conn.execute("DROP TABLE IF EXISTS citations")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_ref TEXT NOT NULL,
                target_id INTEGER,
                citation_type TEXT NOT NULL,
                source_level TEXT NOT NULL,
                target_level TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES documents(id),
                FOREIGN KEY (target_id) REFERENCES documents(id),
                UNIQUE(source_id, target_ref, citation_type)
            );
            CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
            CREATE INDEX IF NOT EXISTS idx_citations_target_id ON citations(target_id);
            CREATE INDEX IF NOT EXISTS idx_citations_target_ref ON citations(target_ref);
            CREATE INDEX IF NOT EXISTS idx_citations_levels ON citations(source_level, target_level);
        """)
        print("Rebuilt citations table")

    extract_all(conn, dry_run=args.dry_run)
    conn.close()


if __name__ == "__main__":
    main()
