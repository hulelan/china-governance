"""
Remove page-chrome TAILS (share widgets, print/close buttons, prev/next nav,
related-link lists, trailing JS/CSS) that body extractors swept in after the
real text of a document.

Why this exists: the A7 body work (0eeb4d5 / f858356 / ff8ed83) fixed the
extractors so NEW crawls stop at the share/print/nav block, but
`backfill_from_html.py` deliberately refuses to overwrite a body with a SHORTER
one, so no extractor fix can ever propagate a tail-trim to an existing row.
The tail is not harmless: a 相关链接 / 相关信息 / 上一篇：《X》 block holds OTHER
documents' titles, which the citation extractor reads as references, and the
share/JS boilerplate is counted as text by ai_relevance and the 5-gram
fidelity scores.

DETECTION (pure function `find_tail`, unit-tested in tests/test_trim_body_tails.py)
  Lines are classified as
    ANCHOR   a widget line: after removing widget tokens (分享到 / 微信 / 微博 /
             QQ空间 / 扫一扫在手机打开当前页 / 打印本页 / 【打印】 / 【关闭】 /
             关闭窗口 / 返回顶部 …) and separators nothing is left;
    NAV      a bare section label (相关链接 / 相关解读 / 相关文档 / 网站导航 /
             返回网易首页 …) or a 上一篇： / 下一篇： line;
    CODE     JS / CSS / HTML source;
    SHORT    any other line <= 60 chars without 。！？ (a link title, a nav item);
    PROSE    everything else.
  Walking back from the END, the tail is the block of ANCHOR/NAV/CODE/SHORT/
  blank lines that ends the body; it starts at its EARLIEST ANCHOR/NAV/CODE line
  such that the SHORT text after that point totals <= 200 chars. It must
  contain at least one ANCHOR or NAV line (a code-only tail is out of scope).
  Consequences, all tested:
    * the first PROSE line from the end stops the walk, so a 分享到 in the
      middle of a body is never touched;
    * SHORT lines BEFORE the first marker (signature, date, attachment name)
      are kept: nothing preceding the first tail marker is removed;
    * the kept text is exactly body[:cut] with trailing whitespace stripped,
      so it is a byte-for-byte prefix of the stored body.
  An inline rule covers single-line bodies that end in "… 扫一扫在手机打开当前页"
  or "… 相关链接：一图读懂《X》" (gdny writes the whole page as one line).

REMEDY per document
  reextract   raw_html_path exists and the file is present, and the site's own
              extractor (routed exactly as backfill_from_html.py does) now
              returns a text with NO tail, >= 50 chars, and not shorter than
              90% of the trimmed text (nor longer than 1.5x unless the stored
              body was all chrome). Preferred: it is what the crawler would
              store today.
  trim        otherwise: cut the stored text at the tail start. No fetch.
  flagged     the text left after the cut has < 20 meaningful characters (the
              "body" was ALL chrome, e.g. an attachment-only page whose
              extractor took the share bar) and re-extraction did not produce a
              real body. Never written: an empty body is worse than a known-bad
              one, because it hides the row from the bodiless backlog queries.
              Recorded in body_tail_flags.

AUDIT (reversible)
  body_tail_trims(doc_id, old_len, new_len, method, trimmed_at, removed_tail, old_body)
    trim:      removed_tail = old[len(new):] (new is a prefix of old, so
               old == new + removed_tail exactly); old_body NULL.
    reextract: old_body = the full previous body.
  `--revert` restores every audited row whose body is still the one we wrote.

WRITES  base.write_with_retry / commit_with_retry; commit every 200 rows; PASSIVE
checkpoint every 1,000; final TRUNCATE (an UPDATE of body_text_cn rewrites its
overflow pages and fires the documents_fts / doc_search triggers, see the
compute_scores lesson in CLAUDE.md). Each UPDATE is guarded by the old body
(`WHERE id=? AND body_text_cn=?`), so a row changed by another writer since the
scan is skipped, never clobbered. Refuses to run while the nightly lock
/tmp/china-governance-daily-sync.lock.d exists unless --force.

Usage:
    python3 scripts/trim_body_tails.py --dry-run              # read-only report + 20-row sample
    python3 scripts/trim_body_tails.py --dry-run --site suzhou
    python3 scripts/trim_body_tails.py --apply                # write
    python3 scripts/trim_body_tails.py --apply --no-reextract # tail-trim only
    python3 scripts/trim_body_tails.py --revert               # undo every audited change

AFTER --apply, re-derive (see the report): citations (extract_citations.py) →
citation_rank / doc_inbound (compute_scores.py, build_site_stats.py) →
diffusion_events / tracker / validate_cascades; ai_relevance (compute_scores.py);
doc_search_seg (build_search_index_seg.py: contentless, not trigger-synced);
any cached pairs.py fidelity output. doc_identity reads header fields only and
is NOT affected.
"""

import argparse
import json
import os
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

LOCK_DIR = Path("/tmp/china-governance-daily-sync.lock.d")

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

WS = " \t\r\n　\xa0   ​﻿"

# Widget tokens, longest first so 扫一扫在手机打开当前页 is removed before 扫一扫.
_WIDGET_TOKENS = sorted([
    "扫一扫在手机打开当前页", "扫一扫在手机上查看当前页面", "扫一扫在手机打开", "手机打开当前页",
    "扫描二维码分享到手机", "扫描二维码", "分享到手机", "扫一扫", "分享到", "分享", "微信朋友圈", "朋友圈", "微信好友", "微信", "新浪微博", "腾讯微博",
    "微博", "QQ空间", "Qzone", "QQ好友", "QQ", "人人网", "豆瓣", "打印本页", "打印此页",
    "打印本文", "打印文章", "打印", "关闭窗口", "关闭本页", "关闭本文", "关闭", "返回顶部", "收藏本页", "加入收藏", "收藏", "字号", "字体", "默认",
    "放大", "缩小", "大", "中", "小", "&nbsp;",
], key=len, reverse=True)
# A widget line must contain one of these; 大/中/小 alone never make a line chrome.
_WIDGET_CORE = ("扫一扫", "手机打开当前页", "分享", "微信", "微博", "QQ空间", "打印", "关闭",
                "返回顶部", "字号", "字体", "收藏")
_SEP_RE = re.compile(r"[\s　\xa0  【】\[\]（）()|｜/\\·•:：,，、\-—_<>《》\.。]+")
_WIDGET_RE = re.compile("|".join(re.escape(t) for t in _WIDGET_TOKENS))

_NAV_LABELS = {
    "相关链接", "相关文档", "相关解读", "相关文章", "相关内容", "相关信息", "相关新闻",
    "相关阅读", "相关稿件", "相关报道", "网站导航", "读取内容中请等待", "返回网易首页",
    "下载网易新闻客户端", "阅读下一篇", "返回列表", "返回首页", "上一篇", "下一篇", "上一条", "下一条",
    "上一页", "下一页", "网站声明", "我要纠错", "解读", "登录", "注册", "新闻链接", "关联稿件",
}
_RELATED_RE = re.compile(r"^[【\[]?相关(链接|文档|解读|文章|内容|信息|新闻|阅读|稿件|报道)[】\]]?\s*[：:]")
# NOTE: 相关附件 / 相关文件 are NOT markers: they head the document's OWN attachment list.
_PREVNEXT_RE = re.compile(r"^[【\[]?(上一篇|下一篇|上一条|下一条)[】\]]?\s*[：:]")

_CODE_STRONG = re.compile(
    r"^</?[a-zA-Z!][^一-鿿]*$"      # an HTML tag line (no CJK)
    r"|^<(div|span|script|style|a|p|li|ul|img|iframe|input)\b"
    r"|\$\(|\bfunction\s*\(|=>|\bdocument\.|\bwindow\.|\.share\(|setWechatInfo"
    r"|===|&&|\|\||\bvar\s+\w+\s*=|\blet\s+\w+\s*=|\bconst\s+\w+\s*="
    r"|^[.#@][\w\-][^一-鿿]*\{|\d+px\s*;|:\s*#[0-9a-fA-F]{3,6}\b|/\*.*\*/"
    r"|^\s*[\"'][A-Za-z_]\w*[\"']\s*:"              # "key": … (quoted JSON/JS key)
    r"|^\s*,?\s*[A-Za-z_]\w*\s*:\s*[\"'{\[]"         # key: 'v' / ,key:{ (JS object literal)
    r"|^\s*[A-Za-z_]\w*\s*:\s*[^\u4e00-\u9fff]*,\s*$"  # key: value, (no CJK)
    r"|^\s*//|^\s*<!--|-->\s*$|[\"']\s*[,;)]\s*$"
    r"|^\s*[\"']?[A-Za-z_][\w\-]*[\"']?\s*:\s*function"
)
_CODE_WEAK = re.compile(r"^[{}()\[\];,\s]+$|[{;]\s*$|^\s*}\s*\)?\s*;?\s*$|^\s*(if|else|return|for|while)\b")
_CJK_RE = re.compile(r"[一-鿿]")
_MEANINGFUL_RE = re.compile(r"[一-鿿A-Za-z0-9]")
_SENT_END = re.compile(r"[。！？]")

SHORT_MAX = 60        # a SHORT line (link title / nav item) is at most this long
SHORT_RUN_BUDGET = 400  # SHORT chars allowed in one run between two tail markers
FINAL_RUN_BUDGET = 150  # … and in the run AFTER the last marker (a tail ends in chrome)
INLINE_MAX = 300      # an inline tail (same line as the text) is at most this long
MIN_KEPT = 20         # fewer meaningful chars than this left → the body was all chrome

ANCHOR, NAV, CODE, SHORT, PROSE, BLANK = "anchor", "nav", "code", "short", "prose", "blank"

# Markers reported per row (the task's list + what the tails actually carry).
REPORT_MARKERS = ["分享到", "微信", "微博", "QQ空间", "打印本页", "关闭窗口", "【打印】", "【关闭】",
                  "扫一扫在手机打开当前页", "相关链接", "相关解读", "相关文档", "上一篇", "下一篇",
                  "网站导航", "CODE(js/css)"]
_CODE_SHARE = ("分享到", "扫一扫", "QQ空间", "qzone", "shareqq", ".share(")


def _cjk_ratio(s: str) -> float:
    return len(_CJK_RE.findall(s)) / max(1, len(s))


def classify_line(line: str) -> str:
    s = line.strip(WS)
    if not s:
        return BLANK
    # widget line
    if any(c in s for c in _WIDGET_CORE) and len(s) <= 80:
        residue = _SEP_RE.sub("", _WIDGET_RE.sub("", s))
        if not residue:
            return ANCHOR
    if _SEP_RE.sub("", s) in _NAV_LABELS or s.rstrip("：:") in _NAV_LABELS:
        return NAV
    if (_PREVNEXT_RE.match(s) or _RELATED_RE.match(s)) and len(s) <= 200 and "。" not in s:
        return NAV
    if s.startswith("读取内容中") or s in ("/阅读下一篇/",):
        return NAV
    # A long line that is mostly Chinese is never code, whatever punctuation it ends in
    # (szns stores whole pages as one line that happens to end in "-->").
    if not (len(s) > 300 and _cjk_ratio(s) >= 0.2):
        if _CODE_STRONG.search(s):
            return CODE
        if _CODE_WEAK.search(s) and _cjk_ratio(s) < 0.3:
            return CODE
    # SHORT = a link title / nav item. A clause (comma / semicolon) or a lead-in ending
    # in a colon is document text even when short: a decree listing what it repeals is
    # all short lines, and it must not be mistaken for a related-links list.
    if (len(s) <= SHORT_MAX and "。" not in s
            and not (len(s) > 20 and ("，" in s or "；" in s))
            and not (len(s) > 10 and s[-1] in "：:")):
        return SHORT
    return PROSE


_LINE_RE = re.compile(r"[^\r\n]*(?:\r\n|\n|\r|$)")


def _lines_with_offsets(body: str):
    """(offset, line) for every line; \\r, \\n and \\r\\n all end a line (mofcom pages
    use bare \\r, so splitting on \\n alone fuses a separator rule with 相关链接)."""
    out = []
    for m in _LINE_RE.finditer(body):
        if m.start() == len(body) and out:
            break
        out.append((m.start(), m.group(0)))
    return out


# Inline tails: the chrome sits on the SAME line as the text (gdny / gdstc / stic store
# a page as one line). A starter token, then nothing sentence-like to the end.
_INLINE_START = re.compile(
    r"(?:(?<=[\s　\xa0。！？”）)\]】])|^)"
    r"(扫一扫在手机打开当前页|分享到[:：]?|【打印[^】]{0,2}】|【关闭[^】]{0,2}】|打印本页|关闭窗口|"
    r"返回顶部|【纠错】|阅读下一篇|相关政策法规\s*/\s*解读[:：])"
    r"|(相关链接[：:])"            # gdstc writes "…2022年9月22日相关链接：《X》政策解读"
    r"|(?<=[\s。])(if\s*\(\s*\$\()")


def _inline_cut(text: str):
    """Earliest inline starter whose remainder to the end is short and has no 。."""
    stripped = text.rstrip(WS)
    lo = max(0, len(stripped) - INLINE_MAX)
    for m in _INLINE_START.finditer(stripped, lo):
        rest = stripped[m.start():]
        # same line only: real text that FOLLOWS a header share bar (nrta) is never cut
        if "。" not in rest and "\n" not in rest and "\r" not in rest and m.start() > 0:
            return m.start()
    return None


def find_tail(body: str):
    """Return (cut, kinds) where body[cut:] is a trailing chrome block, or None.

    `kinds` is the Counter of line classes inside the tail (for the report)."""
    if not body:
        return None
    lines = _lines_with_offsets(body)
    run = 0                  # SHORT chars since the last strong line (or the end)
    best = None              # earliest acceptable strong line index
    has_marker = False
    seen_strong = False
    i = len(lines) - 1
    while i >= 0:
        ln = lines[i][1]
        kind = classify_line(ln)
        if kind == PROSE:
            break
        if kind == SHORT:
            run += len(ln.strip(WS))
            if run > (SHORT_RUN_BUDGET if seen_strong else FINAL_RUN_BUDGET):
                break
        elif kind in (ANCHOR, NAV, CODE):
            if kind != CODE or any(t in ln for t in _CODE_SHARE):
                has_marker = True
            # A code-only tail (no widget/nav line) is out of scope; code BELOW the
            # first marker is still removed, because the cut takes everything after it.
            if has_marker:
                best = i
            run = 0
            seen_strong = True
        i -= 1
    kinds = Counter()
    if best is not None:
        cut = lines[best][0]
        kinds = Counter(classify_line(ln) for _, ln in lines[best:])
        kinds.pop(BLANK, None)
    else:
        cut = len(body)
    # inline tail on the line the cut leaves last (single-line pages, or text + chrome)
    ic = _inline_cut(body[:cut])
    if ic is not None:
        cut = ic
        kinds["inline"] += 1
    if cut >= len(body.rstrip(WS)):
        return None
    return cut, kinds


def meaningful_len(text: str) -> int:
    """CJK chars outside CODE/widget/nav lines (code is never 'real text'). ASCII is
    not counted, so a leftover attribute (class="view TRS_UEDITOR") is not text;
    an English body (>=200 ASCII letters) counts its letters instead."""
    n = a = 0
    for _, ln in _lines_with_offsets(text):
        if classify_line(ln) not in (CODE, ANCHOR, NAV):
            n += len(_CJK_RE.findall(ln))
            a += len(re.findall(r"[A-Za-z]", ln))
    return n if n or a < 200 else a


_PAGE_META = ("您的位置", "当前位置", "浏览次数", "访问量", "阅读：", "阅读:", "字号", "来源：", "来源:",
              "发布日期", "发布时间", "责任编辑", "索引号", "生成日期", "所属机构", "公开形式")


def is_all_chrome(kept: str) -> bool:
    """True when what is left after the cut is not a document text: fewer than
    MIN_KEPT meaningful chars, or a page HEADER only (no PROSE line, at least two
    page-metadata labels like 来源：/发布日期/浏览次数, and < 150 meaningful chars)."""
    m = meaningful_len(kept)
    if m < MIN_KEPT:
        return True
    if m < 150:
        kinds = {classify_line(ln) for _, ln in _lines_with_offsets(kept)}
        if PROSE not in kinds and sum(lab in kept for lab in _PAGE_META) >= 2:
            return True
    return False


def trim_text(body: str):
    """(kept_text, removed_tail, kinds) or None. kept + removed == body exactly."""
    hit = find_tail(body)
    if not hit:
        return None
    cut, kinds = hit
    kept = body[:cut].rstrip(WS)
    return kept, body[len(kept):], kinds


def markers_in(tail: str, kinds: Counter):
    found = [m for m in REPORT_MARKERS if m != "CODE(js/css)" and m in tail]
    if kinds.get(CODE):
        found.append("CODE(js/css)")
    return found


# ---------------------------------------------------------------------------
# Remedy decision
# ---------------------------------------------------------------------------

_router = None


def _reextract(site_key: str, raw_path: str, root: Path):
    global _router
    if not raw_path:
        return None, "no raw_html_path"
    f = root / raw_path
    if not f.exists():
        return None, "html file missing"
    import backfill_from_html as bf  # scripts/ on sys.path
    if _router is None:
        _router = bf._site_router()
    try:
        html = f.read_text(errors="replace")
        return bf.extract_for_site(site_key, html, _router) or "", "ok"
    except Exception as e:  # noqa: BLE001 — a crashing extractor falls back to trim
        return None, f"extractor error {type(e).__name__}"


def decide(body: str, site_key: str, raw_path: str, root: Path, allow_reextract=True):
    """Return a plan dict, or None when the body has no tail."""
    t = trim_text(body)
    if not t:
        return None
    kept, removed, kinds = t
    kept_m = meaningful_len(kept)
    all_chrome = is_all_chrome(kept)
    plan = {"kept": kept, "removed": removed, "kinds": kinds, "all_chrome": all_chrome,
            "kept_meaningful": kept_m, "reextract_status": "not tried"}
    if allow_reextract:
        new, status = _reextract(site_key, raw_path, root)
        plan["reextract_status"] = status
        if new is not None:
            new = new.strip(WS)
            new_m = meaningful_len(new)
            ok = (len(new) >= 50 and find_tail(new) is None and new_m >= MIN_KEPT
                  and new != body)
            if ok and not all_chrome:
                ok = 0.9 * kept_m <= new_m <= 1.5 * kept_m
            if ok:
                plan.update(method="reextract", new=new)
                return plan
            plan["reextract_status"] = ("reextract still has tail" if new and find_tail(new)
                                        else "reextract rejected (empty/short/length drift)")
    if all_chrome:
        plan.update(method="flagged", new=None)
    else:
        plan.update(method="trim", new=kept)
    return plan


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

PREFILTER_TOKENS = ["分享", "扫一扫", "打印", "关闭", "上一篇", "下一篇", "上一条", "下一条",
                    "相关链接", "相关文档", "相关解读", "相关文章", "相关内容",
                    "相关信息", "相关新闻", "相关阅读", "网站导航", "返回顶部", "返回网易首页",
                    "阅读下一篇", "QQ空间", "读取内容中"]
TAIL_WINDOW = 6000   # prefilter looks only at the last N chars (a tail is never longer)


def _connect_ro(db: Path):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _connect_rw(db: Path):
    conn = sqlite3.connect(str(db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS body_tail_trims (
        doc_id INTEGER NOT NULL, old_len INTEGER NOT NULL, new_len INTEGER NOT NULL,
        method TEXT NOT NULL, trimmed_at TEXT NOT NULL,
        removed_tail TEXT, old_body TEXT, reverted_at TEXT)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_body_tail_trims_doc ON body_tail_trims(doc_id)")
    conn.execute("""CREATE TABLE IF NOT EXISTS body_tail_flags (
        doc_id INTEGER PRIMARY KEY, reason TEXT NOT NULL, body_len INTEGER,
        tail_markers TEXT, flagged_at TEXT NOT NULL)""")
    conn.commit()


_PREFILTER_RE = re.compile("|".join(re.escape(t) for t in PREFILTER_TOKENS))


def iter_candidates(conn, sites=None, limit=0):
    """Rows whose last TAIL_WINDOW chars hold any prefilter token.

    The window is computed ONCE per row and matched in Python: 23 SQL
    instr(substr(body, -N), tok) calls re-walk each UTF-8 body 23 times (measured
    >8 min CPU on the droplet before it read a single HTML file). Full bodies are
    then fetched by id for the hits only."""
    sql = (f"SELECT id, substr(body_text_cn, -{TAIL_WINDOW}) FROM documents "
           f"WHERE body_text_cn IS NOT NULL AND body_text_cn != ''")
    params = []
    if sites:
        sql += f" AND site_key IN ({','.join('?' * len(sites))})"
        params += sites
    hits = [doc_id for doc_id, tail in conn.execute(sql, params)
            if tail and _PREFILTER_RE.search(tail)]
    hits.sort()
    if limit:
        hits = hits[:int(limit)]
    for k in range(0, len(hits), 500):
        chunk = hits[k:k + 500]
        q = ",".join("?" * len(chunk))
        yield from conn.execute(
            f"SELECT id, site_key, body_text_cn, COALESCE(raw_html_path,'') FROM documents "
            f"WHERE id IN ({q}) ORDER BY id", chunk).fetchall()


def _norm_ref(s: str) -> str:
    return re.sub(r"[《》〈〉<>\s　\xa0]", "", s or "")


def tail_citations(conn, doc_id: int, kept: str, removed: str):
    """Outbound edges whose target_ref text occurs ONLY inside the removed tail."""
    out = Counter()
    nk, nr = _norm_ref(kept), _norm_ref(removed)
    for ref, ctype, tid in conn.execute(
            "SELECT target_ref, citation_type, target_id FROM citations WHERE source_id=?", (doc_id,)):
        r = _norm_ref(ref)
        if len(r) >= 3 and r in nr and r not in nk:
            out[(ctype, "resolved" if tid else "unresolved")] += 1
    return out


def _share_bucket(frac: float) -> str:
    for hi, lab in ((0.02, "<2%"), (0.05, "2-5%"), (0.10, "5-10%"), (0.25, "10-25%"),
                    (0.50, "25-50%"), (0.90, "50-90%")):
        if frac < hi:
            return lab
    return ">=90%"


def _show(s: str, n=80) -> str:
    return repr(s[-n:]) if s else "''"


def run(db: Path, root: Path, apply=False, sites=None, limit=0, allow_reextract=True,
        sample_n=20, seed=7, report_json=None, dump_tsv=None):
    conn = _connect_rw(db) if apply else _connect_ro(db)
    if apply:
        ensure_schema(conn)
    # citation measurement reads from the same DB (read-only either way)
    by_method, by_site, by_marker = Counter(), defaultdict(Counter), Counter()
    marker_site = defaultdict(Counter)
    share = defaultdict(Counter)
    reex_status = Counter()
    cit = Counter()
    cit_docs = 0
    samples = []
    scanned = 0
    t0 = time.time()

    from crawlers.base import WriteRetryStats, commit_with_retry, write_with_retry
    stats = WriteRetryStats()
    written = flagged = lost = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rng = random.Random(seed)
    dump = open(dump_tsv, "w") if dump_tsv else None
    if dump:
        dump.write("doc_id\tsite\tmethod\told_len\tnew_len\ttail_share\tmarkers\ttail_cites"
                   "\treextract_status\tkept_end\tremoved_head\n")

    for doc_id, site, body, raw_path in iter_candidates(conn, sites, limit):
        scanned += 1
        plan = decide(body, site, raw_path, root, allow_reextract)
        if not plan:
            continue
        m = plan["method"]
        by_method[m] += 1
        by_site[site][m] += 1
        reex_status[plan["reextract_status"]] += 1
        mk = markers_in(plan["removed"], plan["kinds"])
        for x in mk:
            by_marker[x] += 1
            marker_site[x][site] += 1
        share[("all-chrome" if plan["all_chrome"] else "suffix")][
            _share_bucket(len(plan["removed"]) / max(1, len(body)))] += 1
        tc = tail_citations(conn, doc_id, plan["kept"], plan["removed"])
        if tc:
            cit_docs += 1
            cit.update(tc)
        if dump:
            clean = lambda x: x.replace("\t", " ").replace("\r", " ").replace("\n", "⏎")  # noqa: E731
            dump.write(f"{doc_id}\t{site}\t{m}\t{len(body)}\t{len(plan['new'] or '')}\t"
                       f"{len(plan['removed']) / max(1, len(body)):.3f}\t{','.join(mk)}\t"
                       f"{sum(tc.values())}\t{plan['reextract_status']}\t"
                       f"{clean(plan['kept'][-60:])}\t{clean(plan['removed'][:120])}\n")
        # reservoir sample, stratified a little: keep every method represented
        rec = (doc_id, site, m, len(body), len(plan["new"] or ""), body, plan["new"])
        if len(samples) < sample_n:
            samples.append(rec)
        elif rng.random() < sample_n / max(1, sum(by_method.values())):
            samples[rng.randrange(sample_n)] = rec

        if apply:
            if m == "flagged":
                ok = write_with_retry(
                    conn, "INSERT OR REPLACE INTO body_tail_flags VALUES (?,?,?,?,?)",
                    (doc_id, "all_chrome", len(body), ",".join(mk), now), stats=stats,
                    what=f"trim_body_tails flag id={doc_id}")
                flagged += ok
            else:
                new = plan["new"]
                assert new and len(new.strip(WS)) > 0, "refusing to write an empty body"
                before = conn.total_changes
                ok = write_with_retry(
                    conn, "UPDATE documents SET body_text_cn=? WHERE id=? AND body_text_cn=?",
                    (new, doc_id, body), stats=stats, what=f"trim_body_tails id={doc_id} site={site}")
                if ok and conn.total_changes != before:
                    removed_tail = body[len(new):] if m == "trim" else None
                    write_with_retry(
                        conn, "INSERT INTO body_tail_trims (doc_id, old_len, new_len, method, "
                              "trimmed_at, removed_tail, old_body) VALUES (?,?,?,?,?,?,?)",
                        (doc_id, len(body), len(new), m, now, removed_tail,
                         body if m != "trim" else None), stats=stats,
                        what=f"trim_body_tails audit id={doc_id}")
                    written += 1
                elif ok:
                    lost += 1   # body changed under us since the scan; left alone
                if written and written % 200 == 0:
                    commit_with_retry(conn, what=f"trim_body_tails @{written}")
                if written and written % 1000 == 0:
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    print(f"  …{written} written ({time.time() - t0:.0f}s)", flush=True)
    if dump:
        dump.close()
    if apply:
        commit_with_retry(conn, what="trim_body_tails final")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    total = sum(by_method.values())
    print(f"\nScanned {scanned} prefiltered bodies in {time.time() - t0:.0f}s; "
          f"{total} carry a trailing chrome block.")
    print(f"\nRemedy: " + ", ".join(f"{k}={v}" for k, v in by_method.most_common()))
    print(f"  suffix on real text = {sum(share['suffix'].values())}, "
          f"all-chrome = {sum(share['all-chrome'].values())} "
          f"(all-chrome rows that re-extraction rescued count under reextract, the rest are flagged)")
    print("\nRe-extraction outcome: " + ", ".join(f"{k}={v}" for k, v in reex_status.most_common()))
    print("\nTail share of body (removed chars / body chars):")
    labs = ["<2%", "2-5%", "5-10%", "10-25%", "25-50%", "50-90%", ">=90%"]
    print(f"  {'class':12s} " + " ".join(f"{b:>7s}" for b in labs))
    for cls in ("suffix", "all-chrome"):
        print(f"  {cls:12s} " + " ".join(f"{share[cls][b]:7d}" for b in labs))
    print("\nBy marker found in the tail (a row counts once per marker):")
    for x, c in by_marker.most_common():
        top = ", ".join(f"{s} {n}" for s, n in marker_site[x].most_common(5))
        print(f"  {x:22s} {c:7d}   {top}")
    print("\nBy site:")
    print(f"  {'site':16s} {'total':>6s} {'reextract':>9s} {'trim':>6s} {'flagged':>7s}")
    for s, c in sorted(by_site.items(), key=lambda kv: -sum(kv[1].values()))[:60]:
        print(f"  {s:16s} {sum(c.values()):6d} {c['reextract']:9d} {c['trim']:6d} {c['flagged']:7d}")
    if len(by_site) > 60:
        print(f"  … {len(by_site) - 60} more sites")
    print(f"\nOutbound citation edges whose reference text occurs ONLY inside the tail: "
          f"{sum(cit.values())} edges on {cit_docs} docs")
    for (ct, rs), c in sorted(cit.items()):
        print(f"  {ct:7s} {rs:10s} {c}")
    print(f"\nSample ({len(samples)} rows; last 80 chars before → after):")
    for doc_id, site, m, ol, nl, old, new in sorted(samples, key=lambda r: r[2]):
        print(f"  [{m}] id={doc_id} site={site} {ol}→{nl}")
        print(f"      before: {_show(old)}")
        print(f"      after : {_show(new) if new else '(unchanged — flagged)'}")
    if apply:
        print(f"\nAPPLIED: {written} bodies changed, {flagged} flagged, {lost} skipped because the "
              f"body changed since the scan, {stats.retried} lock retries, {stats.skipped} skipped on lock.")
    else:
        print("\nDRY RUN — nothing written (read-only connection).")
    if report_json:
        Path(report_json).write_text(json.dumps({
            "by_method": by_method, "by_site": by_site, "by_marker": by_marker,
            "share": share, "citations": {f"{a}|{b}": c for (a, b), c in cit.items()},
            "citation_docs": cit_docs, "reextract_status": reex_status,
        }, ensure_ascii=False, indent=1, default=dict))
    conn.close()
    return {"candidates": total, "written": written, "flagged": flagged,
            "skipped": stats.skipped, "by_method": dict(by_method)}


def revert(db: Path):
    conn = _connect_rw(db)
    ensure_schema(conn)
    from crawlers.base import WriteRetryStats, commit_with_retry, write_with_retry
    stats = WriteRetryStats()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = conn.execute("SELECT rowid, doc_id, new_len, method, removed_tail, old_body "
                        "FROM body_tail_trims WHERE reverted_at IS NULL ORDER BY rowid DESC").fetchall()
    done = 0
    for rid, doc_id, new_len, method, removed, old_body in rows:
        cur = conn.execute("SELECT body_text_cn FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not cur or len(cur[0] or "") != new_len:
            continue   # changed since; do not clobber
        old = cur[0] + removed if method == "trim" else old_body
        if write_with_retry(conn, "UPDATE documents SET body_text_cn=? WHERE id=? AND body_text_cn=?",
                            (old, doc_id, cur[0]), stats=stats, what=f"revert id={doc_id}"):
            write_with_retry(conn, "UPDATE body_tail_trims SET reverted_at=? WHERE rowid=?",
                             (now, rid), stats=stats)
            done += 1
        if done and done % 200 == 0:
            commit_with_retry(conn, what="trim_body_tails revert")
    commit_with_retry(conn, what="trim_body_tails revert final")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    print(f"Reverted {done} of {len(rows)} audited changes ({stats.skipped} skipped on lock).")
    return stats.skipped


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="read-only report + sample")
    g.add_argument("--apply", action="store_true", help="write trims/re-extractions + audit")
    g.add_argument("--revert", action="store_true", help="undo every audited change")
    p.add_argument("--db", default=os.environ.get("SQLITE_PATH", str(ROOT / "documents.db")))
    p.add_argument("--root", default=str(ROOT), help="repo root holding raw_html/")
    p.add_argument("--site", action="append", help="limit to site_key (repeatable)")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--no-reextract", action="store_true", help="tail-trim only, never read HTML")
    p.add_argument("--sample", type=int, default=20)
    p.add_argument("--report-json")
    p.add_argument("--dump-tsv", help="one row per tailed doc (id, site, method, lengths, markers…)")
    p.add_argument("--force", action="store_true", help="run even while the nightly lock exists")
    a = p.parse_args(argv)
    if (a.apply or a.revert) and LOCK_DIR.exists() and not a.force:
        print(f"REFUSING: {LOCK_DIR} exists (daily_sync is running). Re-run after it finishes, "
              f"or pass --force if the lock is stale.")
        return 2
    db = Path(a.db)
    if a.revert:
        return 1 if revert(db) else 0
    res = run(db, Path(a.root), apply=a.apply, sites=a.site, limit=a.limit,
              allow_reextract=not a.no_reextract, sample_n=a.sample, report_json=a.report_json,
              dump_tsv=a.dump_tsv)
    if res["skipped"]:
        print(f"FAILED: {res['skipped']} writes were not stored (DB locked). Re-run to finish.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
