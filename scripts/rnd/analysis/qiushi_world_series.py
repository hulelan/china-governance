"""Qiushi world-vocabulary time series (docs/research/qiushi-world-vocabulary.md).

A fixed-source, issue-by-issue journal is a time series whose denominator is the
journal, not our crawler. This script counts, per year (and per issue for 求是),
the share of articles using each world concept, split Xi-authored vs other for
求是, and replicates on 光明日报 theory pages and 人民论坛.

Phases (all READ-ONLY; open the DB with ?mode=ro):
  --phase denoms    articles per issue / year, short bodies, duplicates (no terms)
  --phase count     concept shares (the pre-registered test, prereg-qiushi-world.md)
  --phase examples  dated example sentences for turning points (substring-verified)

Run on the droplet against a copy of web/services/discourse_vocab.py:
  mkdir -p /tmp/qs_ts && cp this file + discourse_vocab.py there
  .venv/bin/python3 /tmp/qs_ts/qiushi_world_series.py --db documents.db --phase count
Counting is plain Python regex on title + body, so no FTS length floor applies.
"""
import argparse, json, re, sqlite3, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import discourse_vocab as V          # /tmp/qs_ts copy on the droplet
except ImportError:                      # repo layout on the Mac
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "web" / "services"))
    import discourse_vocab as V

SITES = ["qiushi", "hongqi", "gmrb_theory", "rmlt"]
MIN_BODY = 200          # drops 国家统计局 统计图表 rows (body 0) and stubs

# Frozen in prereg-qiushi-world.md. Regexes reused from discourse_vocab where the
# concept exists there, so this memo and the tracker count the same thing.
TERMS = {
    # mission vocabulary
    "命运共同体": V.C["命运共同体"],
    "全球倡议(任一)": r"全球(?:发展|安全|文明|治理)倡议|[三四]大全球倡议",
    "GDI": V.C["GDI发展倡议"], "GSI": V.C["GSI安全倡议"],
    "GCI": V.C["GCI文明倡议"], "GGI": V.C["GGI治理倡议"],
    "全人类共同价值": V.C["全人类共同价值"],
    "胸怀天下": V.C["胸怀天下"],
    "世界眼光": r"世界眼光",
    # threat vocabulary
    "百年变局": V.C["百年变局"],                 # 百年(?:未有之)?大?变局, catches 世界百年变局
    "动荡变革期": r"动荡变革期",
    "霸权主义": V.C["霸权主义"],
    "敢于斗争": r"敢于斗争|善于斗争|斗争精神|伟大斗争",
    "斗争(裸)": r"斗争",
    "总体国家安全观": r"总体国家安全观",
    "国家安全": r"国家安全",
    # order / other
    "全球南方": V.C["全球南方"],
    "多极化": V.C["多极化"],
    "平等有序多极化": V.PH["平等有序的(世界)多极化"],
    "中国式现代化": V.C["中国式现代化"],
    "人类文明新形态": V.C["人类文明新形态"],
}
RX = {k: re.compile(v) for k, v in TERMS.items()}
# Pre-registered indices (any member present)
MISSION = ["命运共同体", "全球倡议(任一)", "全人类共同价值", "胸怀天下"]
THREAT = ["百年变局", "动荡变革期", "霸权主义", "敢于斗争", "总体国家安全观"]
# Mission without the initiatives, because the initiatives did not exist before 2021-09
# and their arrival mechanically raises the mission index (registered as M2).
MISSION_NOINIT = ["命运共同体", "全人类共同价值", "胸怀天下"]
# Threat without 斗争 family, the term most tied to one domestic campaign (registered T2).
THREAT_WORLD = ["百年变局", "动荡变革期", "霸权主义"]

ISSUE_RX = re.compile(r"issue=求是(\d{4})/(\d{1,2})")
AUTH_RX = re.compile(r"author=([^;]*)")


def rows(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = ("SELECT id, site_key, title, date_published, relation, COALESCE(body_text_cn,'') "
         "FROM documents WHERE site_key IN (%s)" % ",".join("?" * len(SITES)))
    for r in con.execute(q, SITES):
        yield r


def meta(site, title, date, relation):
    year = (date or "")[:4]
    issue = None
    m = ISSUE_RX.search(relation or "")
    if m:
        issue = f"{m.group(1)}/{int(m.group(2)):02d}"
        year = m.group(1)
    a = AUTH_RX.search(relation or "")
    author = a.group(1).strip() if a else ""
    xi = site == "qiushi" and (author == "习近平" or (title or "").startswith("习近平："))
    return year, issue, author, xi


def load(db):
    """Deduped docs: one copy per (site, normalized title, year)."""
    seen = {}
    dup = Counter()
    for did, site, title, date, rel, body in rows(db):
        year, issue, author, xi = meta(site, title, date, rel)
        key = (site, re.sub(r"\s+", "", title or ""), year)
        if key in seen:
            dup[site] += 1
            if len(body) <= len(seen[key]["body"]):
                continue
        seen[key] = dict(id=did, site=site, title=title or "", date=date, year=year,
                         issue=issue, author=author, xi=xi, body=body)
    return list(seen.values()), dup


def phase_denoms(docs, dup):
    out = {"dups_dropped": dict(dup)}
    for site in SITES:
        per = defaultdict(lambda: [0, 0])
        for d in docs:
            if d["site"] != site: continue
            per[d["year"]][0] += 1
            per[d["year"]][1] += len(d["body"]) >= MIN_BODY
        out[site] = {y: per[y] for y in sorted(per)}
    iss = defaultdict(Counter)
    for d in docs:
        if d["site"] == "qiushi" and d["issue"] and len(d["body"]) >= MIN_BODY:
            iss[d["issue"][:4]][d["issue"]] += 1
    qi = {}
    for y in sorted(iss):
        c = iss[y]
        nums = sorted(int(k[5:]) for k in c)
        exp = 24 if y != "2026" else max(nums)
        qi[y] = dict(issues=len(c), missing=[n for n in range(1, exp + 1) if n not in nums],
                     min=min(c.values()), max=max(c.values()),
                     mean=round(sum(c.values()) / len(c), 1),
                     xi=sum(1 for d in docs if d["site"] == "qiushi" and d["year"] == y and d["xi"]
                            and len(d["body"]) >= MIN_BODY),
                     xi_issues=len({d["issue"] for d in docs if d["site"] == "qiushi" and d["year"] == y
                                    and d["xi"]}),
                     chars_median=sorted(len(d["body"]) for d in docs if d["site"] == "qiushi"
                                         and d["year"] == y and len(d["body"]) >= MIN_BODY)[
                                             len([1 for d in docs if d["site"] == "qiushi" and d["year"] == y
                                                  and len(d["body"]) >= MIN_BODY]) // 2])
    out["qiushi_issues"] = qi
    out["qiushi_low_issues"] = sorted((k, v) for y in iss for k, v in iss[y].items() if v <= 6)
    return out


def hits(d):
    text = d["title"] + "\n" + d["body"]
    return {k for k, rx in RX.items() if rx.search(text)}


def phase_count(docs):
    res = {}
    groups = {s: (lambda d, s=s: d["site"] == s) for s in SITES}
    groups["qiushi_xi"] = lambda d: d["site"] == "qiushi" and d["xi"]
    groups["qiushi_other"] = lambda d: d["site"] == "qiushi" and not d["xi"]
    for g, pred in groups.items():
        tab = defaultdict(Counter)
        chars = Counter()
        occ = defaultdict(Counter)
        for d in docs:
            if not pred(d) or len(d["body"]) < MIN_BODY: continue
            y = d["year"]
            h = hits(d)
            tab[y]["_n"] += 1
            chars[y] += len(d["body"])
            for k in h: tab[y][k] += 1
            if h & set(MISSION): tab[y]["MISSION"] += 1
            if h & set(THREAT): tab[y]["THREAT"] += 1
            if h & set(MISSION_NOINIT): tab[y]["MISSION_NOINIT"] += 1
            if h & set(THREAT_WORLD): tab[y]["THREAT_WORLD"] += 1
            text = d["title"] + "\n" + d["body"]
            for k in ("命运共同体", "百年变局", "动荡变革期", "霸权主义", "敢于斗争", "国家安全",
                      "全人类共同价值", "胸怀天下", "全球倡议(任一)"):
                occ[y][k] += len(RX[k].findall(text))
        res[g] = {y: dict(tab[y], _chars=chars[y], _occ=dict(occ[y])) for y in sorted(tab)}
    # qiushi per issue (indices only)
    per = defaultdict(Counter)
    for d in docs:
        if d["site"] != "qiushi" or not d["issue"] or len(d["body"]) < MIN_BODY: continue
        h = hits(d)
        per[d["issue"]]["_n"] += 1
        for k in h: per[d["issue"]][k] += 1
        if h & set(MISSION): per[d["issue"]]["MISSION"] += 1
        if h & set(THREAT): per[d["issue"]]["THREAT"] += 1
    res["qiushi_issue"] = {k: dict(per[k]) for k in sorted(per)}
    return res


def phase_examples(docs, terms, per_year=2):
    """Earliest dated sentences per term per site, verified as substrings of the body."""
    out = defaultdict(list)
    for d in sorted(docs, key=lambda d: (d["date"] or "")):
        if d["site"] not in ("qiushi",) or len(d["body"]) < MIN_BODY: continue
        for k in terms:
            m = RX[k].search(d["body"])
            if not m: continue
            if sum(1 for e in out[k] if e["year"] == d["year"]) >= per_year: continue
            s = max(d["body"].rfind("。", 0, m.start()) + 1, m.start() - 120)
            e = d["body"].find("。", m.end())
            e = m.end() + 120 if e < 0 or e - m.end() > 160 else e + 1
            sent = d["body"][s:e].strip()
            assert sent in d["body"]
            out[k].append(dict(id=d["id"], date=d["date"], year=d["year"], issue=d["issue"],
                               xi=d["xi"], author=d["author"], title=d["title"], sent=sent))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="documents.db")
    ap.add_argument("--phase", choices=["denoms", "count", "examples"], required=True)
    ap.add_argument("--terms", default="动荡变革期,百年变局,霸权主义,全球南方,敢于斗争,胸怀天下,全人类共同价值")
    ap.add_argument("--out")
    a = ap.parse_args()
    docs, dup = load(a.db)
    if a.phase == "denoms":
        r = phase_denoms(docs, dup)
    elif a.phase == "count":
        r = phase_count(docs)
    else:
        r = phase_examples(docs, a.terms.split(","))
    s = json.dumps(r, ensure_ascii=False, indent=1)
    if a.out: Path(a.out).write_text(s)
    else: print(s)


if __name__ == "__main__":
    main()
