#!/usr/bin/env python3
"""
build_doc_identity.py — the per-DOCUMENT identity layer: ONE nightly-rebuildable
side table `doc_identity` holding the five fields the replications showed were
inferred or per-site (docs/research/corpus-lessons.md Part A):

    A1 admin_level_doc   level of the document's ISSUER, not of the hosting site
    A2 instrument_id     canonical copy id shared by all mirrors of one text
    A3 genre             promulgation | implementing | explainer | readout | news | other
    A4 date_quality      good | crawl_stamped | missing   (body_scanned reserved, see below)
    A5 lead_issuer       canonical lead agency from `doc_issuers`

WHY A SIDE TABLE (design decision, not open)
--------------------------------------------
Updating a column on all ~320k `documents` rows nightly rewrites every row's
body overflow pages (the 2026-08-10 compute_scores lesson: ~5GB WAL, 78 min).
`doc_identity` is a narrow table keyed by doc_id, rebuilt in ONE transaction
(CREATE IF NOT EXISTS + DELETE + INSERT); every consumer does one join.

SCHEMA
------
    doc_identity(
        doc_id INTEGER PRIMARY KEY,
        admin_level_doc TEXT,   -- central|provincial|municipal|district|department|media|research
        level_source TEXT,      -- issuer|docnum|npc_publisher|title_cue|site
        instrument_id INTEGER,  -- canonical representative's doc id (own id when unique)
        instrument_role TEXT,   -- canonical|mirror|unique
        genre TEXT,             -- promulgation|implementing|explainer|readout|news|other
        date_quality TEXT,      -- good|crawl_stamped|body_scanned|missing
        lead_issuer TEXT,       -- from doc_issuers.lead_issuer (NULL if none)
        localized_of INTEGER,   -- id of the IN-CHAIN higher text whose stem this doc
                                -- localizes (the genre flip's trigger); NULL otherwise
        province TEXT,          -- A6: 2-letter province code of the ISSUING locality
                                -- (geo.PROVINCE_CODE); NULL for central/media/research
                                -- docs and when no header field names a locality
        instrument_kind TEXT    -- A7: framework | housekeeping | other — WHAT KIND of
                                -- text this is (the matcher's anchor gate); see A7
    ) + indexes on admin_level_doc, instrument_id, genre.
    The table is DROPPED and recreated on every build (schema changes need no migration).

DERIVATION RULES (rule-based, no LLM; header fields only — no body reads)
--------------------------------------------------------------------------
A1  admin_level_doc — first rule that fires wins, recorded in `level_source`:
    (0) media / research SITES: the site type IS the identity (a newspaper is not
        an issuer); level = site type, level_source = 'site'.
    (1) `issuer`: `doc_issuers.lead_issuer` through `level_of_name()`:
          central registry name (issuer_parser.REGISTRY) or a 国家/国务院/中央/全国/
          最高 head with no locality token            -> central
          地区/自治州 (prefecture-tier units)          -> municipal
          X区 / X县 / 新区 / 开发区 (not 自治区)        -> district
          X省 / X自治区 / 北京|上海|天津|重庆市 head     -> provincial
          X市 head                                     -> municipal
          bare 省… / 市… / 区… self-reference           -> provincial / municipal / district
        A bureau folds into its government's level (省厅 -> provincial, 市局 ->
        municipal): the memo's complaint is precisely that bureau SITES blur levels.
    (2) `docnum`: the 文号 prefix. issuer_parser.DOCNUM_SUBNATIONAL (粤府 / 深府 /
        苏政办 …) -> level_of_name(agency); then web.services.documents.
        ADMIN_LEVEL_PREFIXES (国发/国办 -> central, 深X区 -> district …); then
        issuer_parser.DOCNUM_CENTRAL — but ONLY on central sites (公〔…〕 at a
        Shenzhen site is the local 公安局, not 公安部), mirroring the parser.
    (3) `npc_publisher`: the national-laws site (`npc`) hosts ~28k local 人大
        instruments under a blanket 'central' site level. A doc whose
        classify_main_name is in NPC_NATIONAL_CATEGORIES (below) is central; otherwise its `publisher` (X省人大常委会 -> provincial, X市人大
        -> municipal) through level_of_name().
    (4) `title_cue`: the title HEAD (before 关于/印发/the first 《) through
        level_of_name(): 中华人民共和国…/国务院…/中共中央… -> central, 广东省人民
        政府关于… -> provincial, 深圳市龙华区… -> district. Head only, so a
        forwarding notice (转发广东省…) keeps the forwarder's level.
    (5) `site`: fallback to sites.admin_level — except the 13 `department` sites,
        which are all Shenzhen MUNICIPAL bureaus (crawlers/gkmlpt.py) and fall
        back to municipal; `department` therefore appears only if a new
        department site of unknown government is added.

A2  instrument_id — mirrors of one text share one id.
    key   = normalized instrument CORE of the title, reusing the citation matcher's
            exact-core tier (extract_citations._title_cores_of_title + _norm_title):
            the 《X》 inside an institutional promulgation wrapper (印发/发布/公布《X》
            的通知), the X of a bare 关于印发X的通知, the 关于… body after an issuer
            masthead, else the whole title minus status tags / news leads / 文号
            tails. Non-institutional wrappers ('北京发布《X》', flag 2) are news ABOUT
            X and do not key to X. Cores shorter than 6 chars never pool — the floor is
            measured BEFORE the 中华人民共和国 fold (2026-10-07), so a national law whose
            name folds short (城乡规划法, 5) still keys and still pools (`_key_len`).
    RECURRING INSTRUMENTS (2026-10-07): a title a government RE-ISSUES — 政府工作报告,
            国务院关于落实《政府工作报告》重点工作分工的意见 (a new 国发 number every spring),
            国务院关于修改和废止部分行政法规的决定 (a new 国令), 惠州市…防空警报试鸣的通告,
            深圳市森林火险黄色预警信号 — names a DIFFERENT text each time, yet a year's gap
            is under EDITION_GAP_DAYS so the whole run chained into one instrument (505
            pools flagged by a72a341's canonical audit). Span cannot discriminate: the
            WIDEST pools are healthy late-mirror sets (户口登记条例, npc 1958 + a 公安局
            repost 2008). Two intrinsic tests do, applied in this order:
            R1 `split_by_docnum` — INSIDE each edition, partition by the copy's OWN 文号
              (`document_number`, else the title's trailing 文号 group, which is where a
              第N号 recurrence hides because the keying strips that tail). Un-numbered
              copies attach to the nearest numbered text within EDITION_GAP_DAYS. Two
              numbers whose dates are within DOCNUM_SPLIT_MIN_DAYS (30) are NOT split —
              that close, the difference is a mis-stored number on a mirror (chinatax
              keeps the referenced instrument's 文号) — unless they name different
              LOCALITIES (惠府办 vs 江府办), which no mirror pair ever does.
            R2 `is_series` — per sub-pool, when EVERY member is the untyped `other`
              residual and one site holds two copies more than SERIES_REPEAT_DAYS (60)
              apart, the title names a SERIES, not a text: nothing in it pools. The genre
              gate is the discriminator — a `promulgation` or `implementing` member means
              the title does name a text (城市民族工作条例 re-posted by 福建省民宗厅 in 2015
              AND 2021 is one 条例).
            Live: 386 groups split by 文号 into 944 sub-pools, 48 series dissolved;
            instruments 327,634 -> 328,678; no title blocklist needed.
    who   = promulgation + the untyped `other` residual pool together; implementing
            instruments (转发 / 实施方案 at a lower level — distinct acts) pool only
            with their own copies; explainer / readout / news are ABOUT an
            instrument, never a copy of it, and stay `unique`.
    where = only ACROSS sites: a key whose docs all sit on one site stays `unique`
            (a single site's near-duplicates are usually distinct items).
    when  = docs sharing a key are sorted by date and chained into editions: a gap
            of more than 400 days to the previous member starts a NEW edition —
            unless the doc's hosting SITE level is strictly LOWER than the current
            edition's level, in which case it is a late repost of that edition (a
            bureau cannot promulgate a new edition of a State Council text; 政府信
            息公开条例 re-posted by a 民政局 in 2017 belongs to the 2007 text, the
            2019 npc copy opens the 2019 revision). Undated docs join the key's
            only edition, else stay `unique`.
    LOCALIZED RE-ISSUANCE (2026-10-06): a doc is a MIRROR of an instrument only if
            its core is the instrument's core with NO locality / issuing-body prefix.
            深圳市人民政府关于印发推动大规模设备更新和消费品以旧换新行动方案的通知 shares
            the core of the State Council's 《推动…行动方案》 but is Shenzhen's OWN plan —
            the consumption-diffusion memo's key adoption signal, which must be a
            diffusion SOURCE, not a pooled mirror. Rule: a doc whose title names a
            sub-national locality (a 省/市/区/县 masthead before 关于/印发, or a
            <locality>X core) is a *localized re-issuance* whenever its stem (core minus
            the locality) also appears on a HIGHER-level member (central text, or a
            province above a city). It is then its own instrument — `unique`, or the
            canonical of its own local pool keyed (stem, locality) — with genre
            `implementing`, and never pools with the higher-level text. A bare《X》
            repost (no locality anywhere in the title) stays a mirror: 受权发布丨…印发《X》
            on Xinhua, or 国务院…《X》 re-posted by a ministry. Locality names come from
            issuer_parser.DOCNUM_SUBNATIONAL (the 文号 registry's agency names) plus the
            doc's own masthead; province-shaped names (X省 / X自治区) are always accepted.
    IN-CHAIN GENRE FLIP (2026-10-06, docs/working/qa-genre-flip.md): the `localized`
            flag above (which only keeps a doc OUT of the higher text's pool) fires on
            ANY higher-ranked same-stem member. The genre flip promulgation ->
            `implementing` is stricter: it fires only when a same-stem text exists in
            the doc's OWN jurisdictional chain — central, or its own province
            (data/city_province.csv), or for a district its own city / province — and
            the stem is not a self-government housekeeping genre every government
            writes for itself (GENERIC_STEM_RE: 议事规则, 制定地方性法规条例, 三定规定,
            政府工作规则 …). The QA hand-check put the broad rule at 80% precision with
            all 12 wrong flips out-of-chain or housekeeping (苏州市养犬管理条例 <- 天津市;
            深圳市人大常委会议事规则 <- 福建省); the in-chain rule scores 44/45. The
            trigger's id is persisted as `localized_of`. A locality the map does not
            know (false detections such as 转发市) never flips; the count is reported.
    DATE-ORDERED TRIGGER (2026-10-07, docs/research/pair-channels.md §1): a localized
            re-issuance cannot precede the text it localizes, yet 488 of 2,592 persisted
            edges pointed at a trigger dated AFTER the document (云南省行政执法监督条例
            1998 <- the State Council's 行政执法监督条例 2025; 重庆 2006–2016 notices <- a
            later central re-issuance of a same-stem text). Measured on those edges, the
            reversed lags do not cluster near zero — 86% are more than 180 days apart and
            none joins the trigger's instrument pool — so they are false triggers, not
            mirror re-posts. Rule: a candidate trigger must be dated no later than the doc
            plus LOCALIZED_SLACK_DAYS (7: publication-order noise — a ministry text adopted
            before, posted after, the province's copy; the 0..7-day forward bin is as thin
            as the -7..-1 bin), plus MONTH_SLACK_DAYS (31) when either date is a `-01`
            month-precision stamp. Among the date-valid in-chain candidates the LATEST one
            wins (the nearest parent: a city text localizes its province's re-issuance,
            not the central original it also matches), ties -> closest level, lowest id.
            An undated doc or trigger is never date-valid. With no valid trigger the doc
            stays `promulgation`, `localized_of` NULL (the pre-date-rule pick is kept in
            `_chain_trigger` for --dry-run-flips only).
    canonical = promulgation genre > highest admin_level_doc > hosted at-or-above the
                text's own level > earliest date (first publication, among equally
                authoritative copies) > lowest id. (2026-10-07) The host tier exists
                because `admin_level_doc` is the level of the TEXT, so every mirror of a
                national law ties on it and the date alone decided — a 福建省信访局 copy of
                民法典 stamped 2020-01-08 beat the npc adoption of 2020-05-28. See
                _canon_sort_key / _hosted_below_text (and why plausibility is not a tier).
    `unique` docs carry their own id as instrument_id, so GROUP BY instrument_id
    works unconditionally. build_diffusion_events pools anchors by this id and uses
    the canonical member as the anchor representative.

A3  genre — title shape first, stored algo_doc_type second:
    explainer    解读 / 答记者问 / 一图读懂 / 图解 / 政策问答 / 解答 / 划重点 …
    readout      会议 / 召开 / 讲话 / 调研 / 座谈 / 会见 / 出席 / 主持 / 考察 / 致辞 /
                 强调 / 指出 … when the title is NOT an issuance frame
                 (build_diffusion_events.NONISSUE_RE is the ancestor of this rule)
    implementing SUB-NATIONAL level and 实施方案 / 实施意见 / 实施细则 / 实施办法 /
                 实施《X法》办法 / 变通规定 / 贯彻落实 / 转发…的通知 / 若干措施 in an
                 issuance frame (or algo_doc_type in IMPLEMENTING_GENRES, below)
    promulgation an issuance frame (印发/发布/公布《X》 with an institutional masthead,
                 关于…的通知/意见/办法/规定/…, X令, central 关于…的公告), a bare
                 法/条例/办法/规定 title, or algo_doc_type in {regulation, law, decree,
                 opinion, action_plan, policy_issuance, strategy, plan, work_plan,
                 decision, notice, subsidy, standard}. A 征求意见 draft is `other`.
    news         media sites, or 新闻 / 报道 / 快讯 / 发布会 / 记者 / 回应 / 反响 … cues,
                 or a non-institutional 《X》 lead (北京发布《X》)
    other        everything else (procurement, budgets, personnel, consultations,
                 local 公告, research-site reports/translations, and gov-site local
                 news that carries no cue — the known residual, ~half of `other`
                 on the hand-check samples)
    Hand-check precision (3 stratified 60-doc samples, 2026-10-06): A1 level 59/60
    and 59/60; A3 genre 50/60 → 53/60 → 53/60 before each round's fixes (the
    remaining misses are the uncued-news residual in `other`).
    A media reprint of an instrument (受权发布丨…印发《X》) is genre promulgation at
    level media — the diffusion `source_implementing` flag is the AND of the two.

A4  date_quality — per SITE, the industrial-policy memo's rule (docs/research/
    industrial-policy-targeting.md "Date-stamp exclusion"): a government site whose
    dated 2008+ documents are >=70% in the crawl year (2026) carries crawl dates,
    not publication dates; every doc on it is `crawl_stamped`. A >=100-doc floor
    reproduces the memo's 74-site universe (small sites cannot show a spread).
    (2026-10-06, SUPERSEDED) the year rule flagged shallow, recent-only first crawls whose
    dates are real (js_mzt / njd_jiangning / jcgov …: the pages' own <meta PubDate> and URL
    t-dates match the stored dates). The stamp is now measured where it would have to show:
    a site is `crawl_stamped` iff >=70% of the docs pulled on its modal (bulk) crawl day,
    >=20 of them, are dated ON that day — see the comment above crawl_stamped_sites(). The
    >=100-doc floor is kept. (2026-10-07) PLUS a multi-batch DATE-day test for the source's
    own regeneration stamps (Suzhou: 38% + 31% on two days we never crawled on): bulk
    date-days (>=20 docs, >=10% of the site, day != 1) summing to >=50% of the site's dated
    docs. `missing` = no date_published. `body_scanned` is reserved: the
    crawlers do not record where a date came from, so it cannot be derived today. Else `good`.

A5  lead_issuer — doc_issuers.lead_issuer verbatim (the issuer field of record).

A6  province (2026-10-07) — the 2-letter code (scripts/rnd/analysis/geo.PROVINCE_CODE) of
    the locality that ISSUED a sub-national document, so that docs on NATIONAL sites
    (npc 地方法规 ~28.6k, miit 省通信管理局 ~740, bjrd …) can join a provincial chain:
    build_diffusion_events.province_of() is per SITE and returns None for them, which
    dropped 163 localized_of pairs in pair-channels.md and kept every npc provincial
    instrument out of the provincial-anchor matcher. The name is taken from the SAME
    header fields that set the level, in the A1 order — lead_issuer, the 文号 agency
    (DOCNUM_SUBNATIONAL), `publisher` (X省人大常委会), the title masthead, the
    localize() locality, the title head — and resolved to a province through
    jurisdiction_chain() (province itself / city -> province / district -> city ->
    province), falling back to the longest province- or city-name prefix of the name
    (延边朝鲜族自治州人民政府). NULL for central / media / research docs and when no
    field names a locality; consumers fall back to province_of(site) on NULL, so a doc
    whose site already carries a province behaves exactly as before.

A7  instrument_kind (2026-10-07, docs/working/qa-framework-gate.md) — the kind of text,
    orthogonal to `genre` (genre says whether the doc IS the text or is ABOUT it; kind
    says what the text is). It replaces the matcher's own gate (`is_framework` =
    FW_GENRES on algo_doc_type + FW_TITLE_RE), whose exclusions were right 23% of the
    time: it dropped 印发-wrapped 应急预案 / 若干措施 / 工作要点 / 重点工作任务 / 方案
    that cities implement (85% of the dropped pairs were real). Rules, first hit wins,
    on the KIND CORE = the printed text under an issuance wrapper (印发/发布/公布/颁布
    《X》 or 关于印发X的通知, trailing （试行）/（2014年本） groups stripped), else the
    title core:
    framework    (1) a statute: core ends in 法 / 条例 / 法典 (not 办法), or algo law;
                 (3) the matcher's OLD gate (FW_GENRES on algo_doc_type / FW_TITLE_RE on
                     the title) — so no anchor the old gate admitted is lost except
                     through rule (2), exactly the memo's "R1 OR the current test";
                 (5) R1 ADMIT: an issuance WRAPPER whose core names an 应急预案 / 预案 /
                     若干措施 / 政策措施 / 强化措施 / 便利化措施 / 工作要点 / 重点工作 /
                     重点任务 / 任务分工 / 工作安排 / 方案 — the wrapper is required
                     (a bare 应急预案 title scores 0.033 in the memo).
    housekeeping (2) BEFORE the old gate — the exclusions the memo names explicitly and
                     the old gate mislabels: 整改方案 / 组建方案 / 考评 / 考核 anywhere in
                     the core, 立法…计划 / 规章…计划. DECISION: a 考核办法 / 考评办法 is
                     housekeeping although 办法 is in FW_TITLE_RE — the memo reads 考评 /
                     考核 as the issuer's own management rules; this is the ONE place the
                     new gate is narrower than the old one (--dry-run-kind prints the
                     removed set; 2026-10-07 live run: +1,781 added / -291 removed, every
                     removal a 考核/考评 text — some of which DO cascade (食品安全工作
                     评议考核办法, 菜篮子市长负责制考核办法); dropping 考评|考核 from
                     KIND_HK_STRONG_RE is the one-line reversal if that cost is too high).
                 (4) AFTER the old gate — the memo's remaining exclusions / keep-excluding
                     shapes: 申报 in its CALL shape only (关于组织申报…的通知; 经营者集中
                     申报标准的规定 is an instrument and stays with rule 3), 评选 / 名单 /
                     遴选; a core ending in 名单 / 目录 / 清单 / 指南 / 指引 / 标准 / 规范 /
                     规程 / 制度 / 规则 / 章程 / 准则 (an 议事规则 typed `regulation` is
                     kept by rule 3; an untyped one is housekeeping).
    other        everything else — including a bare 通知 with no printed core, which the
                 hand-check found MIXED (6 instruments / 4 administrative / 1 unclear):
                 its instrument status comes from the 文号, not the title, so it is left
                 undecided rather than labelled housekeeping.
    Consumers: build_diffusion_events.is_framework / can_anchor and pairs.parent_is_framework
    read `instrument_kind == 'framework'` when the row carries it and fall back to the old
    gate on NULL (a half-built table never breaks the matcher).

USAGE (repo root; the DB is the droplet's documents.db)
-------------------------------------------------------
    python3 scripts/build_doc_identity.py --self-test
    python3 scripts/build_doc_identity.py --dry-run          # compute + stats, no write
    python3 scripts/build_doc_identity.py --dry-run-flips    # flip counts (broad / in-chain / date rule), reversed-edge
                                                             # audit, slack evidence, province coverage; read-only
    python3 scripts/build_doc_identity.py --dry-run-kind     # A7 instrument_kind by level + framework-gate
                                                             # before/after (old matcher gate vs kind); read-only
    python3 scripts/build_doc_identity.py                    # full rebuild, one transaction
    python3 scripts/build_doc_identity.py --validate         # A1–A4 checks against known truth
    python3 scripts/build_doc_identity.py --sample 60 --seed 7   # stratified hand-check dump

WRITE DISCIPLINE: busy_timeout=30s, one transaction, only touches `doc_identity`.
Refuses to write while the nightly lock (/tmp/china-governance-daily-sync.lock.d)
exists unless --force. daily_sync.sh Phase 2b runs it with --force (it holds the
lock itself) after issuer_parser / compute_scores and before build_diffusion_events.
"""
import argparse
import os
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("CG_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "classification"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))

from extract_citations import (  # noqa: E402
    _norm_title, _title_cores_of_title, _WRAP_QUOTED, _WRAP_PLAIN, _MASTHEAD_PRE,
    _INST_SUFFIX, _STATUS_TAG, _NEWS_LEAD, _TITLE_STRIP, _clean_ref,
    _CORE_DOCNUM, _DOCNUM_TAIL, _FULLWIDTH_DIGITS)
from issuer_parser import REGISTRY, DOCNUM_SUBNATIONAL, DOCNUM_CENTRAL  # noqa: E402
from build_diffusion_events import (  # noqa: E402
    NONISSUE_RE, load_site_names, province_of, FW_GENRES, FW_TITLE_RE, ABOUT_GENRES,
    is_framework as _matcher_is_framework)
from geo import (  # noqa: E402,F401
    CITY_PROVINCE, DISTRICT_CITY, CITY_PROVINCE_CSV, PROVINCE_CODE, load_city_province,
    province_name_of_place)
from genre_typer import clean_title, _TRAILING_ANNOT_RE  # noqa: E402

# The `npc` site (国家法律法规数据库, crawlers/npc.py) is tagged admin_level=central
# as a whole, but ~28k of its rows are provincial/municipal 人大 instruments
# (地方法规 + their amendment/repeal decisions + 法规性决定, which are ALL local
# 人大常委会 decisions — none starts with 全国人民代表大会). Only these categories
# (classify_main_name) are genuinely national-level instruments. (Moved here from
# build_diffusion_events, which now reads admin_level_doc instead.)
NPC_NATIONAL_CATEGORIES = frozenset({
    "宪法", "法律", "修正案", "法律解释", "行政法规", "监察法规",
    "有关法律问题和重大问题的决定",
    "修改、废止的决定（法律）", "修改、废止的决定（行政法规）",
    "高法司法解释", "高检司法解释", "联合发布司法解释", "修改、废止的决定（司法解释）",
})
# algo_doc_type labels that mark a sub-national doc as an implementing INSTRUMENT
# (diffusion-fidelity.md's implementing-instrument subset + the framework labels
# the typer also emits). NOT: explainer, announcement, report, publicity,
# commentary, interview, reply, circular, administrative, budget, procurement,
# personnel, consultation, application_guide, standard, review, request, other.
IMPLEMENTING_GENRES = frozenset({
    "action_plan", "work_plan", "policy_issuance", "opinion", "notice",
    "regulation", "decision", "strategy", "subsidy", "law", "decree", "plan",
})

try:  # web.services.documents pulls in the jieba segmenter; fall back to a copy
    from web.services.documents import ADMIN_LEVEL_PREFIXES  # noqa: E402
except Exception:  # pragma: no cover
    ADMIN_LEVEL_PREFIXES = {
        "central": ["国发", "国办", "国函", "中发", "中办", "发改", "国土资", "建市", "建房",
                    "建科", "人社部", "国税", "财综", "财预", "财建", "环发", "银监",
                    "工信部", "水资源"],
        "provincial": ["粤府", "粤办", "粤财", "粤价", "粤发", "粤卫", "粤环"],
        "municipal": ["深府", "深发", "深办", "深市", "深人", "深规土", "深建", "深前海"],
        "district": ["深坪", "深福", "深南", "深龙", "深宝", "深盐", "深光", "深罗"],
    }

DB_PATH = ROOT / "documents.db"
LOCK_DIR = Path("/tmp/china-governance-daily-sync.lock.d")

LEVELS = ("central", "provincial", "municipal", "district", "department", "media", "research")
LEVEL_RANK = {"central": 0, "provincial": 1, "municipal": 2, "department": 2,
              "district": 3, "media": 4, "research": 4, None: 5, "": 5, "unknown": 5}
NON_ISSUER_SITE_LEVELS = {"media", "research"}
DEPT_SITE_FALLBACK = {"department": "municipal"}
SUBNATIONAL = {"provincial", "municipal", "district", "department"}

# --------------------------------------------------------------------------- #
# A1. level of an agency / locality name                                       #
# --------------------------------------------------------------------------- #
_CENTRAL_NAMES = set(REGISTRY)
_CENTRAL_HEAD = re.compile(r"^(?:中共)?(?:国家|国务院|中共中央|中央|全国|最高人民)")
_LOCALITY_TOKEN = re.compile(r"省|市|自治区|自治州|地区|区|县|分行|分局|特派|驻")
_PROV_MUNI = ("北京市", "上海市", "天津市", "重庆市")
_PROV_HEAD = re.compile(
    r"^(?:中共)?(?:[一-鿿]{2,3}省|[一-鿿]{2,7}自治区|北京市|上海市|天津市|重庆市)")
_PREFECTURE = re.compile(r"自治州|地区|^(?:中共)?[一-鿿]{2,5}盟")
_DISTRICT = re.compile(r"(?<!自治)(?<!地)区(?!域)|县|旗(?=人民|政府|人大|委|$)")  # 旗 = Inner Mongolia banner
_MUNI_HEAD = re.compile(r"^(?:中共)?[一-鿿]{2,4}市")  # 乌鲁木齐市 / 呼伦贝尔市 are 4 chars
_GENERIC_HEAD = re.compile(r"^(?:中共)?(省|市|区|县)")


def level_of_name(name):
    """Administrative level of an issuer / locality name, or None."""
    n = (name or "").strip()
    if not n:
        return None
    if n in _CENTRAL_NAMES:
        return "central"
    if _CENTRAL_HEAD.match(n) and not _LOCALITY_TOKEN.search(
            _CENTRAL_HEAD.sub("", n)):
        return "central"
    if _PREFECTURE.search(n):
        return "municipal"
    if _DISTRICT.search(n):
        return "district"
    if _PROV_HEAD.match(n):
        return "provincial"
    if _MUNI_HEAD.match(n):
        return "municipal"
    m = _GENERIC_HEAD.match(n)
    if m:
        return {"省": "provincial", "市": "municipal", "区": "district", "县": "district"}[m.group(1)]
    return None


# 文号 prefix: the CJK run before the first bracket; drop 依据/依照 metadata leads.
_DOCNUM_PREFIX = re.compile(r"^[一-鿿]{1,12}(?=[〔\[（(【〈《])")
_SUBNAT_PREFIXES = sorted(DOCNUM_SUBNATIONAL, key=len, reverse=True)
_CENTRAL_PREFIXES = sorted(DOCNUM_CENTRAL, key=len, reverse=True)
_WEB_PREFIXES = sorted(((p, lvl) for lvl, ps in ADMIN_LEVEL_PREFIXES.items() for p in ps),
                       key=lambda x: len(x[0]), reverse=True)


def _docnum_prefix(docnum):
    """The agency prefix of a 文号 (粤府办 of 粤府办〔2024〕3号), None if none / generic."""
    dn = (docnum or "").strip()
    for meta in ("依据", "依照"):
        if dn.startswith(meta):
            dn = dn[len(meta):]
    m = _DOCNUM_PREFIX.match(dn)
    if not m:
        return None
    prefix = m.group(0)
    if prefix.startswith(("公告", "通告", "通知", "令", "第")):
        return None
    return prefix


def docnum_agency(docnum):
    """Sub-national agency the 文号 registry names for this prefix (粤府 -> 广东省人民政府)."""
    prefix = _docnum_prefix(docnum)
    if prefix:
        for p in _SUBNAT_PREFIXES:
            if prefix.startswith(p):
                return DOCNUM_SUBNATIONAL[p]
    return None


def level_of_docnum(docnum, site_level):
    prefix = _docnum_prefix(docnum)
    if not prefix:
        return None
    agency = docnum_agency(docnum)
    if agency:
        return level_of_name(agency)
    for p, lvl in _WEB_PREFIXES:
        if prefix.startswith(p):
            return lvl
    if site_level == "central":
        for p in _CENTRAL_PREFIXES:
            if prefix.startswith(p):
                return "central"
    return None


_TITLE_HEAD_CUT = re.compile(
    r"(关于|印发|转发|批转|公布|发布|《|丨|\||：|:|对|就|在|向|与|为|组织|开展|召开|举办|举行|"
    r"发出|部署|要求|强调|指出|调研|会见|出席|主持|公告|通告|决定|令$)")
_STATUS_LEAD = re.compile(r"^[（(【\[〔][^）)】\]〕]{1,8}[)）】\]〕]\s*")
_HEAD_SHAPE = re.compile(r"^[一-鿿·、（）()\s]{2,40}$")
# …and it ends like an institution (…办公厅 / …人民政府 / …局) or a bare instrument (…条例)
_HEAD_END = re.compile(
    _INST_SUFFIX + r"$|(?:条例|办法|规定|规则|准则|细则|章程|规程|决定|意见|方案|计划|规划|纲要|措施|法|法典)$")


def title_head(title):
    """The issuer / instrument HEAD of a title (before the verb frame), or None when the
    head is not name-shaped."""
    t = _STATUS_LEAD.sub("", clean_title(title))
    m = _TITLE_HEAD_CUT.search(t)
    head = t[: m.start()] if m else t
    head = head.strip(" 　")
    # an issuer head is a contiguous CJK run (no spaces / digits / punctuation):
    # '保障防控前提下租房需求 经纪人进社区 人数次数设限制' is a headline, not a name
    if not head or len(head) > 40 or not _HEAD_SHAPE.match(head) or not _HEAD_END.search(head):
        return None
    return head


def level_of_title(title):
    """Level of the issuer named at the HEAD of a title (before the verb frame)."""
    head = title_head(title)
    if not head:
        return None
    if head.startswith("中华人民共和国"):
        return "central"
    return level_of_name(head)


def derive_level(doc, site_level, lead_issuer):
    """-> (admin_level_doc, level_source) per the A1 priority chain."""
    if site_level in NON_ISSUER_SITE_LEVELS:
        return site_level, "site"
    lvl = level_of_name(lead_issuer)
    if lvl:
        return lvl, "issuer"
    lvl = level_of_docnum(doc["docnum"], site_level)
    if lvl:
        return lvl, "docnum"
    if doc["site"] == "npc":
        if doc["cat"] in NPC_NATIONAL_CATEGORIES:
            return "central", "npc_publisher"
        lvl = level_of_name(doc["publisher"])
        if lvl:
            return lvl, "npc_publisher"
    lvl = level_of_title(doc["title"])
    if lvl:
        return lvl, "title_cue"
    # the 13 `department` sites are all Shenzhen MUNICIPAL bureaus (crawlers/gkmlpt.py);
    # a bureau's level is its government's level, so the fallback is municipal.
    return DEPT_SITE_FALLBACK.get(site_level, site_level or "unknown"), "site"


# --------------------------------------------------------------------------- #
# A6. province of the issuing locality                                         #
# --------------------------------------------------------------------------- #
# Longest-first province / prefecture names, the fallback for heads _LOC_FIRST cannot
# segment (延边朝鲜族自治州人民政府: a 5-char 自治州).
_PLACE_PREFIXES = sorted(set(PROVINCE_CODE) | set(CITY_PROVINCE), key=len, reverse=True)


def province_code_of_locality(loc):
    """2-letter code of the province a localize()/locality_of_head() locality sits in:
    the province itself, a city's province, a district's city's province. None for an
    unknown / unqualified ('<municipal>@sz') locality."""
    if not loc or loc.startswith("<"):
        return None
    chain = jurisdiction_chain(loc)
    if chain is None:
        name = province_name_of_place(loc)
    else:
        name = loc if chain == () else chain[-1]
    return PROVINCE_CODE.get(name) if name else None


def province_of_name(name):
    """Province code of a sub-national agency / locality NAME (江苏省人民代表大会常务委员会
    -> js, 深圳市人民政府 -> gd, 海南省通信管理局 -> hi); None for a central or
    unrecognized name."""
    if not name:
        return None
    name = name.strip(" 　​")
    if level_of_name(name) == "central":
        return None
    code = province_code_of_locality(locality_of_head(name))
    if code:
        return code
    for place in _PLACE_PREFIXES:
        if name.startswith(place) and len(name) > len(place):
            return PROVINCE_CODE.get(province_name_of_place(place))
    return None


def derive_province(doc, lead_issuer):
    """A6: province code of a SUB-NATIONAL doc's issuing locality, from the header
    fields in A1 order; None when none names a locality (consumers then fall back
    to the site's province)."""
    for name in (lead_issuer, docnum_agency(doc["docnum"]), doc["publisher"],
                 masthead_of(doc["title"])):
        code = province_of_name(name)
        if code:
            return code
    code = province_code_of_locality(doc.get("_loc"))
    if code:
        return code
    return province_of_name(title_head(doc["title"]))


# --------------------------------------------------------------------------- #
# A3. genre                                                                    #
# --------------------------------------------------------------------------- #
EXPLAINER_RE = re.compile(
    r"解读|答记者问|一图读懂|一图看懂|图解|图读|政策问答|问答|答问|解答|划重点|读懂|看懂|权威解|负责人就")
READOUT_RE = re.compile(
    r"会议(?!事|制度|规则|室|费)|召开|讲话|调研|座谈|会见|出席|主持|考察|致辞|发言|强调|指出|研讨|调度|督导|走访|慰问|"
    r"举办|举行|开展|"
    r"开幕|闭幕|签约|揭牌|启动仪式|专题学习|传达学习|集体学习|党组会|常委会会议|电视电话会")
NEWS_RE = re.compile(
    r"新闻|报道|快讯|要闻|动态|发布会|记者|回应|反响|热议|侧记|综述|述评|评论|速递|播报|聚焦|"
    r"观察|盘点|亮点|看点|干货|微视频|视频|海报|漫画|有啥|怎么看|怎么办|→|正式发布|"
    r"[^印]发布$|本[报网站台]讯|电$|\d+月\d+日电")
IMPL_RE = re.compile(
    r"实施方案|实施意见|实施细则|实施办法|实施《[^》]+》(?:的)?(?:办法|细则|规定|条例|决定)|变通规定|"
    r"贯彻落实|贯彻|落实|转发|批转|若干措施|具体措施")
CONSULT_RE = re.compile(r"征求.{0,6}意见|意见征集|意见稿|公开征求")
# issuance frame (2)-(4): 关于…的通知/意见/…, …令; (1) is the matcher's institutional
# 印发/发布/公布《X》 wrapper (a bare 《X》 or a masthead before the verb — '北京发布《X》'
# is a news lead, not a promulgation, exactly as extract_citations treats it).
# 公告/通告 are normative only at the centre (税务总局公告 = tax rulings); a local
# 公告 (查处非法社会组织 / 入库名单) is administrative and stays `other`.
_ISSUANCE_FRAME = re.compile(
    r"关于.{2,80}的(?:通知|意见|决定|办法|规定|细则|方案|计划|规划|"
    r"批复|函|纲要|措施|规则|准则|指引|指南)$|令$|第[\d〇零一二三四五六七八九十百]{1,6}号令")
_CENTRAL_ANNOUNCE = re.compile(r"关于.{2,80}的?(?:公告|通告|公报)$")
_BARE_INSTRUMENT = re.compile(
    r"(?:条例|办法|规定|规则|准则|细则|章程|规程|决定|意见|方案|计划|规划|纲要|措施|指引|指南|标准|法|法典)$")
_FULLTEXT_TAIL = re.compile(r"(?:的)?全文$")
_HEADLINE_PUNCT = re.compile(r"[，,：:！!？?；;]")
PROMUL_GENRES = frozenset({
    "regulation", "law", "decree", "opinion", "action_plan", "policy_issuance",
    "strategy", "plan", "work_plan", "decision", "notice", "subsidy", "standard"})
ADMIN_GENRES = frozenset({"personnel", "procurement", "budget", "publicity", "report"})


def title_core(title):
    """clean_title minus trailing 文号 / date / 已废止 annotations and a 全文 tail,
    keeping 《》 balanced (genre_typer.core_title drops a trailing 》, which would
    defeat the wrapper regexes)."""
    t = clean_title(title)
    for _ in range(4):
        nt = _TRAILING_ANNOT_RE.sub("", t).strip()
        nt = re.sub(r"[\s、，,。.·\-—]+$", "", nt).strip()
        if nt == t or not nt:
            break
        t = nt
    return _FULLTEXT_TAIL.sub("", t)


def _quoted_wrapper(core):
    """-> 'inst' (bare 《X》 or masthead+verb《X》), 'news' (non-masthead lead+verb《X》,
    e.g. 北京发布《X》), or None."""
    m = _WRAP_QUOTED.match(core)
    if not m:
        return None
    pre = m.group("pre").strip()
    if pre == "":
        return "inst"
    if m.group("verb") is None:
        return None  # 贯彻落实《X》 — about X
    return "inst" if _MASTHEAD_PRE.match(pre) else "news"


def _institutional_wrapper(core):
    return _quoted_wrapper(core) == "inst" or bool(_WRAP_PLAIN.match(core))


def is_issuance_frame(core, full, level=None):
    return (_institutional_wrapper(core) or bool(_ISSUANCE_FRAME.search(core)) or (
        level == "central" and bool(_CENTRAL_ANNOUNCE.search(core))) or (
        bool(_BARE_INSTRUMENT.search(core)) and not READOUT_RE.search(full)
        and not core.startswith("关于") and len(core) <= 60
        and not _HEADLINE_PUNCT.search(core)))  # '…发展，安徽出台…实施办法' is a headline


def derive_genre(title, algo_type, level):
    """-> promulgation | implementing | explainer | readout | news | other."""
    full = clean_title(title)
    core = title_core(title)
    if not full:
        return "other"
    if EXPLAINER_RE.search(full):
        return "explainer"
    frame = is_issuance_frame(core, full, level)
    if READOUT_RE.search(full) and not frame:
        return "readout"
    if not frame and (NEWS_RE.search(full) or NONISSUE_RE.search(full)
                      or _quoted_wrapper(core) == "news"):
        return "news"
    if CONSULT_RE.search(full) or algo_type == "consultation":
        return "other"  # a draft out for comment is not (yet) an instrument
    if algo_type in ADMIN_GENRES and not _institutional_wrapper(core):
        return "other"  # 任职的通知 / 中标公告 / 决算: administrative acts, not instruments
    if level in SUBNATIONAL and IMPL_RE.search(core) and (
            frame or algo_type in IMPLEMENTING_GENRES or algo_type == "regulation"):
        return "implementing"
    if frame:
        return "promulgation"
    if level == "media":
        return "news"  # on a media site only an institutional frame is a reprint; the rest is news
    if level == "research":
        return "other"  # reports, translations (chinalawtranslate), institute notices
    if algo_type in PROMUL_GENRES:
        return "promulgation"
    if NEWS_RE.search(full):
        return "news"
    return "other"


# --------------------------------------------------------------------------- #
# A7. instrument kind (docs/working/qa-framework-gate.md §4)                   #
# --------------------------------------------------------------------------- #
# A looser plain wrapper than extract_citations._WRAP_PLAIN: the verb may precede 关于
# (广东省人民政府印发关于进一步促进科技创新若干政策措施的通知, memo appendix #5).
_KIND_WRAP_LOOSE = re.compile(
    r"^[一-鿿\s丨·、]*?(?:关于)?(?:印发|发布|公布|颁布)(?:关于)?(?P<core>[^《》]{4,}?)的(?:通知|函|通告|公告)$")
_PAREN_TAIL = re.compile(r"(?:\s*[（(][^（()）]{1,20}[)）])+$")
# (1) statutes — 法 but not 办法/做法/看法/说法/想法
KIND_STATUTE_RE = re.compile(r"(?<![办做看说想])法$|条例$|法典$")
# (2) housekeeping the memo names explicitly, which the OLD gate mislabels (a 考核办法
#     via 办法; a 立法工作计划 typed `plan`; a 党组整改方案 typed action_plan) — the only
#     rule that overrides the old gate.
KIND_HK_STRONG_RE = re.compile(r"整改方案|组建方案|考评|考核|立法.{0,4}计划|规章.{0,4}计划")
# (4) the memo's other exclusions / keep-excluding shapes, AFTER the old gate: 申报 only
#     in its CALL shape (关于组织申报…的通知), never as a subject (经营者集中申报标准的规定
#     is a State Council instrument); list / guide / internal-rule tails.
KIND_HK_RE = re.compile(
    r"组织.{0,8}申报|开展.{0,12}申报|申报工作|申报.{0,10}的(?:通知|公告|函)$|评选|名单|遴选")
KIND_HK_TAIL_RE = re.compile(r"(?:名单|目录|清单|指南|指引|标准|规范|规程|制度|规则|章程|准则)$")
# (5) R1 admit — only under an issuance wrapper
KIND_ADMIT_RE = re.compile(
    r"应急预案|预案|若干.{0,6}措施|政策措施|强化措施|便利化措施|工作要点|重点工作|重点任务|任务分工|工作安排|方案")
INSTRUMENT_KINDS = ("framework", "housekeeping", "other")


def issuance_inner(core):
    """-> (printed text under the issuance wrapper, verb present). A bare 《X》 title
    yields (X, False); no wrapper yields (None, False)."""
    m = _WRAP_QUOTED.match(core)
    if m:
        pre = m.group("pre").strip()
        if m.group("verb") is not None:
            return m.group("core"), True
        if pre == "":
            return m.group("core"), False
    m = _WRAP_PLAIN.match(core) or _KIND_WRAP_LOOSE.match(core)
    if m:
        return m.group("core"), True
    return None, False


def kind_core(title):
    """-> (kind core, wrapped): the text whose kind we judge — the wrapper's inner
    (印发《X》的通知 -> X), else the title core; trailing （…） groups stripped."""
    core = title_core(title)
    inner, wrapped = issuance_inner(core)
    kc = _PAREN_TAIL.sub("", inner if inner is not None else core).strip()
    return kc, wrapped


def derive_instrument_kind(title, algo_type):
    """-> framework | housekeeping | other (module docstring A7)."""
    full = clean_title(title)
    if not full:
        return "other"
    kc, wrapped = kind_core(title)
    if KIND_STATUTE_RE.search(kc) or algo_type == "law":
        return "framework"
    if KIND_HK_STRONG_RE.search(kc):
        return "housekeeping"
    if algo_type in FW_GENRES or FW_TITLE_RE.search(full):
        return "framework"  # the old matcher gate: nothing it admitted is lost beyond (2)
    if KIND_HK_RE.search(kc) or KIND_HK_TAIL_RE.search(kc):
        return "housekeeping"
    if wrapped and KIND_ADMIT_RE.search(kc):
        return "framework"
    return "other"


# --------------------------------------------------------------------------- #
# A2. instrument key                                                           #
# --------------------------------------------------------------------------- #
KEY_MIN = 6
EDITION_GAP_DAYS = 400
# Pool CLASS: promulgations and the untyped residual may be copies of one text;
# an implementing instrument (转发/实施方案 at a lower level) is a distinct act and
# pools only with its own copies; explainer / readout / news never pool.
POOL_CLASS = {"promulgation": "p", "other": "p", "implementing": "i"}


# Only an instrument NAME may use the unfolded-length exemption below. Measured on the
# 2026-10-07 corpus the exemption admits 191 distinct folded keys, 186 of which are
# national statute names (行政复议法, 民法典, 抗旱条例, 刑法修正案 …); the residue is
# 中华人民共和国国务院令 (19 docs on 3 sites), 中华人民共和国财政部令 and 中华人民共和国
# 外交部声明 — a 令 / 声明 is the VEHICLE, not the text's name, so dozens of unrelated
# State Council orders share that one title and must NOT pool. A suffix gate keeps the
# exemption to names: the folded core must look like a statute.
_SHORT_KEY_RE = re.compile(r"(?:法|法典|条例|修正案)$")


def _key_len(core):
    """Length that the KEY_MIN floor is measured on: the normalized core BEFORE the
    中华人民共和国 fold.

    WHY (2026-10-07, the 城乡规划法 pooling defect): `_norm_title` strips the PRC
    prefix, so a national law normalizes SHORT — 中华人民共和国城乡规划法 -> 城乡规划法,
    5 chars — and the floor (which exists to stop generic micro-titles like '全文' /
    '停水通知' pooling across sites) silently rejected the key entirely. Every copy of
    such a law therefore got NO instrument key and stayed `instrument_role='unique'`:
    the mee and npc copies of 城乡规划法, both titled identically and both dated
    2019-04-23, never pooled. This is the same class of bug the resolver fixed in the
    2026-10 proxy-target work (`_EXACT_MIN_LEN`), for the same reason.

    Measuring the floor on the UNFOLDED length keeps its purpose (a title has to carry
    >= KEY_MIN real characters to be poolable) while letting the fold do its job (the
    key itself stays the folded form, so 《中华人民共和国海关法》 / 中华人民共和国海关法 /
    海关法 still key together). Only titles that are long enough BEFORE the fold gain a
    key, so nothing generic is admitted."""
    return len(_TITLE_STRIP.sub("", _clean_ref(core) or ""))


def _core_ok(nc, core):
    """Does this core clear the KEY_MIN floor? Either on the folded length, or — for a
    statute name only — on the unfolded length (`_key_len` / `_SHORT_KEY_RE`)."""
    return len(nc) >= KEY_MIN or (bool(_SHORT_KEY_RE.search(nc)) and _key_len(core) >= KEY_MIN)


def _best_core(title):
    """-> (raw core, normalized core) of a stored title (the matcher's exact-core
    tier), or (None, None) when nothing reaches KEY_MIN."""
    title = _FULLTEXT_TAIL.sub("", clean_title(title))
    cores = _title_cores_of_title(title or "")
    best = raw = None
    for core, flag in cores:
        if flag != 1:
            continue  # non-institutional lead ('北京发布《X》') is news ABOUT X
        nc = _norm_title(core)
        if not _core_ok(nc, core):
            continue
        # prefer the innermost (shortest) institutional core: the 《X》 over the wrapper
        if best is None or len(nc) < len(best):
            best, raw = nc, core
    if best is None:
        raw = clean_title(title)
        nt = _norm_title(raw)
        if _core_ok(nt, raw):
            best = nt
        else:
            raw = None
    return raw, best


def instrument_key(title):
    """Normalized instrument core of a stored title (the matcher's exact-core tier)."""
    return _best_core(title)[1]


# --- localized re-issuance ---------------------------------------------------
# First locality element of a name: X省 / X自治区 / X市 / X自治州 / X地区 / X盟
# (乌鲁木齐市 is 4 chars; 新疆维吾尔自治区 is 5 + 自治区); optional district element.
_LOC_FIRST = re.compile(
    r"^([一-鿿]{2,3}省|[一-鿿]{2,7}?自治区|[一-鿿]{2,4}?(?:市|自治州|地区|盟))")
_LOC_DISTRICT = re.compile(r"^[一-鿿]{2,4}?(?:新区|区|县|旗)")
_LOC_LEVELS = ("provincial", "municipal", "district")


def _known_localities():
    """Locality names the 文号 registry already vouches for (广东省, 深圳市, 苏州市 …)."""
    out = set(_PROV_MUNI)
    for agency in DOCNUM_SUBNATIONAL.values():
        a = agency[2:] if agency.startswith("中共") else agency
        m = _LOC_FIRST.match(a)
        if m:
            out.add(m.group(1))
    return frozenset(out)


KNOWN_LOCALITIES = _known_localities()


def masthead_of(title):
    """The issuing-body masthead before the 关于/印发 frame of a title ('' if none)."""
    t = _NEWS_LEAD.sub("", _STATUS_TAG.sub("", title_core(title)))
    m = _WRAP_QUOTED.match(t) or _WRAP_PLAIN.match(t)
    if m:
        pre = m.group("pre")
    else:
        i = t.find("关于")
        pre = t[:i] if i > 0 else ""
    pre = pre.strip(" 　丨·、")
    return pre if pre and _MASTHEAD_PRE.match(pre) else ""


def locality_of_head(head):
    """Sub-national locality named by an issuer masthead: '深圳市', '广东省',
    '深圳市龙华区'; '<municipal>' for an unqualified self-reference (市人民政府办公室);
    None for a central or unrecognized head."""
    lvl = level_of_name(head)
    if lvl not in _LOC_LEVELS:
        return None
    h = head[2:] if head.startswith("中共") else head
    m = _LOC_FIRST.match(h)
    loc = m.group(1) if m else ""
    if lvl == "district":
        md = _LOC_DISTRICT.match(h[len(loc):])
        if md:
            loc += md.group(0)
    return loc or f"<{lvl}>"


def locality_in_core(core, masthead_loc):
    """A locality PREFIX inside an instrument core ('深圳市推动…行动方案' -> '深圳市'),
    accepted only when the 文号 registry knows the name, the doc's own masthead names
    it, or it is province-shaped (X省 / X自治区) — '智慧城市建设方案' is not a locality."""
    m = _LOC_FIRST.match(core) or _LOC_DISTRICT.match(core)
    if not m:
        return None
    loc = m.group(0)
    if loc in KNOWN_LOCALITIES:
        return loc
    if masthead_loc and (masthead_loc.startswith(loc) or masthead_loc.endswith(loc)):
        return loc
    if loc.endswith(("省", "自治区")) and _PROV_HEAD.match(loc):
        return loc
    return None


def locality_rank(loc):
    """LEVEL_RANK of a locality string from locality_of_head / locality_in_core."""
    if loc.startswith("<"):
        return LEVEL_RANK[loc.strip("<>")]
    return LEVEL_RANK.get(level_of_name(loc + "人民政府"), 5)


def localize(title, site):
    """-> (stem, locality, locality_rank) for pooling. stem = normalized core minus a
    locality prefix (the text a central instrument and its local re-issuance share);
    locality = the sub-national name the title carries (masthead or core prefix),
    None when the title names none (a bare / central-masthead copy)."""
    raw, key = _best_core(title)
    if key is None:
        return None, None, None
    mast_loc = locality_of_head(masthead_of(title))
    core_loc = locality_in_core(raw, mast_loc if mast_loc and not mast_loc.startswith("<") else "")
    stem = key
    if core_loc:
        s = _norm_title(raw[len(core_loc):])
        if len(s) >= KEY_MIN:
            stem = s
        else:
            core_loc = None
    loc = core_loc or mast_loc
    if core_loc and mast_loc and not mast_loc.startswith("<") and mast_loc.endswith(core_loc):
        loc = mast_loc  # 龙华区X issued by 深圳市龙华区人民政府: the fuller name
    if loc is None:
        return stem, None, None
    if loc.startswith("<"):
        loc = f"{loc}@{site}"  # unqualified 市政府: its own site, never pooled across
        return stem, loc, LEVEL_RANK[loc[1:loc.index(">")]]
    return stem, loc, locality_rank(loc)


# --- jurisdictional chain (for the genre flip) --------------------------------
# CITY_PROVINCE (data/city_province.csv) and DISTRICT_CITY (bare district -> city) live in
# scripts/rnd/analysis/geo.py, shared with build_diffusion_events.province_of so the
# two scripts cannot drift apart on which city sits in which province.

# Stems every government writes for ITSELF (self-government housekeeping): a same-stem
# text above the doc is not its parent, so these never flip to `implementing`.
GENERIC_STEM_RE = re.compile(
    r"议事规则|"                                    # 人大常委会/政府 议事规则
    r"制定地方性法规条例|立法条例|"                  # how the local 人大 legislates
    r"讨论.?决定重大事项|"                          # 人大常委会 讨论、决定重大事项的规定
    r"(?:修改|废止)(?:部分|一批|有关)?(?:地方性)?(?:法规|规章|规范性文件|文件|决定)|"  # omnibus amend/repeal decisions
    r"宣布失效|"                                    # 宣布失效一批文件的决定
    r"主要职责内设机构和人员编制|"                   # 三定规定
    r"政府工作规则|"                                # 政府工作规则
    r"(?:政府网站|依法行政|法治政府建设)(?:绩效)?考评|"  # self-assessment schemes
    r"重大行政决策事项目录|"                         # annual decision catalogues
    r"(?:预算|国有资产|规范性文件|计划).{0,4}(?:审查)?监督(?:条例|办法|规定)")  # 人大 oversight regs


def jurisdiction_chain(loc):
    """Ancestor localities of a locality string from localize(): () for a province /
    直辖市 (central is the only superior), ('广东省',) for a city, ('深圳市', '广东省')
    for a district; None when the locality is unknown / unqualified ('<municipal>@sz',
    a false detection such as '转发市')."""
    if not loc or loc.startswith("<"):
        return None
    if loc in _PROV_MUNI or (loc.endswith(("省", "自治区")) and _PROV_HEAD.match(loc)):
        return ()
    if loc in CITY_PROVINCE:
        prov = CITY_PROVINCE[loc]
        return () if prov == loc else (prov,)
    city = DISTRICT_CITY.get(loc)
    if city is None:  # '深圳市龙华区' / '北京市密云区' / '广东省X县': strip the parent prefix
        m = _LOC_FIRST.match(loc)
        if m and len(loc) > len(m.group(1)):
            city = m.group(1)
    if city is None:
        return None
    if city in _PROV_MUNI:
        return (city,)
    prov = CITY_PROVINCE.get(city)
    if prov is None:
        return None if city.endswith("市") else (city,)  # X省X县: province only
    return (city, prov)


def in_chain(m, o):
    """Is higher-ranked same-stem member `o` in doc `m`'s own jurisdictional chain?"""
    if o["level"] == "central":
        return True
    chain = jurisdiction_chain(m["_loc"])
    return bool(chain) and o["_loc"] in chain


_DATE_RE = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})")


def _to_date(s):
    m = _DATE_RE.match(s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# A localized re-issuance cannot precede the text it localizes. Publication order is
# noisy by a few days (a ministry text adopted before, posted after, the province's
# copy), and a `-01` day is usually a month-precision stamp (docs/research/pair-channels.md
# §1; the distribution is printed by --dry-run-flips).
LOCALIZED_SLACK_DAYS = 7
MONTH_SLACK_DAYS = 31


def trigger_lag_floor(doc_date, trig_date):
    """Minimum accepted (doc_date - trig_date) in days for a date-valid trigger."""
    slack = LOCALIZED_SLACK_DAYS
    if doc_date.day == 1 or trig_date.day == 1:
        slack += MONTH_SLACK_DAYS
    return -slack


def is_date_valid_trigger(m, o):
    """Is candidate trigger `o` dated no later than doc `m` (within the slack)? An
    undated doc or trigger is never valid."""
    if not m["date"] or not o["date"]:
        return False
    return (m["date"] - o["date"]).days >= trigger_lag_floor(m["date"], o["date"])


def pick_trigger(m, higher):
    """The nearest date-valid IN-CHAIN parent among the higher same-stem members:
    latest date first (a city localizes its province's re-issuance, not the central
    original it also matches), then the closest level, then the lowest id."""
    valid = [o for o in higher if in_chain(m, o) and is_date_valid_trigger(m, o)]
    if not valid:
        return None
    return max(valid, key=lambda o: (o["date"], o["_rank"], -o["id"]))


# --- recurring instruments: one title, many texts ---------------------------
# (2026-10-07, surfaced by a72a341's canonical audit) A key group is pooled into
# EDITIONS by date gaps, and the gap is 400 days — so a title a government re-issues
# EVERY YEAR chains its whole run into ONE instrument: 政府工作报告 (a different text
# per year per government), 国务院关于落实《政府工作报告》重点工作分工的意见 (国发〔2014〕
# 15号 … 国发〔2022〕9号, 10 docs, one instrument), 国务院关于修改和废止部分行政法规的决定
# (14 docs across 国令 764/777/797), 惠州市人民政府关于防空警报试鸣的通告 (15 docs,
# 2014–2025), 深圳市森林火险黄色预警信号 (13 docs in 2.5 years). The pool's date range,
# its canonical, its citation_rank and any time series on it are then a merged phantom.
#
# The widest-span pools, by contrast, are genuine LATE-MIRROR sets that must STAY
# pooled: 中华人民共和国户口登记条例 (npc 1958 + a 公安局 repost 2008), 城市民族工作条例
# (npc 1993 + 福建/西藏 民委 reposts 2015–2021), 中华人民共和国宪法 (5 sites, 2018–2022).
# Span alone therefore cannot discriminate — a 50-year span is the HEALTHY case. Two
# tests intrinsic to the documents do:
#
#   R1 DISTINCT 文号 (the strong one). Copies of one text carry one 文号 or none;
#      an annual re-issuance carries its OWN. 546 pools hold >= 2 CONFLICTING 文号.
#      The number is taken from `document_number`, else from the title's own trailing
#      文号 group (_DOCNUM_TAIL) — which is where a 第N号 recurrence shows up, since
#      _title_cores_of_title strips that tail before keying (国务院关于修改和废止部分
#      行政法规的决定（…令 第843号） keys identically to the bare title).
#   R2 SAME-SITE REPEAT (for the un-numbered series: 预警信号 / 招聘公告 / 听证公告 /
#      政府工作报告 carry no 文号 at all). One site holds ONE copy of one text; a site
#      holding two copies months apart is re-issuing a SERIES. Gated on EVERY member
#      being the untyped `other` residual, because that gate is exactly what separates
#      the two sides on the data: of the 54 same-site-repeat pools spanning >= 1 year,
#      the 23 holding a promulgation are real statutes re-posted late (城市民族工作条例,
#      退役士兵安置条例, 深圳经济特区道路交通安全管理条例) and the 31 all-`other` ones are
#      series. A series title does not name a text, so its members pool with nothing.
#
# No title blocklist is needed: 台风/森林火险预警 fall to R2 as 'other'-genre series.
_DN_LING = re.compile(r'(?:令|第)\s*0*(\d+)\s*号')
SERIES_REPEAT_DAYS = 60  # a repost trickles in over weeks; a series re-issues monthly+
# A 文号 conflict is evidence of a different TEXT only when the copies are also
# temporally separated. `document_number` is not reliably the document's own (the
# a72a341 finding: chinatax stores the SUPERSEDING or merely REFERENCED instrument's
# number — 财库〔2020〕46号 on 国家税务总局关于落实《政府采购…办法》的通知, whose own number
# is 税总函〔2021〕67号; samr stores 市场监管总局令第60号 on a 通知 numbered 市监食协发
# 〔2024〕35号). Both of those pairs are 8-9 days apart: a mirror. Nothing a government
# re-issues comes round again inside a month, so requiring the two numbers' date ranges
# to be more than DOCNUM_SPLIT_MIN_DAYS apart keeps those pairs pooled while every
# recurrence this rule targets (>= a reporting period apart) still splits.
DOCNUM_SPLIT_MIN_DAYS = 30


# A digit-free bracket group inside a 文号 qualifies the AGENCY (深公交（规）〔2024〕3号,
# 深教规（试行）…) and breaks _CORE_DOCNUM, whose opening-bracket class matches the
# qualifier's '（' and then fails to find a year. Dropping such groups first is what lets
# 深公交（规）〔2024〕3号 and 深公交规〔2024〕3号 — the gazette's and the bureau's copy of ONE
# 通告 — key alike; without it the pair reads as un-numbered and R2 unpooled it.
_DN_QUALIFIER = re.compile(r'[（(【\[]\s*[^0-9（()）【】\[\]]{1,6}\s*[）)】\]]')


def _dn_keys(s):
    """(year|None, serial) keys of every 文号 in a string, year-form preferred."""
    s = _DN_QUALIFIER.sub("", (s or "").translate(_FULLWIDTH_DIGITS))
    out = [(m.group(2), m.group(3).lstrip("0") or "0") for m in _CORE_DOCNUM.finditer(s)]
    if not out:
        out = [(None, m.group(1).lstrip("0") or "0") for m in _DN_LING.finditer(s)]
    return out


def own_docnum_key(d):
    """This document's OWN 文号 identity as (year|None, serial), or None.

    `document_number` first; failing that the title's trailing own-文号 group
    (_DOCNUM_TAIL — '（中华人民共和国国务院令 第843号）'), never a mid-title mention of
    some other document's number. The agency string is deliberately NOT part of the key:
    folding 国令第473号 / 中华人民共和国国务院令第473号 / 第473号 to one key means a
    bracket-style difference can never SPLIT a mirror set, only a different number can."""
    k = _dn_keys(d.get("docnum"))
    if not k:
        m = _DOCNUM_TAIL.search(d["title"] or "")
        k = _dn_keys(m.group(0)) if m else []
    return k[-1] if k else None


def _canon_docnum_keys(keys):
    """Fold each year-less key onto the year-ful key with the same serial when that is
    unambiguous (a copy storing '第711号' is the same instrument as one storing
    '国令〔2019〕711号'); ambiguous or unmatched year-less keys stay on their own."""
    by_serial = defaultdict(set)
    for y, s in keys:
        if y:
            by_serial[s].add(y)
    out = {}
    for k in keys:
        y, s = k
        if y is None and len(by_serial.get(s, ())) == 1:
            out[k] = (next(iter(by_serial[s])), s)
        else:
            out[k] = k
    return out


def is_series(members):
    """R2: does this key name a recurring SERIES rather than one text? True when EVERY
    member is the untyped `other` residual and some single site holds two copies more
    than SERIES_REPEAT_DAYS apart (one site holds one copy of one text).

    The genre gate is what separates the two sides on the data. Of the 54 same-site-repeat
    pools spanning >= 1 year, the ones holding a `promulgation` are statutes re-posted
    late (城市民族工作条例 by 福建/西藏 民委 2015–2021, 退役士兵安置条例, 深圳经济特区道路交通
    安全管理条例) and the ones holding an `implementing` are a bureau's own re-postings of
    its 实施意见 (深圳市初中学业水平考试体育与健康科目考试实施意见, 3 szeb copies over 187
    days, all under 深教规〔2024〕2号) — both must stay pooled. `other` is the untyped
    residual that pools only because it shares the promulgation pool class, and that is
    where the series live: 政府工作报告, 预警信号, 招聘公告, 听证公告, 执法证遗失公告."""
    if any(m["genre"] != "other" for m in members):
        return False
    bysite = defaultdict(list)
    for m in members:
        if m["date"]:
            bysite[m["site"]].append(m["date"])
    return any((max(ds) - min(ds)).days > SERIES_REPEAT_DAYS
               for ds in bysite.values() if len(ds) > 1)


def _docnum_locality(d):
    """The locality the doc's own 文号 prefix names (惠府办 -> 惠州市), else None."""
    agency = docnum_agency(d.get("docnum"))
    loc = locality_of_head(agency) if agency else None
    return loc if loc and not loc.startswith("<") else None


def _own_locality(d):
    """The locality this copy itself claims — its 文号's, else its title masthead's
    (`_loc`, set in pass 1). An unqualified '<provincial>@site' self-reference names no
    locality and returns None."""
    loc = _docnum_locality(d)
    if loc:
        return loc
    loc = d.get("_loc")
    return loc if loc and not loc.startswith("<") else None


def _merge_close_keys(members, keys):
    """Fold together 文号 keys whose dated members sit within DOCNUM_SPLIT_MIN_DAYS of
    each other: that close in time, the difference is a mis-stored number on a mirror,
    not a re-issuance. A key with no dated member is merged with its nearest key (it
    carries no temporal evidence of its own).

    EXCEPT when the two numbers were issued by different LOCALITIES (惠府办函〔2016〕35号
    vs 江府办函〔2016〕52号 — Huizhou's and Jiangmen's own 应急管理工作计划, five days
    apart): one locality's document is never a copy of another's, whatever the dates, so
    the date guard must not re-merge those. The guard protects against a mis-stored
    number on a mirror, and the numbers it protects (chinatax's 财库 vs 税总函) are
    central, where no locality is named."""
    dates = defaultdict(list)
    locs = defaultdict(set)
    for m in members:
        k = keys[m["id"]]
        if not k:
            continue
        if m["date"]:
            dates[k].append(m["date"])
        agency = docnum_agency(m.get("docnum"))
        loc = locality_of_head(agency) if agency else None
        if loc and not loc.startswith("<"):
            locs[k].add(loc)
    ks = [k for k in {k for k in keys.values() if k}]
    parent = {k: k for k in ks}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            la, lb = locs.get(a), locs.get(b)
            if la and lb and not (la & lb):
                continue  # different issuing localities: never one text
            da, db = dates.get(a), dates.get(b)
            if not da or not db:
                gap = 0  # no date evidence either side -> not separable
            else:
                gap = max(min(da) - max(db), min(db) - max(da)).days
            if gap <= DOCNUM_SPLIT_MIN_DAYS:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra
    return {did: (find(k) if k else None) for did, k in keys.items()}


def split_by_docnum(members):
    """R1: -> list of member lists, one per distinct own-文号, or [members] when the
    group carries fewer than two distinct numbers.

    Applied INSIDE an edition, never across editions: the edition walk is what encodes
    revisions (政府信息公开条例 2008 vs 2019) and it already keeps an un-numbered late
    repost with its own edition — partitioning the whole key group first would strand
    those reposts (the fj_wjw 2014 and bjb_tjj 2024 copies of 政府信息公开条例 are more
    than EDITION_GAP_DAYS from any numbered copy and became a third instrument). The
    annual recurrence this rule exists for is a WITHIN-edition pile, by construction:
    one year's gap is under EDITION_GAP_DAYS."""
    keys = {}
    for m in members:
        keys[m["id"]] = own_docnum_key(m)
    canon = _canon_docnum_keys([k for k in keys.values() if k])
    for m in members:  # fold the year-less variants onto their year-ful twin
        if keys[m["id"]]:
            keys[m["id"]] = canon[keys[m["id"]]]
    keys = _merge_close_keys(members, keys)
    distinct = {k for k in keys.values() if k}
    if len(distinct) < 2:
        return [members]
    parts = defaultdict(list)
    unnumbered = []
    for m in members:
        k = keys[m["id"]]
        (parts[k] if k else unnumbered).append(m)
    numbered = list(parts.items())  # snapshot: the leftover bucket is added below
    plocs = {k: {loc for loc in (_docnum_locality(o) for o in ms) if loc} for k, ms in numbered}
    for m in unnumbered:
        best, dist = None, None
        mloc = _own_locality(m)
        if m["date"]:
            for k, ms in numbered:
                # same locality rule as the date guard: a Chongqing copy is not a
                # repost of 江苏's numbered text however close the dates are
                if mloc and plocs[k] and mloc not in plocs[k]:
                    continue
                for o in ms:
                    if not o["date"]:
                        continue
                    g = abs((m["date"] - o["date"]).days)
                    if dist is None or g < dist:
                        best, dist = k, g
        if best is not None and dist <= EDITION_GAP_DAYS:
            parts[best].append(m)
        else:
            parts[("_none",)].append(m)
    return list(parts.values())


def _hosted_below_text(d):
    """1 when this copy sits on a site BELOW the level of the text it carries — i.e. it
    is a REPOST, not the issuing institution's own publication.

    (2026-10-07) The canonical tie-break used to fall straight through to the earliest
    date, and `level` is the level of the TEXT (a 中华人民共和国民法典 repost on a 福建省
    信访局 site derives `central` from its own title cue), so for the whole class of
    nationally-mirrored instruments the level tier is CONSTANT and the date decided
    alone — handing the canonical slot to whichever copy carried the earliest date,
    bad dates included: 民法典's canonical was the fj_xfj copy stamped 2020-01-08,
    four months BEFORE the NPC adopted it on 2020-05-28.

    The hosting SITE is the discriminator, and this file already uses exactly this test
    for exactly this reason in the edition walk ("only a site at or above the edition's
    level can open a new edition; a bureau's late copy is a repost"). Measured: a raw
    site-level rank (prefer the grandest host) is worse than this boolean — it promotes
    a central PORTAL's reprint of a sub-national text over the issuer's own copy (an
    empty-bodied miit copy of 福建省通信管理局's report; the npc reprint of a 深圳经济特区
    条例 over the sz_gazette original). Asking only "is this copy hosted below its own
    text's level" leaves those alone and still fixes 77 of the 88 pools whose canonical
    is a repost while a non-repost copy exists."""
    return 1 if LEVEL_RANK.get(d["site_level"], 5) > LEVEL_RANK.get(d["level"], 5) else 0


def _canon_sort_key(d):
    """promulgation genre > highest doc level > hosted at-or-above the text's own level
    (a repost loses to the issuer's own copy, _hosted_below_text) > earliest date (among
    equally authoritative copies the first publication is the original; reposts come
    later) > lowest id.

    Date PLAUSIBILITY is deliberately NOT a tier. The candidate test — a copy dated
    before Jan 1 of its own 文号's year — fires on 5 pools corpus-wide and is wrong on 3
    of them, because the `document_number` field is not reliably the document's own
    (chinatax stores the SUPERSEDING instrument's 文号: 财税〔2009〕17号 on the 2007 text),
    so the gate demotes copies whose date is right. Where a date is genuinely wrong on
    the authoritative copy that is a `date_quality` fact about that copy, not a reason to
    let a subordinate repost represent the instrument — level/host wins over plausibility,
    and _POOL_TESTS encodes that choice."""
    return (0 if d["genre"] == "promulgation" else 1, LEVEL_RANK.get(d["level"], 5),
            _hosted_below_text(d), d["date"] or date.max, d["id"])


def assign_instruments(docs):
    """Set instrument_id / instrument_role on every doc dict (in place)."""
    # Pass 1: group by (class, stem) to find LOCALIZED re-issuances — a doc naming a
    # sub-national locality whose stem also appears on a higher-level member. Those
    # pool under (class, stem, locality); everything else keeps the plain core key.
    stems = defaultdict(list)
    for d in docs.values():
        d["instrument_id"], d["instrument_role"] = d["id"], "unique"
        d["localized"], d["localized_of"], d["_broad_trigger"] = False, None, None
        d["_chain_trigger"] = None  # the in-chain pick BEFORE the date rule (dry-run audit)
        cls = POOL_CLASS.get(d["genre"])
        if not cls:
            continue
        k = instrument_key(d["title"])
        if not k:
            continue
        stem, loc, rank = localize(d["title"], d["site"])
        d["_key"], d["_stem"], d["_loc"] = k, stem, loc
        d["_rank"] = rank if loc else LEVEL_RANK.get(d["level"], 5)
        stems[(cls, stem)].append(d)
    groups = defaultdict(list)
    n_localized = n_flipped = n_flipped_broad = n_unknown_loc = 0
    n_flipped_chain = 0
    for (cls, stem), members in stems.items():
        if len(members) > 1:
            generic = bool(GENERIC_STEM_RE.search(stem))
            for m in members:
                if not m["_loc"]:
                    continue
                higher = [o for o in members if o["_rank"] < m["_rank"] and o["_loc"] != m["_loc"]]
                if not higher:
                    continue
                # pooling isolation: ANY higher same-stem member keeps this doc out of
                # the higher text's pool (a 苏州 条例 must not become a 天津 mirror either)
                m["localized"] = True
                n_localized += 1
                if not (m["genre"] == "promulgation" and m["level"] in SUBNATIONAL):
                    continue
                # genre flip: only an IN-CHAIN parent (qa-genre-flip.md option D + denylist)
                higher.sort(key=lambda o: (o["_rank"], o["date"] or date.max, o["id"]))
                m["_broad_trigger"] = higher[0]["id"]  # what the pre-QA rule would have used
                n_flipped_broad += 1
                if generic:
                    continue
                if jurisdiction_chain(m["_loc"]) is None:
                    n_unknown_loc += 1  # unknown / unqualified locality: cannot place it, no flip
                    continue
                chain_trig = next((o for o in higher if in_chain(m, o)), None)
                if chain_trig is None:
                    continue
                m["_chain_trigger"] = chain_trig["id"]  # the 2026-10-06 rule's pick
                n_flipped_chain += 1
                trig = pick_trigger(m, higher)  # date-ordered, nearest parent
                if trig is None:
                    continue
                m["genre"] = "implementing"
                m["localized_of"] = trig["id"]
                n_flipped += 1
        for m in members:
            key = (cls, stem, m["_loc"]) if m["localized"] else (cls, m["_key"])
            groups[key].append(m)
    stats = {"n_localized": n_localized, "n_flipped": n_flipped,
             "n_flipped_broad": n_flipped_broad, "n_unknown_loc": n_unknown_loc,
             "n_flipped_chain": n_flipped_chain}
    n_pooled = 0
    n_series = n_docnum_split = n_subpools = 0
    for members in groups.values():
        if len(members) < 2 or len({m["site"] for m in members}) < 2:
            continue
        dated = sorted((m for m in members if m["date"]), key=lambda m: m["date"])
        undated = [m for m in members if not m["date"]]
        # The edition gap is measured from the edition's ANCHOR — its latest copy hosted
        # at or above the edition's own level — not from its latest copy of any kind.
        # (2026-10-07) Measuring from the latest copy let a LOW-level late repost BRIDGE a
        # revision: 中华人民共和国监察法 2018 + a 北京市统计局 repost of 2024-05-27 put the
        # npc 2024-12-25 revision only 212 days after the running tail, so the amended text
        # was pooled into the 2018 instrument (同 统计法 2009/2024, 对外贸易法 2022/2025).
        # A bureau's repost cannot open an edition (below), so it must not extend one either.
        editions, cur, anchor = [], None, None
        for m in dated:
            if cur is None:
                cur, anchor = [m], m["date"]
                editions.append(cur)
                continue
            # a repost carries the TEXT's level (title cue 中华人民共和国… -> central),
            # so test the hosting SITE: only a site at or above the edition's level
            # can open a new edition; a bureau's late copy is a repost.
            canon_rank = min(LEVEL_RANK.get(x["level"], 5) for x in cur)
            authoritative = LEVEL_RANK.get(m["site_level"], 5) <= canon_rank
            if (m["date"] - anchor).days > EDITION_GAP_DAYS and authoritative:
                cur, anchor = [m], m["date"]
                editions.append(cur)
                continue
            cur.append(m)
            if authoritative:
                anchor = m["date"]  # an at-or-above-level copy re-anchors the edition
        if len(editions) == 1 and undated:
            editions[0].extend(undated)
        for ed in editions:
            # R1 inside the edition: an annual re-issuance piles into ONE edition
            # (a year's gap is under EDITION_GAP_DAYS) and each year carries its own 文号.
            parts = split_by_docnum(ed) if len(ed) > 1 else [ed]
            if len(parts) > 1:
                n_docnum_split += 1
                n_subpools += len(parts)
            for part in parts:
                if len(part) < 2 or len({m["site"] for m in part}) < 2:
                    continue
                # R2 LAST, per sub-pool: a SERIES title does not name a text, so nothing
                # in it pools. After R1 so that a numbered series still pools each
                # issue's own mirrors (深公交（规）〔2024〕3号 on sz_gazette + ga is one
                # text even though the 通告 comes round every year).
                if is_series(part):
                    n_series += 1
                    continue
                canon = min(part, key=_canon_sort_key)
                for m in part:
                    m["instrument_id"] = canon["id"]
                    m["instrument_role"] = "canonical" if m is canon else "mirror"
                    n_pooled += 1
    # The nearest dated parent may be a MIRROR of the triggering text (the mee repost of
    # the SC 以旧换新 plan, 5 days after gov): persist the instrument's canonical copy when
    # it is itself date-valid. (2026-10-07) The canonical is no longer necessarily the
    # pool's earliest copy — the host tier can prefer a later, non-repost copy — so the
    # is_date_valid_trigger guard below is what keeps the swap honest, not an invariant.
    n_trigger_moved = 0
    for m in docs.values():
        if m["localized_of"] is None:
            continue
        t = docs[m["localized_of"]]
        c = docs.get(t["instrument_id"])
        if c is not None and c is not t and is_date_valid_trigger(m, c):
            m["localized_of"] = c["id"]
        if m["localized_of"] != m["_chain_trigger"]:
            n_trigger_moved += 1
    stats["n_trigger_moved"] = n_trigger_moved
    stats["n_pooled"] = n_pooled
    stats["n_series_groups"] = n_series
    stats["n_docnum_split_groups"] = n_docnum_split
    stats["n_docnum_subpools"] = n_subpools
    return stats


# --------------------------------------------------------------------------- #
# A4. date quality                                                             #
# --------------------------------------------------------------------------- #
STAMP_SHARE = 0.70
STAMP_MIN_DOCS = 100
STAMP_DATE_LO = date(2008, 1, 1)
STAMP_MIN_BULK = 20
# (2026-10-06) The stamp is measured on the site's BULK crawl day, not on the year share.
# The memo rule (>=70% of dated docs in the crawl year) was a proxy for "the crawler wrote
# today's date"; measured against the raw HTML it turned out to flag SHALLOW RECENT crawls
# instead: the Jul-Sep 2026 province/dept/district tier was first crawled ~30 list pages
# deep, so most of its REAL dates fall in 2026 (js_mzt 319/417 equal the page's own
# <meta PubDate>; jcgov/jilin/fujian URL t-dates equal the stored date for 95-100% of docs;
# no crawler in crawlers/ writes today() into date_published). A whole-site "date == crawl
# day" share is fooled the same way — a live site synced daily dates most of its NEW docs on
# their crawl day (liaoning 89%, jcgov 86%, both real). What cannot happen on a real site is
# the first bulk pull of an archive coming back dated on the pull day: that is the stamp. So
# a site is crawl_stamped iff, on its modal crawl day (>= STAMP_MIN_BULK docs), >= 70% of the
# docs are dated on that very day. On the 2026-10-07 corpus this fires on 0 sites (the max is
# leshan, 88% of a 17-doc day, under the floor) — the 74-site / 27.9k-doc exclusion in
# industrial-policy-targeting.md was a coverage-DEPTH artefact, not a date-quality one.
#
# (2026-10-07) SECOND test — the SOURCE's own regeneration stamp, which the crawl-day test
# cannot see. Suzhou (fidelity-jiangsu.md §7): the CMS regenerated its archive on 2023-02-09
# and 2025-02-11 and wrote that time into <meta PubDate>, so 1,860 + 1,499 = 68% of the site
# sat on two DATE days while we crawled it on 2026-03-31. Neither day was our crawl day, and
# neither batch alone reached 70%. Multi-batch rule: "bulk date-days" are days carrying
# >= STAMP_MIN_BULK docs AND >= STAMP_BULK_DAY_SHARE of the site's dated docs; the site is
# stamped when the bulk days together hold >= STAMP_MULTI_SHARE of its dated docs. Two
# calibrations from the 2026-10-07 corpus: (a) day-01 dates are EXEMPT — a YYYY-MM-01 (or
# YYYY-01-01) pile is the URL-month/year fallback that crawlers write when only the month is
# known (yc/abazhou/ganzhou/kashi 77-80% on 2026-09-01, laiwu 95% on 2026-01-01: month-
# precision, real month, shallow one-month crawls — not stamps); (b) a single real heavy
# publication day does not reach 50%: gov 2,308 docs on 2018-12-31 = 11.5%, samr 1,841 on
# 2024-05-07 = 42%, mot 429 on 2025-12-26 = 32%, moe 81 on 2008-04-25 = 24% all stay `good`.
STAMP_BULK_DAY_SHARE = 0.10
STAMP_MULTI_SHARE = 0.50


def crawl_stamped_sites(docs, site_level, crawl_year):
    """{site: (n_dated_2008plus, n_bulk, n_stamped)} for sites whose dates are stamps. Two
    tests, either fires: (1) crawl-day — >=70% of the docs pulled on the site's busiest
    (modal) crawl day (>=20 docs) are dated ON that day (an archive pull cannot be);
    (2) multi-batch date-day — the docs sitting on bulk DATE days (>=20 docs and >=10% of the
    site's dated docs each, day != 1) together make >=50% of the site's dated docs. Both need
    >=100 dated docs. For (2) the tuple is (n, n_on_bulk_days, n_on_bulk_days)."""
    per_site = defaultdict(lambda: [0, Counter(), Counter(), Counter()])  # n, crawl-day, stamped, date-day
    for d in docs.values():
        if site_level.get(d["site"]) in NON_ISSUER_SITE_LEVELS:
            continue
        dt = d["date"]
        if not dt or dt < STAMP_DATE_LO or dt.year > crawl_year:
            continue
        c = per_site[d["site"]]
        c[0] += 1
        if dt.day != 1:
            c[3][dt] += 1
        cd = d.get("crawl_date")
        if cd:
            c[1][cd] += 1
            if cd == dt:
                c[2][cd] += 1
    out = {}
    for s, (n, days, eq, by_date) in per_site.items():
        if n < STAMP_MIN_DOCS:
            continue
        if days:  # (1) single crawl-day test
            bulk_day, nb = max(days.items(), key=lambda kv: (kv[1], kv[0]))
            e = eq.get(bulk_day, 0)
            if nb >= STAMP_MIN_BULK and e / nb >= STAMP_SHARE:
                out[s] = (n, nb, e)
                continue
        # (2) multi-batch date-day test
        bulk = sum(k for k in by_date.values()
                   if k >= STAMP_MIN_BULK and k / n >= STAMP_BULK_DAY_SHARE)
        if bulk and bulk / n >= STAMP_MULTI_SHARE:
            out[s] = (n, bulk, bulk)
    return out


# --------------------------------------------------------------------------- #
# Load + build                                                                 #
# --------------------------------------------------------------------------- #
def connect(db_path, ro=False):
    uri = f"file:{db_path}?mode=ro" if ro else str(db_path)
    conn = sqlite3.connect(uri, uri=ro, timeout=30, isolation_level=None)  # manual txn
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def load(conn):
    site_level = {k: (v or "unknown") for k, v in conn.execute(
        "SELECT site_key, admin_level FROM sites")}
    lead = dict(conn.execute(
        "SELECT doc_id, lead_issuer FROM doc_issuers WHERE lead_issuer IS NOT NULL"))
    docs = {}
    cur = conn.execute(
        """SELECT id, site_key, title, document_number, publisher, date_published,
                  crawl_timestamp, algo_doc_type, classify_main_name
           FROM documents""")
    crawl_years = Counter()
    for (did, sk, title, dn, pub, dp, ct, at, cat) in cur:
        docs[did] = {
            "id": did, "site": sk or "", "title": title or "", "docnum": dn or "",
            "publisher": pub or "", "date": _to_date(dp or ""), "has_date": bool(dp),
            "algo": at or "", "cat": cat or "",
            "crawl_date": _to_date(ct[:10]) if ct else None,
        }
        if ct:
            crawl_years[ct[:4]] += 1
    crawl_year = int(crawl_years.most_common(1)[0][0]) if crawl_years else date.today().year
    return docs, site_level, lead, crawl_year


def build(conn):
    t0 = time.time()
    docs, site_level, lead, crawl_year = load(conn)
    t_load = time.time() - t0
    for d in docs.values():
        sl = site_level.get(d["site"], "unknown")
        li = lead.get(d["id"])
        d["lead_issuer"] = li
        d["level"], d["level_source"] = derive_level(d, sl, li)
        d["genre"] = derive_genre(d["title"], d["algo"], d["level"])
        d["instrument_kind"] = derive_instrument_kind(d["title"], d["algo"])
        d["site_level"] = sl
    inst = assign_instruments(docs)
    stamped = crawl_stamped_sites(docs, site_level, crawl_year)
    for d in docs.values():
        d["province"] = derive_province(d, d["lead_issuer"]) if d["level"] in SUBNATIONAL else None
        if not d["has_date"]:
            d["date_quality"] = "missing"
        elif d["site"] in stamped:
            d["date_quality"] = "crawl_stamped"
        else:
            d["date_quality"] = "good"
    meta = {"t_load": t_load, "t_total": time.time() - t0, "stamped": stamped,
            "crawl_year": crawl_year, **inst}
    return docs, meta


DDL = """
DROP TABLE IF EXISTS doc_identity;
CREATE TABLE doc_identity (
    doc_id INTEGER PRIMARY KEY,
    admin_level_doc TEXT,
    level_source TEXT,
    instrument_id INTEGER,
    instrument_role TEXT,
    genre TEXT,
    date_quality TEXT,
    lead_issuer TEXT,
    localized_of INTEGER,
    province TEXT,
    instrument_kind TEXT
);
CREATE INDEX IF NOT EXISTS idx_doc_identity_level ON doc_identity(admin_level_doc);
CREATE INDEX IF NOT EXISTS idx_doc_identity_instrument ON doc_identity(instrument_id);
CREATE INDEX IF NOT EXISTS idx_doc_identity_genre ON doc_identity(genre);
"""


def write(conn, docs):
    t0 = time.time()
    rows = [(d["id"], d["level"], d["level_source"], d["instrument_id"], d["instrument_role"],
             d["genre"], d["date_quality"], d["lead_issuer"], d["localized_of"], d["province"],
             d["instrument_kind"])
            for d in docs.values()]
    conn.execute("BEGIN IMMEDIATE")
    try:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                conn.execute(stmt)
        conn.executemany("INSERT INTO doc_identity VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return len(rows), time.time() - t0


def print_stats(docs, meta, site_level):
    n = len(docs)
    print(f"\ndocs: {n:,}   load {meta['t_load']:.1f}s   compute {meta['t_total']:.1f}s"
          f"   crawl year {meta['crawl_year']}")
    for field in ("level", "level_source", "genre", "instrument_kind", "instrument_role", "date_quality"):
        c = Counter(d[field] for d in docs.values())
        print(f"\n{field}:")
        for k, v in c.most_common():
            print(f"  {str(k):14s} {v:8,}  {v / n * 100:5.1f}%")
    changed = sum(1 for d in docs.values() if d["level"] != d["site_level"])
    print(f"\nlevel != site level: {changed:,} ({changed / n * 100:.1f}%)")
    xt = Counter((d["site_level"], d["level"]) for d in docs.values() if d["level"] != d["site_level"])
    for (a, b), v in xt.most_common(12):
        print(f"  {a:11s} -> {b:11s} {v:7,}")
    n_inst = len({d["instrument_id"] for d in docs.values()})
    print(f"\ninstruments: {n_inst:,} for {n:,} docs ({meta['n_pooled']:,} docs in pools; "
          f"{meta['n_localized']:,} localized re-issuances kept out of higher-level pools)")
    print(f"recurring-instrument split: {meta['n_series_groups']:,} key groups are SERIES "
          f"(an all-`other` title one site re-issues) and pool with nothing; "
          f"{meta['n_docnum_split_groups']:,} split by distinct 文号 into "
          f"{meta['n_docnum_subpools']:,} sub-pools")
    print(f"genre flips promulgation->implementing: {meta['n_flipped']:,} in-chain + date-ordered "
          f"(in-chain alone {meta['n_flipped_chain']:,}; broad any-higher rule {meta['n_flipped_broad']:,}; "
          f"{meta['n_unknown_loc']:,} skipped for an unknown locality; "
          f"{meta['n_trigger_moved']:,} triggers moved to the nearest dated parent)")
    sub = [d for d in docs.values() if d["level"] in SUBNATIONAL]
    n_prov = sum(1 for d in sub if d["province"])
    print(f"province (A6): {n_prov:,} of {len(sub):,} sub-national docs resolved "
          f"({n_prov / max(len(sub), 1) * 100:.1f}%)")
    print(f"crawl-stamped sites: {len(meta['stamped'])}  "
          f"({sum(1 for d in docs.values() if d['date_quality'] == 'crawl_stamped'):,} docs)")


# --------------------------------------------------------------------------- #
# Validation against known truth                                               #
# --------------------------------------------------------------------------- #
def validate(docs, meta):
    print("\n=== A1 level ===")
    npc = [d for d in docs.values() if d["site"] == "npc"]
    c = Counter(d["level"] for d in npc)
    print(f"npc docs {len(npc):,}: " + ", ".join(f"{k}={v:,}" for k, v in c.most_common()))
    local = [d for d in npc if d["cat"] in ("地方法规", "修改、废止的决定（地方法规）", "法规性决定")]
    cl = Counter(d["level"] for d in local)
    print(f"npc 地方法规/local decisions {len(local):,}: "
          + ", ".join(f"{k}={v:,}" for k, v in cl.most_common()))
    bad = [d for d in local if d["level"] == "central"]
    for d in bad[:5]:
        print(f"   still central: {d['id']} {d['publisher'][:20]!r} {d['title'][:50]}")

    print("\n=== A2 instruments ===")
    xgk = [d for d in docs.values() if _norm_title(clean_title(d["title"])) == "政府信息公开条例"]
    by_inst = defaultdict(list)
    for d in xgk:
        by_inst[d["instrument_id"]].append(d)
    print(f"政府信息公开条例 bare-title copies: {len(xgk)} on {len({d['site'] for d in xgk})} sites "
          f"-> {len(by_inst)} instrument id(s)")
    for iid, ms in sorted(by_inst.items(), key=lambda kv: -len(kv[1])):
        cd = docs[iid]
        dates = sorted(m["date"].isoformat() for m in ms if m["date"])
        print(f"   instrument {iid} (canonical {cd['site']} {cd['level']} {cd['genre']}): "
              f"{len(ms)} copies, {dates[0] if dates else '-'}..{dates[-1] if dates else '-'}")
    for did in (12650974, 12704698, 900105357):
        d = docs.get(did)
        if d:
            print(f"   {did} {d['site']:7s} inst={d['instrument_id']} role={d['instrument_role']:9s} "
                  f"lvl={d['level']} genre={d['genre']} | {d['title'][:48]}")
    ok = (docs[12650974]["instrument_id"] == docs[12704698]["instrument_id"] == 12650974
          and docs[900105357]["instrument_id"] != 12650974) if all(
        k in docs for k in (12650974, 12704698, 900105357)) else None
    print(f"   提振消费 check (gov canonical, xinhua mirror, bj news out): {ok}")
    for did in (900039931, 11271152):
        d = docs.get(did)
        if d:
            print(f"   {did} {d['site']:7s} inst={d['instrument_id']} role={d['instrument_role']:9s} "
                  f"lvl={d['level']} genre={d['genre']} | {d['title'][:48]}")
    ok2 = (docs[11271152]["instrument_id"] != docs[900039931]["instrument_id"]
           and docs[11271152]["genre"] == "implementing") if all(
        k in docs for k in (900039931, 11271152)) else None
    print(f"   以旧换新 check (Shenzhen localized re-issuance is NOT a mirror of the SC text): {ok2}")
    n_inst = len({d["instrument_id"] for d in docs.values()})
    roles = Counter(d["instrument_role"] for d in docs.values())
    print(f"instruments {n_inst:,} vs docs {len(docs):,}; roles {dict(roles)}")

    print("\n=== A3 genre ===")
    print(Counter(d["genre"] for d in docs.values()).most_common())
    hlj = docs.get(12714192)
    if hlj:
        print(f"   黑龙江 AI+ 实施方案 12714192: genre={hlj['genre']} level={hlj['level']}")
    print("   AI+ mention sources (diffusion source_implementing=0):")
    for did in (3507800, 3903923, 3933421, 4771210, 12692769, 12692866, 12758859, 12913722,
                900069411, 900077629, 900082162, 900083978, 900085686, 12715715):
        d = docs.get(did)
        if d:
            print(f"     {did} {d['genre']:12s} {d['level']:10s} | {d['title'][:50]}")

    print("\n=== A4 dates ===")
    st = meta["stamped"]
    print(f"crawl-stamped sites: {len(st)}, docs: "
          f"{sum(1 for d in docs.values() if d['date_quality'] == 'crawl_stamped'):,}")
    for s, (n, nb, e) in sorted(st.items(), key=lambda kv: -kv[1][0])[:12]:
        print(f"   {s:14s} n={n:6,} bulk-day docs={nb:5,} dated-on-bulk-day={e / nb:.2f}")


def dry_run_flips(docs, meta, n=30, seed=7):
    """Broad-rule vs in-chain flip counts and a sample of FLIP-BACKS (docs the pre-QA
    rule flipped to `implementing` that now stay `promulgation`). Read-only."""
    backs = [d for d in docs.values() if d["_broad_trigger"] is not None and d["localized_of"] is None]
    print("\n=== genre flip: broad (any higher same-stem member) vs in-chain + denylist ===")
    print(f"flips before (broad rule): {meta['n_flipped_broad']:,}")
    print(f"flips after  (in-chain):   {meta['n_flipped']:,}")
    print(f"flip-backs:                {len(backs):,}  "
          f"(unknown-locality skips: {meta['n_unknown_loc']:,}; "
          f"generic-stem skips: {sum(1 for d in backs if GENERIC_STEM_RE.search(d['_stem'])):,})")
    lv = Counter(d["level"] for d in backs)
    print("flip-backs by level: " + ", ".join(f"{k}={v:,}" for k, v in lv.most_common()))
    kept = Counter(docs[d["localized_of"]]["level"] for d in docs.values() if d["localized_of"])
    print("kept flips by trigger level: " + ", ".join(f"{k}={v:,}" for k, v in kept.most_common()))
    dry_run_date_rule(docs, meta)
    dry_run_province(docs)
    rnd = random.Random(seed)
    print(f"\n--- {min(n, len(backs))} flip-backs (title | locality | trigger title) ---")
    for d in rnd.sample(backs, min(n, len(backs))):
        t = docs[d["_broad_trigger"]]
        why = "generic" if GENERIC_STEM_RE.search(d["_stem"]) else (
            "unknown-loc" if jurisdiction_chain(d["_loc"]) is None else "out-of-chain")
        print(f"{d['id']:>10} {d['level']:10s} {why:12s} {d['title'][:46]} | {d['_loc']} | "
              f"[{t['level']} {t['_loc'] or '-'} {t['date'] or 'n.d.'}] {t['title'][:46]}")
    for title in ("深圳市人民代表大会常务委员会议事规则", "苏州市客运出租汽车管理条例",
                  "揭阳市人民政府办公室关于印发揭阳市粮食安全责任考核办法的通知",
                  "宁夏回族自治区宗教事务条例"):
        hits = [d for d in docs.values() if clean_title(d["title"]) == title]
        for d in hits[:2]:
            print(f"   sanity {d['id']} genre={d['genre']:12s} localized_of={d['localized_of']} | {title}")


def dry_run_kind(docs, n=12, seed=7):
    """A7: instrument_kind by level, and the matcher's framework gate BEFORE (old
    `is_framework` on algo_doc_type + title) vs AFTER (kind == framework) on the docs
    that could anchor a cascade (central / provincial, genre not ABOUT). Read-only."""
    print("\n=== A7 instrument_kind by level ===")
    levels = [lv for lv in LEVELS if any(d["level"] == lv for d in docs.values())]
    print(f"{'level':12s} " + " ".join(f"{k:>13s}" for k in INSTRUMENT_KINDS) + f" {'docs':>9s}")
    for lv in levels:
        c = Counter(d["instrument_kind"] for d in docs.values() if d["level"] == lv)
        n_lv = sum(c.values())
        print(f"{lv:12s} " + " ".join(f"{c.get(k, 0):9,} {c.get(k, 0) / n_lv * 100:3.0f}%" for k in INSTRUMENT_KINDS)
              + f" {n_lv:9,}")
    print("\n=== framework gate: old matcher gate -> instrument_kind (anchor-eligible docs: "
          "central/provincial, genre not explainer/readout/news) ===")
    print(f"{'level':12s} {'before':>8s} {'after':>8s} {'added':>7s} {'removed':>8s} "
          f"{'insts before':>13s} {'insts after':>12s}")
    added, removed = [], []
    for lv in ("central", "provincial"):
        elig = [d for d in docs.values() if d["level"] == lv and d["genre"] not in ABOUT_GENRES]
        before = [d for d in elig if _matcher_is_framework(d["algo"], d["title"])]
        after = [d for d in elig if d["instrument_kind"] == "framework"]
        b_ids, a_ids = {d["id"] for d in before}, {d["id"] for d in after}
        added += [d for d in after if d["id"] not in b_ids]
        removed += [d for d in before if d["id"] not in a_ids]
        print(f"{lv:12s} {len(before):8,} {len(after):8,} {len(a_ids - b_ids):7,} {len(b_ids - a_ids):8,} "
              f"{len({d['instrument_id'] for d in before}):13,} {len({d['instrument_id'] for d in after}):12,}")
    rnd = random.Random(seed)
    for label, rows in (("ADDED (R1 admit)", added), ("REMOVED (memo housekeeping over the old gate)", removed)):
        print(f"\n--- {label}: {len(rows):,}; by algo_doc_type: "
              + ", ".join(f"{k}={v:,}" for k, v in Counter(d["algo"] for d in rows).most_common(6)) + " ---")
        for d in rnd.sample(rows, min(n, len(rows))):
            print(f"{d['id']:>10} {d['level']:10s} {d['algo']:15s} {d['genre']:12s} | {d['title'][:60]}")
    for did in (145311, 141804, 3166422, 2903650, 142604, 4701868, 4016742, 900042244):
        d = docs.get(did)
        if d:
            print(f"   memo #{did}: kind={d['instrument_kind']:12s} genre={d['genre']:12s} | {d['title'][:56]}")


_LAG_BINS = ((-10**9, -731, "<= -731"), (-730, -366, "-730..-366"), (-365, -181, "-365..-181"),
             (-180, -91, "-180..-91"), (-90, -61, "-90..-61"), (-60, -31, "-60..-31"),
             (-30, -8, "-30..-8"), (-7, -1, "-7..-1"), (0, 7, "0..7"), (8, 31, "8..31"),
             (32, 90, "32..90"), (91, 365, "91..365"), (366, 730, "366..730"), (731, 10**9, "> 730"))


def _lag_bin(lag):
    return next(label for lo, hi, label in _LAG_BINS if lo <= lag <= hi)


def dry_run_date_rule(docs, meta):
    """The date rule's audit: flips before/after, the lag distribution of the pre-date-rule
    edges (reversed vs forward), the slack and its evidence, and the reversed edges
    REMAINING among the persisted triggers (must be 0)."""
    print("\n=== date-ordered trigger (pair-channels.md §1) ===")
    pre = [d for d in docs.values() if d["_chain_trigger"] is not None]
    print(f"flips before the date rule (in-chain, any date): {meta['n_flipped_chain']:,}")
    print(f"flips after  the date rule (nearest dated parent): {meta['n_flipped']:,}  "
          f"(triggers moved to a nearer parent: {meta['n_trigger_moved']:,})")
    rejected = [d for d in pre if d["localized_of"] is None]
    why = Counter()
    for d in rejected:
        t = docs[d["_chain_trigger"]]
        if not d["date"]:
            why["doc undated"] += 1
        elif not t["date"]:
            why["trigger undated"] += 1
        else:
            why["all in-chain candidates dated after the doc"] += 1
    print(f"rejected: {len(rejected):,}  (" + "; ".join(f"{k}: {v:,}" for k, v in why.most_common()) + ")")

    # lag distribution of the PRE-date-rule edges, by bin
    bins = Counter()
    month = Counter()
    for d in pre:
        t = docs[d["_chain_trigger"]]
        if d["date"] and t["date"]:
            lag = (d["date"] - t["date"]).days
            b = _lag_bin(lag)
            bins[b] += 1
            if d["date"].day == 1 or t["date"].day == 1:
                month[b] += 1
    dated = sum(bins.values())
    neg = sum(v for k, v in bins.items() if k.startswith("-") or k.startswith("<"))
    print(f"\npre-date-rule edges with both dates: {dated:,}; reversed (doc before trigger): {neg:,}")
    print("  doc_date - trigger_date (days)   edges   of which a -01 (month-precision) date")
    for _, _, label in _LAG_BINS:
        if bins.get(label):
            print(f"  {label:>12}  {bins[label]:7,}  {month.get(label, 0):7,}")
    far = sum(v for k, v in bins.items() if k in ("<= -731", "-730..-366", "-365..-181"))
    near7 = bins.get("-7..-1", 0)
    near31 = near7 + bins.get("-30..-8", 0)
    near60 = near31 + bins.get("-60..-31", 0)
    fwd7 = bins.get("0..7", 0)
    print(f"\nslack chosen: {LOCALIZED_SLACK_DAYS}d, +{MONTH_SLACK_DAYS}d when either date is a -01 stamp. Why:")
    print(f"  reversed edges > 180d apart: {far:,} of {neg:,} ({far / max(neg, 1) * 100:.0f}%) — false triggers "
          f"(a later central re-issuance of a same-stem text), not re-posts;")
    print(f"  reversed within 7d: {near7:,}, within 31d: {near31:,}, within 60d: {near60:,}; forward within 7d: {fwd7:,} — "
          f"the near-zero mass is thin and symmetric (publication-order noise), there is no re-post cluster;")
    print(f"  8..60d reversed are annual-cycle siblings (city 立法工作计划 before the province's), so the slack stops at 7d.")

    # reversed edges REMAINING among the persisted triggers — must be 0 (beyond slack)
    strict = beyond = 0
    for d in docs.values():
        if d["localized_of"] is None:
            continue
        t = docs[d["localized_of"]]
        if not d["date"] or not t["date"]:
            beyond += 1  # cannot happen: an undated pair is never date-valid
            continue
        lag = (d["date"] - t["date"]).days
        if lag < 0:
            strict += 1
        if lag < trigger_lag_floor(d["date"], t["date"]):
            beyond += 1
    print(f"\nreversed edges remaining among persisted localized_of: beyond slack {beyond:,} "
          f"({'OK' if beyond == 0 else 'FAIL'}; must be 0); strictly negative within slack {strict:,}")


def dry_run_province(docs):
    """A6 coverage where it matters: sub-national docs whose SITE has no province
    (npc / miit / bjrd …), plus agreement with the site's province where both exist."""
    print("\n=== province (A6) ===")
    sub = [d for d in docs.values() if d["level"] in SUBNATIONAL]
    n_prov = sum(1 for d in sub if d["province"])
    print(f"sub-national docs: {len(sub):,}; province resolved: {n_prov:,} ({n_prov / max(len(sub), 1) * 100:.1f}%)")
    gap = [d for d in sub if not province_of(d["site"])]
    per_site = defaultdict(lambda: [0, 0])
    for d in gap:
        per_site[d["site"]][0 if d["province"] else 1] += 1
    print(f"docs on sites province_of() cannot place (the matcher's gap): {len(gap):,} on {len(per_site)} sites")
    print("  site            resolved  unresolved")
    for s, (ok, bad) in sorted(per_site.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:12]:
        print(f"  {s:14s}  {ok:8,}  {bad:10,}")
    unresolved = [d for d in gap if not d["province"]]
    pubs = Counter((d["publisher"] or d["lead_issuer"] or "-")[:24] for d in unresolved)
    print(f"  top unresolved publishers/issuers ({len(unresolved):,} docs):")
    for p, n in pubs.most_common(10):
        print(f"    {n:6,}  {p}")
    for d in unresolved[:6]:
        print(f"    e.g. {d['id']} {d['site']:8s} {d['level']:10s} src={d['level_source']:13s} "
              f"pub={d['publisher'][:14]!r} | {d['title'][:40]}")
    both = [(d["province"], province_of(d["site"])) for d in sub if d["province"] and province_of(d["site"])]
    agree = sum(1 for a, b in both if a == b)
    print(f"agreement with the site's province where both exist: {agree:,}/{len(both):,} "
          f"({agree / max(len(both), 1) * 100:.1f}%)")
    dis = Counter((d["site"], d["province"]) for d in sub
                  if d["province"] and province_of(d["site"]) and d["province"] != province_of(d["site"]))
    for (s, p), n in dis.most_common(8):
        ex = next(d for d in sub if d["site"] == s and d["province"] == p)
        print(f"  {s:12s} site={province_of(s)} doc={p} {n:5,}  e.g. {(ex['lead_issuer'] or ex['publisher'] or '-')[:16]} | {ex['title'][:36]}")


def sample(docs, n, seed, field):
    """Stratified hand-check dump: n docs spread evenly over the field's values."""
    rnd = random.Random(seed)
    by = defaultdict(list)
    for d in docs.values():
        by[d[field]].append(d)
    keys = sorted(by)
    per = max(1, n // len(keys))
    out = []
    for k in keys:
        out.extend(rnd.sample(by[k], min(per, len(by[k]))))
    print(f"\n--- hand-check sample: {len(out)} docs stratified by {field} ---")
    for d in out[:n]:
        print(f"{d['id']:>10} site={d['site']:12s} site_lvl={d['site_level']:10s} "
              f"{field}={d[field]:12s} src={d['level_source']:13s} algo={d['algo']:14s} "
              f"issuer={(d['lead_issuer'] or '-')[:16]:16s} | {d['title'][:70]}")


# --------------------------------------------------------------------------- #
# Self test                                                                    #
# --------------------------------------------------------------------------- #
_LEVEL_TESTS = [
    ("国务院", "central"), ("工业和信息化部", "central"), ("市场监管总局", "central"),
    ("国家税务总局广东省税务局", None),  # vertical bureau in a province: ambiguous, fall through
    ("广东省人民政府", "provincial"), ("江苏省人民代表大会常务委员会", "provincial"),
    ("内蒙古自治区人民代表大会常务委员会", "provincial"), ("上海市人民政府办公厅", "provincial"),
    ("重庆市人民政府", "provincial"), ("广东省工业和信息化厅", "provincial"),
    ("深圳市人民政府", "municipal"), ("深圳市公安局交通警察局", "municipal"),
    ("苏州市人民政府", "municipal"), ("延边朝鲜族自治州人民政府", "municipal"),
    ("深圳市大鹏新区管理委员会", "district"), ("深圳市龙华区人民政府", "district"),
    ("北京经济技术开发区管理委员会", "district"), ("坪山区人民政府", "district"),
    ("市人民政府办公室", "municipal"), ("省政府办公厅", "provincial"), ("区委办", "district"),
    ("中国人民银行广州分行", None),
]
_TITLE_LEVEL_TESTS = [
    ("中华人民共和国政府信息公开条例", "central"),
    ("国务院办公厅关于做好施行《中华人民共和国政府信息公开条例》准备工作的通知", "central"),
    ("中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", "central"),
    ("广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知", "provincial"),
    ("转发省政府办公厅关于做好施行《中华人民共和国政府信息公开条例》准备工作的通知", None),
    ("深圳市龙华区人民政府办公室关于印发龙华区X办法的通知", "district"),
    ("北京发布《深化改革提振消费专项行动方案》", None),
    ("保障防控前提下租房需求 经纪人进社区 人数次数设限制", None),
    ("江苏省环境保护条例", "provincial"),
]
_GENRE_TESTS = [
    ("中华人民共和国政府信息公开条例", "regulation", "central", "promulgation"),
    ("受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", "action_plan", "media", "promulgation"),
    ("北京发布《深化改革提振消费专项行动方案》", "action_plan", "provincial", "news"),
    ("黑龙江省人民政府关于印发《黑龙江省深入实施“人工智能+”行动的实施方案》的通知", "notice", "provincial", "implementing"),
    ("国务院关于深入实施“人工智能+”行动的意见", "opinion", "central", "promulgation"),
    ("【文字解读】《黑龙江省深入实施“人工智能+”行动的实施方案》政策解读", "explainer", "provincial", "explainer"),
    ("保障人民群众依法获取政府信息——政府信息公开条例解读", "explainer", "provincial", "explainer"),
    ("吴泽桐主持召开市政府党组会议 部署人工智能高质量发展工作", "other", "municipal", "readout"),
    ("陈杰吴晓晖到台山市调研督导“百千万工程”推进情况", "other", "municipal", "readout"),
    ("习近平出席2026世界人工智能大会暨人工智能全球治理高级别会议开幕式并发表主旨讲话", "other", "provincial", "readout"),
    ("事关新型政策性金融工具、人工智能发展等，国家发改委最新回应→", "other", "municipal", "news"),
    ("《关于深入实施“人工智能+”行动的意见》引发深圳企业家热烈反响", "other", "municipal", "news"),
    ("转发省政府办公厅关于做好施行《中华人民共和国政府信息公开条例》准备工作的通知", "notice", "municipal", "implementing"),
    ("国务院办公厅转发国家发展改革委关于X实施方案的通知", "notice", "central", "promulgation"),
    ("司法鉴定管理服务项目中标结果公示", "procurement", "municipal", "other"),
    ("2023年深圳市社会保险基金管理局龙岗分局部门决算", "budget", "district", "other"),
    ("关于召开全市安全生产工作会议的通知", "notice", "municipal", "promulgation"),
    ("市委常委会召开会议", "other", "municipal", "readout"),
    ("西藏自治区实施《中华人民共和国草原法》办法", "regulation", "provincial", "implementing"),
    ("新疆维吾尔自治区人民代表大会常务委员会议事规则", "regulation", "provincial", "promulgation"),
    ("积极推进皖港澳法治协同发展，安徽出台律所合伙联营实施办法", "regulation", "media", "news"),
    ("揭阳市人民政府关于庄湃澍等同志任职的通知", "personnel", "municipal", "other"),
    ("Organic Law of the Peoples Courts of the P R C 2018 Revision", "other", "research", "other"),
    ("市北部水源工程管理处举办“一把手”谈安全生产活动", "other", "municipal", "readout"),
    ("国家税务总局关于契税纳税申报有关问题的公告", "application_guide", "central", "promulgation"),
    ("深圳市民政局关于查处非法社会组织的公告", "announcement", "municipal", "other"),
    ("深圳市应急管理局关于向社会公开征求《救灾物资储备标准指引（公开征求意见稿）》意见的通告", "consultation", "municipal", "other"),
]
# derive_instrument_kind(title, algo_doc_type) — the memo's appendix shapes (A7).
_KIND_TESTS = [
    # R1 admit: issuance wrapper + 预案 / 措施 / 要点 / 重点任务 / 方案 core
    ("广东省人民政府关于印发《广东省突发事件总体应急预案》的通知", "notice", "framework"),
    ("广东省人民政府印发关于进一步促进科技创新若干政策措施的通知", "notice", "framework"),  # verb before 关于
    ("广东省人民政府办公厅关于印发广东省“数字政府”改革建设2024年工作要点的通知", "policy_issuance", "framework"),
    ("国务院办公厅关于印发深化医药卫生体制改革2016年重点工作任务的通知", "policy_issuance", "framework"),
    ("广东省人民政府关于印发广东省“三线一单”生态环境分区管控方案的通知", "policy_issuance", "framework"),
    # statutes and the old gate still pass
    ("中华人民共和国政府信息公开条例", "regulation", "framework"),
    ("中华人民共和国数据安全法", "law", "framework"),
    ("国务院关于深入实施“人工智能+”行动的意见", "opinion", "framework"),
    # housekeeping: the memo's exclusions
    ("广东省人民政府关于印发《广东省人民政府党组党的群众路线教育实践活动整改方案》的通知", "policy_issuance", "housekeeping"),
    ("揭阳市人民政府办公室关于印发揭阳市粮食安全责任考核办法的通知", "regulation", "housekeeping"),  # 考核 beats 办法 (A7 decision)
    ("广东省人民政府办公厅关于印发《广东省人民政府2025年度立法工作计划》的通知", "plan", "housekeeping"),
    ("广东省人民政府办公厅关于印发广东省人民政府2019年制定规章计划的通知", "policy_issuance", "housekeeping"),
    ("关于公布2024年省级示范企业名单的通知", "notice", "housekeeping"),
    ("广东省科学技术厅关于组织申报2024年度广东省重点领域研发计划“海洋科技”重大专项旗舰项目的通知", "notice", "housekeeping"),
    ("国务院关于发布政府核准的投资项目目录（2014年本）的通知", "notice", "housekeeping"),
    ("广东省人民政府办公厅关于印发《广东省社会保险监督委员会章程（试行）》的通知", "policy_issuance", "housekeeping"),
    ("政府信息公开指南", "other", "housekeeping"),
    ("工业和信息化部办公厅关于开展2026年科技型企业孵化器申报工作的通知", "notice", "housekeeping"),
    ("全国信息技术标准化技术委员会教育技术分技术委员会（CETSC）章程", "other", "housekeeping"),
    # the old gate is kept: typed instruments stay framework even with a housekeeping-looking word
    ("国务院关于经营者集中申报标准的规定", "regulation", "framework"),  # 申报 as subject, not a call
    ("青海省人民代表大会议事规则", "regulation", "framework"),  # typed regulation -> rule 3 keeps it
    # other: bare 通知 with no printed core (mixed class, left undecided), bare 预案 (no wrapper)
    ("广东省人民政府办公厅关于做好优化建设工程防雷许可有关工作的通知", "notice", "other"),
    ("中共中央办公厅 国务院办公厅印发《关于做好2022年元旦春节期间有关工作的通知》", "policy_issuance", "other"),
    ("《广东省地震应急预案》", "other", "other"),
]
_KEY_TESTS = [
    ("中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》",
     "受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", True),
    ("中华人民共和国政府信息公开条例", "《中华人民共和国政府信息公开条例》全文", True),
    ("中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》",
     "北京发布《深化改革提振消费专项行动方案》", False),
    ("广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知",
     "广东省推动消费品以旧换新行动方案", True),
    # (2026-10-07) a national law folds SHORT (城乡规划法, 5 chars) — it must still key,
    # and the bare / bracketed / 全文 forms must key together
    ("中华人民共和国城乡规划法", "《中华人民共和国城乡规划法》", True),
    ("中华人民共和国城乡规划法", "中华人民共和国城市规划法", False),
    # a BARE 5-char title clears no floor on either measure and still gets no key: the
    # exemption is about the 中华人民共和国 fold, not about shortening the floor itself
    ("中华人民共和国城乡规划法", "城乡规划法", False),
]
# instrument_key on short-folding titles: the unfolded-length exemption admits statute
# NAMES only, so a 令 / 声明 vehicle title (shared by dozens of unrelated texts) still
# gets no key and can never pool.
_SHORT_KEY_TESTS = [
    ("中华人民共和国城乡规划法", "城乡规划法"),
    ("中华人民共和国民法典", "民法典"),
    ("中华人民共和国宪法", "宪法"),
    ("中华人民共和国刑法修正案", "刑法修正案"),
    ("中华人民共和国电信条例", "电信条例"),
    ("中华人民共和国国务院令", None),   # the vehicle, not a name: 20 unrelated texts
    ("中华人民共和国财政部令", None),
    ("中华人民共和国外交部声明", None),
    ("停水通知", None),                 # the floor's original purpose
    ("全文", None),
]
# localize(title, site) -> (stem, locality): the stem a central text and its local
# re-issuance share, and the sub-national name the title carries (None = bare copy).
_LOCALIZE_TESTS = [
    ("国务院关于印发《推动大规模设备更新和消费品以旧换新行动方案》的通知", "gov",
     "推动大规模设备更新和消费品以旧换新行动方案", None),
    ("深圳市人民政府关于印发推动大规模设备更新和消费品以旧换新行动方案的通知", "sz",
     "推动大规模设备更新和消费品以旧换新行动方案", "深圳市"),
    ("深圳市人民政府办公厅关于印发深圳市推动大规模设备更新和消费品以旧换新行动方案的通知", "sz",
     "推动大规模设备更新和消费品以旧换新行动方案", "深圳市"),
    ("受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", "xinhua",
     "提振消费专项行动方案", None),
    ("广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知", "gd",
     "推动消费品以旧换新行动方案", "广东省"),
    ("深圳市龙华区人民政府办公室关于印发龙华区政务公开办法的通知", "lh",
     "政务公开办法", "深圳市龙华区"),
    ("智慧城市建设行动方案", "sz", "智慧城市建设行动方案", None),  # not a locality
    ("市人民政府办公室关于印发市级储备粮管理办法的通知", "huizhou",
     "市级储备粮管理办法", "<municipal>@huizhou"),
]
# assign_instruments on synthetic pools: (docs, {id: (expected instrument_id, role, genre)})
_D = date
_POOL_TESTS = [
    # the live case: Shenzhen's own 以旧换新 plan shares the SC core but is NOT a mirror;
    # the gov + mee copies still pool.
    ([dict(id=900039931, site="gov", level="central", site_level="central", genre="promulgation",
           date=_D(2024, 3, 13), title="国务院关于印发《推动大规模设备更新和消费品以旧换新行动方案》的通知"),
      dict(id=12684861, site="mee", level="central", site_level="central", genre="promulgation",
           date=_D(2024, 3, 18), title="国务院关于印发《推动大规模设备更新和消费品以旧换新行动方案》的通知"),
      dict(id=11271152, site="sz", level="municipal", site_level="municipal", genre="promulgation",
           date=_D(2024, 5, 1), title="深圳市人民政府关于印发推动大规模设备更新和消费品以旧换新行动方案的通知")],
     {900039931: (900039931, "canonical", "promulgation"), 12684861: (900039931, "mirror", "promulgation"),
      11271152: (11271152, "unique", "implementing")}),
    # the xinhua 受权发布 copy is still a mirror of the gov text
    ([dict(id=12650974, site="gov", level="central", site_level="central", genre="promulgation",
           date=_D(2025, 3, 16), title="中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》"),
      dict(id=12704698, site="xinhua", level="media", site_level="media", genre="promulgation",
           date=_D(2025, 3, 16), title="受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》")],
     {12650974: (12650974, "canonical", "promulgation"), 12704698: (12650974, "mirror", "promulgation")}),
    # a province's localized re-issuance + its bare copy on a dept site form their OWN
    # local pool (canonical = the notice), apart from the central text
    ([dict(id=1, site="gov", level="central", site_level="central", genre="promulgation",
           date=_D(2024, 3, 13), title="国务院关于印发《推动消费品以旧换新行动方案》的通知"),
      dict(id=2, site="gd", level="provincial", site_level="provincial", genre="promulgation",
           date=_D(2024, 4, 20), title="广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知"),
      dict(id=3, site="swj", level="provincial", site_level="provincial", genre="promulgation",
           date=_D(2024, 4, 25), title="广东省推动消费品以旧换新行动方案")],
     {1: (1, "unique", "promulgation"), 2: (2, "canonical", "implementing"), 3: (2, "mirror", "implementing")}),
    # with NO higher-level text, a local notice and its bare copy pool exactly as before
    ([dict(id=2, site="gd", level="provincial", site_level="provincial", genre="promulgation",
           date=_D(2024, 4, 20), title="广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知"),
      dict(id=3, site="swj", level="provincial", site_level="provincial", genre="promulgation",
           date=_D(2024, 4, 25), title="广东省推动消费品以旧换新行动方案")],
     {2: (2, "canonical", "promulgation"), 3: (2, "mirror", "promulgation")}),
    # --- qa-genre-flip.md cases: the flip needs an IN-CHAIN parent + a non-generic stem ---
    # denylist: every 人大 writes its own 议事规则 — a 福建省 copy is not Shenzhen's parent
    ([dict(id=10, site="npc", level="provincial", site_level="central", genre="promulgation",
           date=_D(2005, 1, 1), title="福建省人民代表大会常务委员会议事规则"),
      dict(id=11, site="sz", level="municipal", site_level="municipal", genre="promulgation",
           date=_D(2019, 1, 1), title="深圳市人民代表大会常务委员会议事规则")],
     {10: (10, "unique", "promulgation"), 11: (11, "unique", "promulgation")}),
    # out of chain: a 贵州省 条例 is not 茂名市's superior -> stays promulgation
    ([dict(id=20, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2017, 1, 1), title="贵州省文明行为促进条例"),
      dict(id=21, site="npc", site_level="central", level="municipal", genre="promulgation",
           date=_D(2022, 1, 1), title="茂名市文明行为促进条例")],
     {20: (20, "unique", "promulgation"), 21: (21, "unique", "promulgation")}),
    # in chain: 广东省 IS 广州市's province -> implementing, localized_of = the GD text
    ([dict(id=30, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2017, 1, 1), title="广东省文明行为促进条例"),
      dict(id=31, site="npc", site_level="central", level="municipal", genre="promulgation",
           date=_D(2022, 1, 1), title="广州市文明行为促进条例")],
     {30: (30, "unique", "promulgation"), 31: (31, "unique", "implementing")}),
    # central in chain for a province: 宁夏 宗教事务条例 under the State Council 条例
    # (memo case 1); 西藏 实施《草原法》办法 is typed implementing by IMPL_RE upstream
    # (see _GENRE_TESTS) and the pool pass leaves it so (no shared stem, no trigger)
    ([dict(id=40, site="gov", site_level="central", level="central", genre="promulgation",
           date=_D(2008, 1, 1), title="宗教事务条例"),
      dict(id=41, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2023, 1, 1), title="宁夏回族自治区宗教事务条例"),
      dict(id=42, site="npc", site_level="central", level="central", genre="promulgation",
           date=_D(2013, 1, 1), title="中华人民共和国草原法"),
      dict(id=43, site="npc", site_level="central", level="provincial",
           genre=derive_genre("西藏自治区实施《中华人民共和国草原法》办法", "regulation", "provincial"),
           date=_D(2020, 1, 1), title="西藏自治区实施《中华人民共和国草原法》办法")],
     {40: (40, "unique", "promulgation"), 41: (41, "unique", "implementing"),
      42: (42, "unique", "promulgation"), 43: (43, "unique", "implementing")}),
    # district: own city is in chain (大鹏新区 <- 深圳市); an unrelated province is not
    ([dict(id=50, site="sz", site_level="municipal", level="municipal", genre="promulgation",
           date=_D(2023, 1, 1), title="深圳市民政局关于进一步规范社会组织举办研讨会论坛活动的通知"),
      dict(id=51, site="dp", site_level="district", level="district", genre="promulgation",
           date=_D(2023, 3, 1), title="大鹏新区统战和社会建设局关于进一步规范社会组织举办研讨会论坛活动的通知"),
      dict(id=52, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2025, 1, 1), title="湖南省建设工程造价管理办法"),
      dict(id=53, site="lh", site_level="district", level="district", genre="promulgation",
           date=_D(2023, 1, 1), title="深圳市罗湖区人民政府办公室关于印发《罗湖区建设工程造价管理办法》的通知")],
     {50: (50, "unique", "promulgation"), 51: (51, "unique", "implementing"),
      52: (52, "unique", "promulgation"), 53: (53, "unique", "promulgation")}),
    # --- pair-channels.md §1: the trigger must be DATED no later than the doc ---
    # reversed: 云南省行政执法监督条例 (1998) cannot localize the SC 条例 of 2025 -> no flip
    ([dict(id=60, site="gov", site_level="central", level="central", genre="promulgation",
           date=_D(2025, 12, 17), title="行政执法监督条例"),
      dict(id=61, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(1998, 11, 27), title="云南省行政执法监督条例")],
     {60: (60, "unique", "promulgation"), 61: (61, "unique", "promulgation")}),
    # nearest dated parent: the GD re-issuance (Apr) is the city's trigger, not the
    # higher-ranked SC original (Mar) and not the later SC repost (Jul, reversed)
    ([dict(id=70, site="gov", site_level="central", level="central", genre="promulgation",
           date=_D(2024, 3, 13), title="国务院关于印发《推动消费品以旧换新行动方案》的通知"),
      dict(id=71, site="gd", site_level="provincial", level="provincial", genre="promulgation",
           date=_D(2024, 4, 20), title="广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知"),
      dict(id=72, site="huizhou", site_level="municipal", level="municipal", genre="promulgation",
           date=_D(2024, 6, 10), title="惠州市人民政府关于印发惠州市推动消费品以旧换新行动方案的通知"),
      dict(id=73, site="ndrc", site_level="central", level="central", genre="promulgation",
           date=_D(2024, 7, 10), title="国家发展改革委关于印发《推动消费品以旧换新行动方案》的通知")],
     {70: (70, "canonical", "promulgation"), 71: (71, "unique", "implementing"),
      72: (72, "unique", "implementing"), 73: (70, "mirror", "promulgation")}),
    # a higher-ranked LATER text is not the parent when an earlier in-chain one exists:
    # SC text dated after the city doc (reversed, > slack), the GD text before it
    ([dict(id=80, site="gov", site_level="central", level="central", genre="promulgation",
           date=_D(2024, 8, 1), title="国务院关于印发《物业服务收费管理办法》的通知"),
      dict(id=81, site="gd", site_level="provincial", level="provincial", genre="promulgation",
           date=_D(2023, 5, 4), title="广东省人民政府关于印发广东省物业服务收费管理办法的通知"),
      dict(id=82, site="zhuhai", site_level="municipal", level="municipal", genre="promulgation",
           date=_D(2024, 6, 20), title="珠海市人民政府关于印发珠海市物业服务收费管理办法的通知")],
     {80: (80, "unique", "promulgation"), 81: (81, "unique", "promulgation"),
      82: (82, "unique", "implementing")}),
    # month-precision slack: a city doc stamped 2024-05-01 and the GD text of 2024-05-20
    # (lag -19d) is within the 31d month slack -> flips; the same lag on two day-precise
    # dates (05-02 vs 05-21) is beyond the 7d slack -> stays promulgation
    ([dict(id=90, site="gd", site_level="provincial", level="provincial", genre="promulgation",
           date=_D(2024, 5, 20), title="广东省人民政府关于印发广东省能源发展规划的通知"),
      dict(id=91, site="jieyang", site_level="municipal", level="municipal", genre="promulgation",
           date=_D(2024, 5, 1), title="揭阳市人民政府关于印发揭阳市能源发展规划的通知"),
      dict(id=92, site="gd", site_level="provincial", level="provincial", genre="promulgation",
           date=_D(2024, 5, 21), title="广东省人民政府关于印发广东省粮食安全责任考核办法的通知"),
      dict(id=93, site="jieyang", site_level="municipal", level="municipal", genre="promulgation",
           date=_D(2024, 5, 2), title="揭阳市人民政府关于印发揭阳市粮食安全责任考核办法的通知")],
     {90: (90, "unique", "promulgation"), 91: (91, "unique", "implementing"),
      92: (92, "unique", "promulgation"), 93: (93, "unique", "promulgation")}),
    # undated doc / undated trigger: never date-valid -> no flip (the doc stays promulgation)
    ([dict(id=100, site="gov", site_level="central", level="central", genre="promulgation",
           date=_D(2020, 1, 15), title="国务院关于印发《保障农民工工资支付条例》的通知"),
      dict(id=101, site="cq", site_level="provincial", level="provincial", genre="promulgation",
           date=None, title="重庆市人民政府关于印发重庆市保障农民工工资支付条例的通知"),
      dict(id=102, site="gov", site_level="central", level="central", genre="promulgation",
           date=None, title="国务院关于印发《城镇排水与污水处理条例》的通知"),
      dict(id=103, site="gd", site_level="provincial", level="provincial", genre="promulgation",
           date=_D(2021, 3, 3), title="广东省人民政府关于印发广东省城镇排水与污水处理条例的通知")],
     {100: (100, "unique", "promulgation"), 101: (101, "unique", "promulgation"),
      102: (102, "unique", "promulgation"), 103: (103, "unique", "promulgation")}),
    # --- (2026-10-07) national laws fold SHORT and must still pool (the live defect) ---
    # the real 城乡规划法 trio: the two 2019-04-23 copies are one promulgation; the 2015
    # text is a different edition and stays apart.
    ([dict(id=12685270, site="mee", site_level="central", level="central", genre="promulgation",
           date=_D(2019, 4, 23), title="中华人民共和国城乡规划法"),
      dict(id=12742122, site="npc", site_level="central", level="central", genre="promulgation",
           date=_D(2019, 4, 23), title="中华人民共和国城乡规划法"),
      dict(id=12747143, site="npc", site_level="central", level="central", genre="promulgation",
           date=_D(2015, 4, 24), title="中华人民共和国城乡规划法"),
      # the proxy-target doc (citation-network-structure.md §1.3) merely NAMES the law:
      # a province's own 实施办法 is never a copy of it
      dict(id=12747144, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2010, 1, 1), title="河南省实施《中华人民共和国城乡规划法》办法")],
     {12685270: (12685270, "canonical", "promulgation"),
      12742122: (12685270, "mirror", "promulgation"),
      12747143: (12747143, "unique", "promulgation"),
      12747144: (12747144, "unique", "promulgation")}),
    # the documented 政府信息公开条例 split survives: 2008 text + a 2017 bureau repost of it,
    # then the 2019 revision as its own instrument
    ([dict(id=200, site="gov", site_level="central", level="central", genre="promulgation",
           date=_D(2008, 3, 28), title="中华人民共和国政府信息公开条例"),
      dict(id=201, site="mzj", site_level="department", level="central", genre="promulgation",
           date=_D(2017, 8, 24), title="《中华人民共和国政府信息公开条例》全文"),
      dict(id=202, site="npc", site_level="central", level="central", genre="promulgation",
           date=_D(2019, 4, 3), title="中华人民共和国政府信息公开条例")],
     {200: (200, "canonical", "promulgation"), 201: (200, "mirror", "promulgation"),
      202: (202, "unique", "promulgation")}),
    # a LOW-level late repost must not BRIDGE a revision: the real 监察法 shape — 2018 text,
    # a 北京市统计局 repost in 2024-05, then the 2024-12-25 amended text. The gap is measured
    # from the edition's ANCHOR (its latest at-or-above-level copy), so the amendment opens
    # its own instrument instead of being pooled 212 days after the bureau's repost.
    ([dict(id=210, site="npc", site_level="central", level="central", genre="promulgation",
           date=_D(2018, 3, 20), title="中华人民共和国监察法"),
      dict(id=211, site="spp", site_level="central", level="central", genre="promulgation",
           date=_D(2018, 3, 22), title="中华人民共和国监察法"),
      dict(id=212, site="bjb_tjj", site_level="municipal", level="central", genre="promulgation",
           date=_D(2024, 5, 27), title="中华人民共和国监察法"),
      dict(id=213, site="npc", site_level="central", level="central", genre="promulgation",
           date=_D(2024, 12, 25), title="中华人民共和国监察法"),
      dict(id=214, site="nbs", site_level="central", level="central", genre="promulgation",
           date=_D(2025, 6, 9), title="中华人民共和国监察法")],
     {210: (210, "canonical", "promulgation"), 211: (210, "mirror", "promulgation"),
      212: (210, "mirror", "promulgation"), 213: (213, "canonical", "promulgation"),
      214: (213, "mirror", "promulgation")}),
    # a localized re-issuance of a short-folding text still isolates (and still flips to
    # `implementing`): 深圳市's own 消防条例 does not pool with the national 消防法's stem,
    # and 深圳市 + 广东省 copies of one locality-free plan stay out of the central pool
    ([dict(id=220, site="npc", site_level="central", level="central", genre="promulgation",
           date=_D(2021, 4, 29), title="中华人民共和国安全生产法"),
      dict(id=221, site="gdyjt", site_level="provincial", level="central", genre="promulgation",
           date=_D(2021, 6, 17), title="中华人民共和国安全生产法"),
      dict(id=222, site="sz", site_level="municipal", level="municipal", genre="promulgation",
           date=_D(2022, 1, 10), title="深圳市人民政府关于印发深圳市安全生产条例的通知"),
      dict(id=223, site="gd", site_level="provincial", level="provincial", genre="promulgation",
           date=_D(2021, 9, 1), title="广东省安全生产条例")],
     {220: (220, "canonical", "promulgation"), 221: (220, "mirror", "promulgation"),
      222: (222, "unique", "implementing"), 223: (223, "unique", "promulgation")}),
    # --- (2026-10-07) the canonical must be the issuer's copy, not the earliest REPOST ---
    # the live 民法典 pool: every copy derives level `central` from its own title cue, so the
    # level tier ties and the date used to decide alone — the 福建省信访局 copy stamped
    # 2020-01-08 won the canonical slot four months before the NPC adopted the code. The
    # host tier drops the three provincially-hosted reposts and the npc copy (lowest id of
    # the two central-hosted 2020-05-28 copies) wins.
    ([dict(id=900083261, site="fj_xfj", site_level="provincial", level="central",
           genre="promulgation", date=_D(2020, 1, 8), title="中华人民共和国民法典"),
      dict(id=12740336, site="npc", site_level="central", level="central",
           genre="promulgation", date=_D(2020, 5, 28), title="中华人民共和国民法典"),
      dict(id=900063006, site="chinatax", site_level="central", level="central",
           genre="promulgation", date=_D(2020, 5, 28), title="中华人民共和国民法典"),
      dict(id=900083626, site="fj_wjw", site_level="provincial", level="central",
           genre="promulgation", date=_D(2020, 6, 1), title="中华人民共和国民法典"),
      dict(id=900081808, site="fj_scjgj", site_level="provincial", level="central",
           genre="promulgation", date=_D(2020, 7, 17), title="中华人民共和国民法典")],
     {900083261: (12740336, "mirror", "promulgation"), 12740336: (12740336, "canonical", "promulgation"),
      900063006: (12740336, "mirror", "promulgation"), 900083626: (12740336, "mirror", "promulgation"),
      900081808: (12740336, "mirror", "promulgation")}),
    # the earliest date must STILL win among equally authoritative copies: the real 科学绿化
    # shape — a 重庆市林业局 repost 9 days early loses to the host tier, and between the two
    # central-hosted copies the gov original (2021-06-02) beats the mee repost (2021-06-03).
    ([dict(id=900088373, site="cq_lyj", site_level="provincial", level="central",
           genre="promulgation", date=_D(2021, 5, 24),
           title="国务院办公厅关于科学绿化的指导意见"),
      dict(id=12651594, site="gov", site_level="central", level="central",
           genre="promulgation", date=_D(2021, 6, 2),
           title="国务院办公厅关于科学绿化的指导意见"),
      dict(id=12685042, site="mee", site_level="central", level="central",
           genre="promulgation", date=_D(2021, 6, 3),
           title="国务院办公厅关于科学绿化的指导意见")],
     {900088373: (12651594, "mirror", "promulgation"), 12651594: (12651594, "canonical", "promulgation"),
      12685042: (12651594, "mirror", "promulgation")}),
    # the ENCODED decision for a bad date at a higher level: LEVEL/HOST WINS, plausibility
    # is not a tier. The real 网络音视频信息服务管理规定 shape — the gov copy is stamped
    # 2018-12-31, before the 国信办通字〔2019〕3号 it carries and before the measure existed,
    # yet it is the issuing portal's own copy and stays canonical; the correctly dated cac
    # copy is an equally-hosted later publication, and the fj_xfj copy is a repost. A wrong
    # date here is a date_quality fact about the canonical, not grounds to promote a repost.
    ([dict(id=900056231, site="gov", site_level="central", level="central",
           genre="promulgation", date=_D(2018, 12, 31),
           title="关于印发《网络音视频信息服务管理规定》的通知"),
      dict(id=12694184, site="cac", site_level="central", level="central",
           genre="promulgation", date=_D(2019, 11, 29),
           title="关于印发《网络音视频信息服务管理规定》的通知"),
      dict(id=900081900, site="fj_xfj", site_level="provincial", level="central",
           genre="promulgation", date=_D(2019, 11, 29),
           title="关于印发《网络音视频信息服务管理规定》的通知")],
     {900056231: (900056231, "canonical", "promulgation"),
      12694184: (900056231, "mirror", "promulgation"),
      900081900: (900056231, "mirror", "promulgation")}),
    # --- the recurring-instrument split (2026-10-07) ---------------------------
    # ANNUAL RE-ISSUANCE: 国务院关于落实《政府工作报告》重点工作分工的意见 is a different text
    # every year, and one edition of the pool (a year's gap is under EDITION_GAP_DAYS)
    # held all of them. Each year's own 国发 number splits them; each year's own mirrors
    # still pool.
    ([dict(id=301, site="gov", site_level="central", level="central", genre="promulgation",
           docnum="国发〔2021〕6号", date=_D(2021, 3, 25),
           title="国务院关于落实《政府工作报告》重点工作分工的意见"),
      dict(id=302, site="mee", site_level="central", level="central", genre="promulgation",
           docnum="国发〔2021〕6号", date=_D(2021, 3, 29),
           title="国务院关于落实《政府工作报告》重点工作分工的意见"),
      dict(id=303, site="gov", site_level="central", level="central", genre="promulgation",
           docnum="国发〔2022〕9号", date=_D(2022, 3, 25),
           title="国务院关于落实《政府工作报告》重点工作分工的意见"),
      dict(id=304, site="mee", site_level="central", level="central", genre="promulgation",
           docnum="国发〔2022〕9号", date=_D(2022, 3, 25),
           title="国务院关于落实《政府工作报告》重点工作分工的意见")],
     {301: (301, "canonical", "promulgation"), 302: (301, "mirror", "promulgation"),
      303: (303, "canonical", "promulgation"), 304: (303, "mirror", "promulgation")}),
    # TRUE LATE-MIRROR SET, 28 years wide, must STAY pooled: one 条例 and its 民委 reposts,
    # no 文号 anywhere — and 福建省民宗厅 holds TWO copies six years apart, which is exactly
    # the same-site repeat R2 keys on. The promulgation genre is what keeps R2 off it.
    ([dict(id=311, site="npc", site_level="central", level="central", genre="promulgation",
           docnum="", date=_D(1993, 9, 15), title="城市民族工作条例"),
      dict(id=312, site="fj_mzzjt", site_level="provincial", level="central",
           genre="promulgation", docnum="", date=_D(2015, 3, 19), title="城市民族工作条例"),
      dict(id=313, site="xz_mw", site_level="provincial", level="central",
           genre="promulgation", docnum="", date=_D(2019, 3, 15), title="城市民族工作条例"),
      dict(id=314, site="fj_mzzjt", site_level="provincial", level="central",
           genre="promulgation", docnum="", date=_D(2021, 10, 9), title="城市民族工作条例")],
     {311: (311, "canonical", "promulgation"), 312: (311, "mirror", "promulgation"),
      313: (311, "mirror", "promulgation"), 314: (311, "mirror", "promulgation")}),
    # 第N号 RECURRENCE: 国务院关于修改和废止部分行政法规的决定 comes round under a new 国令
    # number. The number lives in `document_number` on the gov copies and in the mee
    # copy's TITLE TAIL — which _title_cores_of_title strips before keying, so without
    # reading the tail the mee copy looks un-numbered. The un-numbered npc copies attach
    # to the nearest numbered text, each on its own side of the split.
    ([dict(id=321, site="npc", site_level="central", level="central", genre="promulgation",
           docnum="", date=_D(2026, 1, 30), title="国务院关于修改和废止部分行政法规的决定"),
      dict(id=322, site="gov", site_level="central", level="central", genre="promulgation",
           docnum="国令第829号", date=_D(2026, 2, 5), title="国务院关于修改和废止部分行政法规的决定"),
      dict(id=323, site="npc", site_level="central", level="central", genre="promulgation",
           docnum="", date=_D(2026, 8, 8), title="国务院关于修改和废止部分行政法规的决定"),
      dict(id=324, site="gov", site_level="central", level="central", genre="promulgation",
           docnum="国令第843号", date=_D(2026, 8, 13), title="国务院关于修改和废止部分行政法规的决定"),
      dict(id=325, site="mee", site_level="central", level="central", genre="promulgation",
           docnum="", date=_D(2026, 8, 14),
           title="国务院关于修改和废止部分行政法规的决定（中华人民共和国国务院令 第843号）")],
     {321: (321, "canonical", "promulgation"), 322: (321, "mirror", "promulgation"),
      323: (323, "canonical", "promulgation"), 324: (323, "mirror", "promulgation"),
      325: (323, "mirror", "promulgation")}),
    # INVARIANT 1: 政府信息公开条例 stays exactly 2 instruments (2008 and the 2019 revision).
    # This is the regression that moved R1 inside the edition walk: the un-numbered 2014
    # and 2024 reposts are more than EDITION_GAP_DAYS from any numbered copy, so
    # partitioning the whole key group first stranded them as a third instrument.
    ([dict(id=331, site="gov", site_level="central", level="central", genre="promulgation",
           docnum="国令第492号", date=_D(2008, 3, 28), title="中华人民共和国政府信息公开条例"),
      dict(id=332, site="fj_wjw", site_level="provincial", level="central",
           genre="promulgation", docnum="", date=_D(2014, 8, 2), title="中华人民共和国政府信息公开条例"),
      dict(id=333, site="mzj", site_level="department", level="central", genre="promulgation",
           docnum="中华人民共和国国务院令第492号", date=_D(2017, 8, 24),
           title="中华人民共和国政府信息公开条例"),
      dict(id=334, site="npc", site_level="central", level="central", genre="promulgation",
           docnum="", date=_D(2019, 4, 3), title="中华人民共和国政府信息公开条例"),
      dict(id=335, site="gov", site_level="central", level="central", genre="promulgation",
           docnum="国令第711号", date=_D(2019, 4, 15), title="中华人民共和国政府信息公开条例"),
      dict(id=336, site="bjb_tjj", site_level="municipal", level="central",
           genre="promulgation", docnum="", date=_D(2024, 5, 27),
           title="中华人民共和国政府信息公开条例")],
     {331: (331, "canonical", "promulgation"), 332: (331, "mirror", "promulgation"),
      333: (331, "mirror", "promulgation"), 334: (334, "canonical", "promulgation"),
      335: (334, "mirror", "promulgation"), 336: (334, "mirror", "promulgation")}),
    # INVARIANT 2: the 城乡规划法 trio — the 2019 pair pools with the mee copy canonical
    # (lowest id of the two central-hosted same-date copies) and the 2015 text stays apart.
    ([dict(id=12747143, site="npc", site_level="central", level="central",
           genre="promulgation", docnum="", date=_D(2015, 4, 24), title="中华人民共和国城乡规划法"),
      dict(id=12685270, site="mee", site_level="central", level="central",
           genre="promulgation", docnum="", date=_D(2019, 4, 23), title="中华人民共和国城乡规划法"),
      dict(id=12742122, site="npc", site_level="central", level="central",
           genre="promulgation", docnum="", date=_D(2019, 4, 23), title="中华人民共和国城乡规划法")],
     {12747143: (12747143, "unique", "promulgation"),
      12685270: (12685270, "canonical", "promulgation"),
      12742122: (12685270, "mirror", "promulgation")}),
    # A SERIES dissolves: 政府工作报告 names no text — a different report every year for
    # every government that writes one. sz_gazette's own run is the evidence.
    ([dict(id=341, site="sz_gazette", site_level="municipal", level="municipal",
           genre="other", docnum="", date=_D(2015, 6, 25), title="政府工作报告"),
      dict(id=342, site="sz_gazette", site_level="municipal", level="municipal",
           genre="other", docnum="", date=_D(2016, 3, 9), title="政府工作报告"),
      dict(id=343, site="heyuan", site_level="municipal", level="municipal",
           genre="other", docnum="", date=_D(2018, 7, 25), title="政府工作报告")],
     {341: (341, "unique", "other"), 342: (342, "unique", "other"),
      343: (343, "unique", "other")}),
    # R2 MUST NOT fire on an `implementing` set: 深圳市教育局 re-posts its own 实施意见 three
    # times over 187 days, all under 深教规〔2024〕2号 — one text, and the gazette's copy is
    # its mirror. (A `promulgation` or `implementing` member is a text; `other` is not.)
    ([dict(id=351, site="szeb", site_level="department", level="municipal",
           genre="implementing", docnum="深教规〔2024〕2号", date=_D(2024, 3, 27),
           title="深圳市教育局关于印发《深圳市初中学业水平考试体育与健康科目考试实施意见》的通知"),
      dict(id=352, site="sz_gazette", site_level="municipal", level="municipal",
           genre="implementing", docnum="深教规〔2024〕2号", date=_D(2024, 4, 8),
           title="深圳市教育局关于印发《深圳市初中学业水平考试体育与健康科目考试实施意见》的通知"),
      dict(id=353, site="szeb", site_level="department", level="municipal",
           genre="implementing", docnum="深教规〔2024〕2号", date=_D(2024, 9, 30),
           title="深圳市教育局关于印发《深圳市初中学业水平考试体育与健康科目考试实施意见》的通知")],
     {351: (351, "canonical", "implementing"), 352: (351, "mirror", "implementing"),
      353: (351, "mirror", "implementing")}),
    # A MIS-STORED 文号 must not split a mirror pair: chinatax keeps the REFERENCED
    # instrument's number (财库〔2020〕46号) on a text whose own number is 税总函〔2021〕67号.
    # Nine days apart is a mirror, not a re-issuance — DOCNUM_SPLIT_MIN_DAYS keeps them.
    ([dict(id=361, site="chinatax", site_level="central", level="central",
           genre="promulgation", docnum="财库〔2020〕46号", date=_D(2021, 4, 16),
           title="国家税务总局关于落实《政府采购促进中小企业发展管理办法》的通知"),
      dict(id=362, site="gov", site_level="central", level="central", genre="promulgation",
           docnum="税总函〔2021〕67号", date=_D(2021, 4, 25),
           title="国家税务总局关于落实《政府采购促进中小企业发展管理办法》的通知")],
     {361: (361, "canonical", "promulgation"), 362: (361, "mirror", "promulgation")}),
    # …but the date guard must not re-merge two LOCALITIES' own documents: Huizhou's and
    # Jiangmen's 2016 应急管理工作计划, five days apart under their own 文号. Zhongshan's
    # un-numbered copy names its own city and joins neither.
    ([dict(id=371, site="jiangmen", site_level="municipal", level="municipal",
           genre="promulgation", docnum="江府办函〔2016〕52号", date=_D(2016, 4, 1),
           title="江门市人民政府办公室关于印发2016年全市应急管理工作计划的通知"),
      dict(id=372, site="huizhou", site_level="municipal", level="municipal",
           genre="promulgation", docnum="惠府办函〔2016〕35号", date=_D(2016, 4, 6),
           title="惠州市人民政府办公室关于印发2016年全市应急管理工作计划的通知"),
      dict(id=373, site="huizhou2", site_level="municipal", level="municipal",
           genre="promulgation", docnum="惠府办函〔2016〕35号", date=_D(2016, 4, 6),
           title="惠州市人民政府办公室关于印发2016年全市应急管理工作计划的通知"),
      dict(id=374, site="zhongshan", site_level="municipal", level="municipal",
           genre="promulgation", docnum="", date=_D(2016, 4, 26),
           title="中山市人民政府办公室关于印发2016年全市应急管理工作计划的通知")],
     {371: (371, "unique", "promulgation"), 372: (372, "canonical", "promulgation"),
      373: (372, "mirror", "promulgation"), 374: (374, "unique", "promulgation")}),
]
# localized_of expectations, one dict per _POOL_TESTS entry (id -> trigger id; unlisted = NULL).
# In test 3 the bare GD copy (id 3) is also a provincial-level localization of the SC text.
_LOCALIZED_OF = [{11271152: 900039931}, {}, {2: 1, 3: 1}, {}, {}, {}, {31: 30}, {41: 40}, {51: 50},
                 {}, {71: 70, 72: 71}, {82: 81}, {91: 90}, {},
                 {}, {}, {}, {222: 223}, {}, {}, {},
                 # the recurring-instrument split cases: no localization in any of them
                 {}, {}, {}, {}, {}, {}, {}, {}, {}]
# A6 province: (doc fields, level, lead_issuer) -> 2-letter code. Central docs are tested
# through derive_province's caller (build() passes only SUBNATIONAL levels) — here a
# central NAME must resolve to None.
_PROVINCE_TESTS = [
    # npc 地方法规: the publisher is the only locality field
    (dict(title="江苏省大气污染防治条例", docnum="", publisher="江苏省人民代表大会常务委员会"), None, "js"),
    (dict(title="深圳经济特区养老服务条例", docnum="", publisher="深圳市人民代表大会常务委员会"), None, "gd"),
    (dict(title="内蒙古自治区草原条例", docnum="", publisher="内蒙古自治区人民代表大会常务委员会"), None, "nm"),
    # miit: a 省通信管理局 lead issuer on the ministry's site (publisher = the ministry)
    (dict(title="海南省通信管理局关于开展职称评审专家征集的通知", docnum="", publisher="工业和信息化部"),
     "海南省通信管理局", "hi"),
    # bjrd: no issuer / publisher, the title head names the body
    (dict(title="北京市人民代表大会法制委员会关于《北京市测绘地理信息条例（草案）》审议结果的报告",
          docnum="", publisher=""), None, "bj"),
    # 文号 agency (粤府办 -> 广东省人民政府办公厅) when the issuer is missing
    (dict(title="关于印发若干措施的通知", docnum="粤府办〔2024〕3号", publisher=""), None, "gd"),
    # district issuer -> its city's province; 直辖市 district -> the 直辖市
    (dict(title="关于印发龙华区政务公开办法的通知", docnum="", publisher=""), "深圳市龙华区人民政府", "gd"),
    (dict(title="密云区文化和旅游发展规划", docnum="", publisher=""), "北京市密云区文化和旅游局", "bj"),
    # 5-char 自治州 head: the longest-prefix fallback
    (dict(title="关于印发延边州若干措施的通知", docnum="", publisher=""), "延边朝鲜族自治州人民政府", "jl"),
    # localize() locality (a bare core with a city prefix) when every header field is empty
    (dict(title="苏州市推动消费品以旧换新实施方案", docnum="", publisher="", _loc="苏州市"), None, "js"),
    # central name / no locality anywhere -> None
    (dict(title="关于印发《信息通信行业发展规划》的通知", docnum="", publisher="工业和信息化部"), "工业和信息化部", None),
    (dict(title="市人民政府办公室关于印发市级储备粮管理办法的通知", docnum="", publisher="", _loc="<municipal>@huizhou"),
     None, None),
]
_CHAIN_TESTS = [
    ("广东省", ()), ("北京市", ()), ("宁夏回族自治区", ()), ("广州市", ("广东省",)),
    ("苏州市", ("江苏省",)), ("深圳市龙华区", ("深圳市", "广东省")), ("大鹏新区", ("深圳市", "广东省")),
    ("北京市密云区", ("北京市",)), ("硚口区", ("武汉市", "湖北省")), ("转发市", None),
    ("<municipal>@huizhou", None), (None, None), ("延边朝鲜族自治州", ("吉林省",)),
]
_GENERIC_STEM_TESTS = [
    ("人民代表大会常务委员会议事规则", True), ("制定地方性法规条例", True),
    ("人民代表大会常务委员会讨论决定重大事项的规定", True), ("人民政府关于修改部分规章的决定", True),
    ("人民政府关于宣布失效一批市政府文件的决定", True), ("食品药品监督管理局主要职责内设机构和人员编制规定", True),
    ("人民政府工作规则", True), ("人民政府2022年度重大行政决策事项目录", True),
    ("文明行为促进条例", False), ("粮食安全责任考核办法", False), ("养犬管理条例", False),
    ("推动大规模设备更新和消费品以旧换新行动方案", False),
]


def _stamp_docs(bulk, bulk_stamped, daily, daily_same_day=True, bulk_day=date(2026, 8, 13)):
    """Site 's': `bulk` docs crawled on `bulk_day`, of which `bulk_stamped` are dated ON that
    day and the rest carry a spread of older real dates; then `daily` docs crawled one per
    following day, dated on their crawl day (a live site synced daily) or a day earlier."""
    from datetime import timedelta
    out, i = {}, 0
    for j in range(bulk):
        dt = bulk_day if j < bulk_stamped else date(2024, 1, 1) + timedelta(days=j % 700)
        out[i] = {"site": "s", "date": dt, "crawl_date": bulk_day}; i += 1
    for j in range(daily):
        cd = bulk_day + timedelta(days=1 + j)
        out[i] = {"site": "s", "date": cd if daily_same_day else cd - timedelta(days=1), "crawl_date": cd}; i += 1
    return out


def _pile_docs(piles, spread, crawl_day=date(2026, 3, 31)):
    """Site 's' crawled on ONE day (far from every date, so the crawl-day test is silent):
    `piles` = [(date, n)] docs sitting on that exact DATE day, plus `spread` docs with real
    dates fanned over 2012-2025 (one per ~3 days, never the 1st)."""
    from datetime import timedelta
    out, i = {}, 0
    for dt, n in piles:
        for _ in range(n):
            out[i] = {"site": "s", "date": dt, "crawl_date": crawl_day}; i += 1
    for j in range(spread):
        dt = date(2012, 1, 2) + timedelta(days=(3 * j) % 5000)
        if dt.day == 1:
            dt += timedelta(days=1)
        out[i] = {"site": "s", "date": dt, "crawl_date": crawl_day}; i += 1
    return out


_STAMP_TESTS = [
    # (label, docs, expected stamped set)
    # --- (2) multi-batch date-day test ---
    ("suzhou shape: two regeneration batches 1,860 + 1,499 of 4,840 (38% + 31%), crawled 2026-03-31",
     _pile_docs([(date(2023, 2, 9), 1860), (date(2025, 2, 11), 1499)], 1481), {"s"}),
    ("suzhou after the URL-month redate: piles gone, 3,359 docs spread over months (day 01 exempt)",
     _pile_docs([(date(2023, 2, 1), 60), (date(2025, 2, 1), 55)], 4700), set()),
    ("gazette / gov shape: ONE real heavy publication day, 2,308 of 20,150 (11.5%)",
     _pile_docs([(date(2018, 12, 31), 2308)], 17842), set()),
    ("samr shape: one 1,841-doc day of 4,361 (42%) — under the 50% multi-batch bar",
     _pile_docs([(date(2024, 5, 7), 1841)], 2520), set()),
    ("single source-stamp batch of 55% (one regeneration day, not our crawl day)",
     _pile_docs([(date(2023, 2, 9), 110)], 90), {"s"}),
    ("URL-month fallback shape (yc): 80% on 2026-09-01 — day 01 is exempt",
     _pile_docs([(date(2026, 9, 1), 225)], 55), set()),
    ("year fallback shape (laiwu): 95% on 2026-01-01 — exempt", _pile_docs([(date(2026, 1, 1), 125)], 6), set()),
    ("many small piles: 6 days x 9% each (54%) — none reaches the 10% bulk-day bar",
     _pile_docs([(date(2020, 3, 3 + k), 18) for k in range(6)], 92), set()),
    ("two batches 30% + 25% = 55%, each >= 20 docs and >= 10%", _pile_docs([(date(2021, 6, 6), 60), (date(2022, 7, 7), 50)], 90), {"s"}),
    ("two batches 30% + 19% = 49% — under the bar", _pile_docs([(date(2021, 6, 6), 60), (date(2022, 7, 7), 38)], 102), set()),
    ("too small for the multi-batch test (<100 dated docs)", _pile_docs([(date(2023, 2, 9), 50), (date(2025, 2, 11), 40)], 9), set()),
    # --- (1) single crawl-day test ---
    ("bulk stamp: 150-doc pull all dated on the pull day", _stamp_docs(150, 150, 0), {"s"}),
    ("bulk stamp + daily tail (stamped site kept syncing)", _stamp_docs(150, 140, 60), {"s"}),
    ("shallow recent crawl: 200-doc bulk with real dates, 100 daily same-day (jcgov shape)",
     _stamp_docs(200, 10, 100), set()),
    ("js_mzt shape: 200-doc bulk real dates, 217 daily picked up a day late", _stamp_docs(200, 0, 217, False), set()),
    ("whole-site 'in crawl year' 100% but bulk is real (liaoning shape: 62 bulk, 1,100 daily)",
     _stamp_docs(62, 4, 300), set()),
    ("too small (<100 docs)", _stamp_docs(80, 80, 0), set()),
    ("bulk day under the 20-doc floor (leshan shape: 17-doc day, 88% stamped)", _stamp_docs(17, 15, 150), set()),
    ("borderline: exactly 70% of a 20-doc bulk day", _stamp_docs(20, 14, 100), {"s"}),
    ("just under: 69% of a 100-doc bulk day, on a 1,000-doc site (date-day share 6.9%)",
     _stamp_docs(100, 69, 900), set()),
    ("69% of a 100-doc bulk day on a 100-doc site: under the crawl-day bar but 69% of the site "
     "sits on one date-day -> the multi-batch test flags it", _stamp_docs(100, 69, 0), {"s"}),
]


def self_test():
    fails = 0
    for name, exp in _LEVEL_TESTS:
        got = level_of_name(name)
        if got != exp:
            fails += 1
            print(f"XX level_of_name({name!r}) = {got!r}, expected {exp!r}")
    for title, exp in _TITLE_LEVEL_TESTS:
        got = level_of_title(title)
        if got != exp:
            fails += 1
            print(f"XX level_of_title({title[:40]!r}) = {got!r}, expected {exp!r}")
    for title, algo, lvl, exp in _GENRE_TESTS:
        got = derive_genre(title, algo, lvl)
        if got != exp:
            fails += 1
            print(f"XX derive_genre({title[:40]!r}, {algo}, {lvl}) = {got!r}, expected {exp!r}")
    for title, algo, exp in _KIND_TESTS:
        got = derive_instrument_kind(title, algo)
        if got != exp:
            fails += 1
            print(f"XX derive_instrument_kind({title[:40]!r}, {algo}) = {got!r}, expected {exp!r}")
    for a, b, same in _KEY_TESTS:
        ka, kb = instrument_key(a), instrument_key(b)
        # two unkeyed titles are NOT "the same instrument" — a None key never pools
        if (ka == kb) != same or (same and ka is None):
            fails += 1
            print(f"XX instrument_key: {ka!r} vs {kb!r} (expected same={same})")
    for title, exp in _SHORT_KEY_TESTS:
        got = instrument_key(title)
        if got != exp:
            fails += 1
            print(f"XX instrument_key({title!r}) = {got!r}, expected {exp!r}")
    for title, site, exp_stem, exp_loc in _LOCALIZE_TESTS:
        stem, loc, _ = localize(title, site)
        if (stem, loc) != (exp_stem, exp_loc):
            fails += 1
            print(f"XX localize({title[:40]!r}) = {(stem, loc)!r}, expected {(exp_stem, exp_loc)!r}")
    for (members, expected), exp_trig in zip(_POOL_TESTS, _LOCALIZED_OF):
        docs = {m["id"]: dict(m) for m in members}
        assign_instruments(docs)
        got = {i: (d["instrument_id"], d["instrument_role"], d["genre"]) for i, d in docs.items()}
        if got != expected:
            fails += 1
            print(f"XX assign_instruments: {got!r}\n   expected {expected!r}")
        lo = {i: d["localized_of"] for i, d in docs.items()}
        exp_lo = {i: exp_trig.get(i) for i in docs}
        if lo != exp_lo:
            fails += 1
            print(f"XX localized_of: {lo!r}\n   expected {exp_lo!r}")
    for loc, exp in _CHAIN_TESTS:
        got = jurisdiction_chain(loc)
        if got != exp:
            fails += 1
            print(f"XX jurisdiction_chain({loc!r}) = {got!r}, expected {exp!r}")
    for fields, issuer, exp in _PROVINCE_TESTS:
        got = derive_province(fields, issuer)
        if got != exp:
            fails += 1
            print(f"XX derive_province({fields['title'][:30]!r}, {issuer!r}) = {got!r}, expected {exp!r}")
    for stem, exp in _GENERIC_STEM_TESTS:
        if bool(GENERIC_STEM_RE.search(stem)) != exp:
            fails += 1
            print(f"XX GENERIC_STEM_RE({stem!r}) expected {exp}")
    for label, docs, exp in _STAMP_TESTS:
        got = set(crawl_stamped_sites(docs, {"s": "municipal"}, 2026))
        if got != exp:
            fails += 1
            print(f"XX crawl_stamped_sites[{label}] = {got!r}, expected {exp!r}")
    total = (len(_LEVEL_TESTS) + len(_TITLE_LEVEL_TESTS) + len(_GENRE_TESTS) + len(_KIND_TESTS) + len(_KEY_TESTS)
             + len(_SHORT_KEY_TESTS) + len(_LOCALIZE_TESTS) + len(_POOL_TESTS) + len(_CHAIN_TESTS)
             + len(_GENERIC_STEM_TESTS) + len(_STAMP_TESTS) + len(_PROVINCE_TESTS))
    print(f"self-test: {total - fails}/{total} passed")
    return fails == 0


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--dry-run", action="store_true", help="compute + stats, no write")
    ap.add_argument("--dry-run-flips", action="store_true",
                    help="broad vs in-chain genre-flip counts + 30 sample flip-backs; read-only, no write")
    ap.add_argument("--dry-run-kind", action="store_true",
                    help="A7 instrument_kind by level + framework-gate before/after; read-only, no write")
    ap.add_argument("--validate", action="store_true", help="run the A1–A4 truth checks")
    ap.add_argument("--sample", type=int, default=0, help="stratified hand-check dump of N docs")
    ap.add_argument("--sample-field", default="level", choices=["level", "genre", "instrument_kind"])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--force", action="store_true", help="write even if the nightly lock exists")
    args = ap.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1

    writing = not (args.dry_run or args.dry_run_flips or args.dry_run_kind or args.validate
                   or args.sample)
    if writing and LOCK_DIR.exists() and not args.force:
        print(f"nightly lock {LOCK_DIR} exists — refusing to write (use --force)")
        return 2

    conn = connect(args.db, ro=not writing)
    load_site_names(conn)  # province_of(site) for the A6 coverage audit
    docs, meta = build(conn)
    site_level = {d["site"]: d["site_level"] for d in docs.values()}
    print_stats(docs, meta, site_level)
    if args.validate:
        validate(docs, meta)
    if args.dry_run_flips:
        dry_run_flips(docs, meta, seed=args.seed)
    if args.dry_run_kind:
        dry_run_kind(docs, seed=args.seed)
    if args.sample:
        sample(docs, args.sample, args.seed, args.sample_field)
    if writing:
        n, t = write(conn, docs)
        print(f"\nwrote doc_identity: {n:,} rows in {t:.1f}s (one transaction)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
