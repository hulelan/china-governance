#!/usr/bin/env python3
"""
topic_typer.py — rule-based Chinese-government document TOPIC (subject) classifier.

WHY THIS EXISTS
---------------
We already tag every doc with a GENRE (`algo_doc_type` / genre_typer.py: 通知,
规定, 意见 …) — WHAT KIND of document it is. This module adds the ORTHOGONAL
axis: WHAT it is ABOUT. It multi-labels each doc with 0..N of 29 policy-topic
categories (Energy, Health, Education, Party, Legal, …).

The 29 categories are adopted VERBATIM from reconnectchina.org's policy-topic
facet, so our subject facet aligns 1:1 with theirs. The vocabulary lives in
`data/topic_ontology.yaml` (one curated keyword/phrase list per category); this
module is just the matcher + CLI. Editing the taxonomy = editing the YAML.

Multi-label is expected and correct: 新能源汽车充电设施 → Energy + Transport +
Infrastructure; a 医保基金监管 doc → Health + Finance.

DESIGN / PRECISION
------------------
  - Pure function of text. `classify(title, keywords='', body='')` compiles each
    category's patterns into one alternation regex, counts how many DISTINCT
    patterns hit, and returns the matched category ids ordered by that count
    (strongest subject first), tie-broken by the YAML order.
  - Title + keywords are the default haystack (fast; body optional). On the live
    corpus `keywords` is populated on only ~20% of docs, so title carries most of
    the signal — the patterns were tuned against real titles for that reason.
    CAVEAT: on COMMERCIAL-MEDIA articles (ifeng/36kr/…) the `keywords` field is a
    noisy auto-tag bag (e.g. a phone-review doc tagged 台湾省/中国/论坛), which can
    inject spurious topics. Gov-doc keywords are clean. If precision on news
    matters, pass keywords='' for media sites (they're excludable anyway via the
    source ontology's "exclude news" branch) or gate keyword use on admin_level.
  - The ontology AVOIDS issuer-organ words that ride on nearly every title
    (政府/人民政府/办公厅) and bare colliding chars (安全/法/卫生); see the header
    of data/topic_ontology.yaml for the precision rules. Net effect: high
    coverage with low spurious tagging.

HOW TO WIRE IT IN LATER  (do NOT auto-apply — left for a human; I own only this
file + the YAML)
--------------------------------------------------------------------------------
STORAGE — recommended: a stored `topics_algo` TEXT column (comma-joined ids),
computed by a pass mirroring scripts/compute_scores.py:

  1. `ALTER TABLE documents ADD COLUMN topics_algo TEXT DEFAULT '';`
     (+ optionally `CREATE INDEX idx_documents_topics ON documents(topics_algo);`
      note: a plain index only helps prefix/equality; for facet COUNTs prefer the
      FTS approach below or a join table.)
  2. In a compute pass, SELECT id, title, COALESCE(keywords,'') and set
     topics_algo = ','.join(classify(title, keywords)). Diff-and-update only
     rows whose value CHANGED (same score-preserving pattern compute_scores.py
     already uses — see its 2026-08-10 note) so a re-run writes only deltas.
  3. Recompute in daily_sync.sh alongside compute_scores.py Phase 2 (pure CPU,
     no LLM, ~seconds for a day's new docs). classify() is title-only by default
     so it needs no body read.

  Why a comma-joined column over a join table: the corpus is single-writer
  SQLite and the app already reads flat columns; a `documents.topics_algo LIKE
  '%Energy%'` facet is simple and index-free-scan is ~0.1s on 284k rows warm.
  If facet COUNTs get hot, add a contentless FTS5 index over topics_algo (like
  doc_search) or a `doc_topics(doc_id, topic)` join table for exact-match counts.

FACETING IN THE WEB APP (web/services/lens.py + browse) — NOT edited here:
  - Lens breakdowns: add a "by topic" bar next to the existing admin-level/genre
    breakdowns, GROUP BY over the split topics_algo.
  - Browse/search filter: a topic dropdown → `WHERE topics_algo LIKE '%'||?||'%'`
    (or the FTS/join variant). Because it's multi-label, treat it as an additive
    filter (AND across chosen topics) rather than mutually exclusive like genre.

CLI
---
    python3 scripts/rnd/classification/topic_typer.py --self-test
    python3 scripts/rnd/classification/topic_typer.py --sample 8000
        # ssh a random N-row sample off the droplet (title+keywords, read-only)
        # and report coverage (% with >=1 topic) + the per-topic distribution +
        # a spot-check sample of taggings.
    python3 scripts/rnd/classification/topic_typer.py --sample 8000 --show 40
        # also print 40 example taggings for a manual precision check.
    python3 scripts/rnd/classification/topic_typer.py --tsv path.tsv
        # score a local id\ttitle\tkeywords TSV (offline; no ssh).
"""
from __future__ import annotations

import html as _html
import re
import sys
from pathlib import Path

# Repo root: scripts/rnd/classification/topic_typer.py -> parents[3]
_ROOT = Path(__file__).resolve().parents[3]
_ONTOLOGY_PATH = _ROOT / "data" / "topic_ontology.yaml"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    if not text:
        return ""
    t = _html.unescape(text)
    t = _TAG_RE.sub(" ", t)
    t = t.replace("　", " ")  # ideographic space
    return _WS_RE.sub(" ", t).strip()


# --------------------------------------------------------------------------
# Load the ontology. One compiled alternation regex per category, PLUS the raw
# pattern list so we can count DISTINCT hits (for ordering by match strength).
# --------------------------------------------------------------------------

def _load_ontology(path: Path = _ONTOLOGY_PATH):
    """Return [(category_id, [compiled_pattern, ...]), ...] in YAML order.

    Uses PyYAML if available; else a tiny fallback parser for this file's simple
    shape (so the module works on a box without pyyaml).
    """
    text = path.read_text(encoding="utf-8")
    data = None
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
    except Exception:
        data = _mini_parse(text)
    cats = []
    for cat in data["categories"]:
        cid = cat["id"]
        pats = [re.compile(p) for p in cat.get("patterns", [])]
        cats.append((cid, pats))
    return cats


def _mini_parse(text: str):
    """Minimal parser for the fixed topic_ontology.yaml shape (no pyyaml).

    Recognizes:  `  - id: X` then following `      - <pattern>` list items under
    a `patterns:` key. Comments (#) and other scalar keys are ignored.
    """
    categories = []
    cur = None
    in_patterns = False
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m_id = re.match(r"-\s*id:\s*(\S+)", s)
        if m_id:
            cur = {"id": m_id.group(1).strip(), "patterns": []}
            categories.append(cur)
            in_patterns = False
            continue
        if s.startswith("patterns:"):
            in_patterns = True
            continue
        if re.match(r"(label_zh|label_en|version):", s):
            in_patterns = False
            continue
        if in_patterns and s.startswith("- ") and cur is not None:
            pat = s[2:].strip()
            # strip optional surrounding quotes
            if len(pat) >= 2 and pat[0] == pat[-1] and pat[0] in "'\"":
                pat = pat[1:-1]
            if pat:
                cur["patterns"].append(pat)
    return {"categories": [c for c in categories if c["patterns"]]}


_CATEGORIES = _load_ontology()
CATEGORY_IDS = [cid for cid, _ in _CATEGORIES]


def classify(title: str, keywords: str = "", body: str = "") -> list[str]:
    """Return the matched topic-category ids for a document.

    Ordered by match STRENGTH (number of distinct patterns that hit), then by
    ontology order. Pure function; never raises on bad input. Empty list means
    "no topic matched" (some docs legitimately have none — a bare leader-activity
    readout, a procurement notice with no subject term).
    """
    hay = _clean(title)
    if keywords:
        hay += " " + _clean(keywords)
    if body:
        hay += " " + _clean(body)
    if not hay:
        return []
    scored = []
    for idx, (cid, pats) in enumerate(_CATEGORIES):
        hits = 0
        for rx in pats:
            if rx.search(hay):
                hits += 1
        if hits:
            scored.append((-hits, idx, cid))
    scored.sort()
    return [cid for _, _, cid in scored]


# --------------------------------------------------------------------------
# Self-test — hand-labeled examples. Each expects a SET of REQUIRED labels that
# must ALL be present in classify()'s output (multi-label; extra labels allowed
# unless listed in `forbid`).
# --------------------------------------------------------------------------

_SELF_TESTS = [
    # (title, keywords, required_labels, forbidden_labels)
    ("《可再生能源发展“十五五”规划》发布", "", {"Energy"}, set()),
    ("广东省渔业管理条例", "", {"Agriculture"}, set()),
    ("河北省食品小作坊小餐饮小摊点管理条例", "", {"Safety"}, set()),
    ("西安市道路交通安全条例", "", {"Transport", "Safety"}, set()),
    ("河南省公共安全技术防范管理条例", "", {"Security"}, set()),
    ("贵州省通信管理局启动2026年反电信网络诈骗法落实情况检查", "", {"Security"}, set()),
    ("民政部 国家乡村振兴局关于动员引导社会组织参与乡村振兴工作的通知", "",
     {"Agriculture", "Welfare"}, set()),
    ("深圳市住房保障署面向人才配售住房通告", "", {"Housing"}, set()),
    ("关于颁发珠海市第二届哲学社会科学优秀成果奖的决定", "", {"Awards"}, set()),
    # no algorithmic Tech keyword (产业生态 is a false friend); assert we DON'T
    # mistag it Environment off bare 生态 (removed from the ontology for that reason)
    ("云天励飞携手产业链推进国产推理生态建设", "", set(), {"Environment"}),
    ("倒计时1天 | 来服贸会参加一场贯穿AI与算力全景生态的活动", "模型,技术,互联网",
     {"Tech"}, set()),
    ("浙江省科学技术厅关于强化企业科技创新主体地位加快科技企业高质量发展的实施意见", "",
     {"Tech"}, set()),
    ("2025年广东省商务厅部门预算", "", {"Finance"}, set()),
    ("国台办：赖清德已成为“台湾之害”", "", {"Diplomacy"}, set()),
    ("中共深圳市民政局党组关于邢享明同志任职的通知", "深民党组任〔2022〕20号",
     {"Personnel"}, set()),
    ("关于优化完善无线电频率占用费标准的通知", "", set(), {"Sports", "Weather"}),
    ("市委常委会召开会议", "", set(), set()),  # no strong subject; empty OK
    ("荒漠化防治边会在COP17“中国角”举行", "", {"Environment"}, set()),
    ("我市举行金融助力乡村酒店（民宿）暨农文旅高质量发展融资对接会", "",
     {"Finance", "Tourism"}, set()),
    ("深圳市公安局交通警察局关于注销驾驶证公告", "", {"Transport"}, set()),
    ("关于加快我省优势传统产业转型升级的意见", "", set(), set()),
    ("退役军人事务部关于做好优抚对象抚恤补助的通知", "", {"Veterans"}, set()),
    ("台风“杜苏芮”防御工作气象预警", "", {"Weather"}, set()),
    ("广东省第十五届运动会闭幕", "", {"Sports"}, set()),
    ("国家卫生健康委关于印发医疗机构管理条例的通知", "", {"Health"}, set()),
    ("中共中央关于全面从严治党加强党风廉政建设的意见", "", {"Party"}, set()),
    ("最高人民法院关于知识产权民事诉讼证据的若干规定", "", {"Legal"}, set()),
    ("海关总署关于优化跨境电商进出口监管的公告", "", {"Trade"}, set()),
]


def _self_test() -> bool:
    ok = 0
    for title, kw, req, forbid in _SELF_TESTS:
        got = set(classify(title, kw))
        miss = req - got
        bad = forbid & got
        passed = not miss and not bad
        if passed:
            ok += 1
        else:
            detail = []
            if miss:
                detail.append(f"MISSING {sorted(miss)}")
            if bad:
                detail.append(f"FORBIDDEN {sorted(bad)}")
            print(f"XX  {'; '.join(detail):40s} got={sorted(got)} | {title[:40]}")
    print(f"\nself-test: {ok}/{len(_SELF_TESTS)} passed")
    return ok == len(_SELF_TESTS)


# --------------------------------------------------------------------------
# Sample report
# --------------------------------------------------------------------------

def _report(rows, show=0):
    """rows: iterable of (id, title, keywords). Print coverage + distribution."""
    from collections import Counter
    n = 0
    tagged = 0
    per_topic = Counter()
    label_count = Counter()  # how many topics per doc
    examples = []
    for _id, title, kw in rows:
        n += 1
        topics = classify(title, kw)
        if topics:
            tagged += 1
            for t in topics:
                per_topic[t] += 1
            label_count[len(topics)] += 1
        else:
            label_count[0] += 1
        if show and len(examples) < show:
            examples.append((_id, topics, title))
    if n == 0:
        print("no rows")
        return
    print(f"\nSample size                 : {n:,}")
    print(f"Docs with >=1 topic         : {tagged:,}  ({tagged/n*100:.1f}%)")
    print(f"Docs with NO topic          : {n-tagged:,}  ({(n-tagged)/n*100:.1f}%)")
    print("\nLabels-per-doc distribution:")
    for k in sorted(label_count):
        print(f"  {k} topic(s): {label_count[k]:6,}  ({label_count[k]/n*100:.1f}%)")
    print(f"\nPer-topic distribution (doc counts; sums >100% — multi-label):")
    for cid in CATEGORY_IDS:  # stable order, then show count
        c = per_topic.get(cid, 0)
        bar = "#" * int(c / n * 100)
        print(f"  {cid:14s} {c:6,}  ({c/n*100:5.1f}%)  {bar}")
    if show and examples:
        print(f"\n--- {len(examples)} example taggings (spot-check) ---")
        for _id, topics, title in examples:
            print(f"  [{','.join(topics) if topics else '—':30s}] {title[:60]}")


def _fetch_sample(host, n):
    import subprocess
    sql = (
        "SELECT id, title, COALESCE(keywords,'') FROM documents "
        f"WHERE title != '' ORDER BY RANDOM() LIMIT {int(n)};"
    )
    cmd = ["ssh", host,
           f"cd /root/china-governance && sqlite3 documents.db \".mode tabs\" \"{sql}\""]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if out.returncode != 0:
        sys.stderr.write(out.stderr)
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            _id = parts[0]
            title = parts[1]
            kw = parts[2] if len(parts) >= 3 else ""
            rows.append((_id, title, kw))
    return rows


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--sample", type=int, metavar="N",
                    help="ssh a random N-row sample off the droplet and report")
    ap.add_argument("--tsv", metavar="PATH",
                    help="score a local id\\ttitle\\tkeywords TSV (offline)")
    ap.add_argument("--show", type=int, default=0,
                    help="print this many example taggings for a spot check")
    ap.add_argument("--host", default="root@104.236.88.45")
    args = ap.parse_args(argv)

    if args.self_test:
        return 0 if _self_test() else 1

    if args.tsv:
        rows = []
        with open(args.tsv, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    rows.append((parts[0], parts[1], parts[2] if len(parts) >= 3 else ""))
        _report(rows, show=args.show)
        return 0

    if args.sample:
        rows = _fetch_sample(args.host, args.sample)
        _report(rows, show=args.show)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
