"""Qin, Stromberg & Wu (2018, AER 108(9)) "Media Bias in China": the content-gap logic on our
speaker types. Read-only.

Pre-registration: docs/working/prereg-qsw-media-bias.md (written after --coverage and BEFORE
--measure was first run). Memo: docs/research/media-bias-qsw.md.

    python3 media_bias_qsw.py --db DB --coverage                  # denominators only
    python3 media_bias_qsw.py --db DB --measure --out flags.tsv   # one row per deduped doc
    python3 media_bias_qsw.py --analyze --flags flags.tsv         # every table in the memo
    python3 media_bias_qsw.py --db DB --events --out events.tsv   # the timing test (section T)

Run on the droplet with --db /root/china-governance/documents.db (opened ?mode=ro). The
speaker classifier and strip_chrome come from web/services/discourse_vocab.py; pass --vocab-dir
to point at a copy of that file when the checkout predates it.
"""
import argparse
import csv
import math
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

WINDOW = ("2025-07-01", "2026-11-12")
DENSE_START = "2026-07-26"     # first date at which ifeng and jjckb are both present
MIN_BODY = 200                 # chars of body; shorter rows leave the denominator
MIN_SITE = 100                 # deduped documents for a site to enter the unweighted site mean

# ---------------------------------------------------------------------------------------
# MEASURES (frozen in the prereg; any change is an append-only note there)
# ---------------------------------------------------------------------------------------
PBSC = "习近平|李强|赵乐际|王沪宁|蔡奇|丁薛祥|李希"
RX = {
    # Party line
    "lead_title_xi": re.compile(r"习近平|总书记"),
    "lead_title_pbsc": re.compile(PBSC + r"|总书记"),
    "lead_body_xi": re.compile(r"习近平"),
    "xh_relay": re.compile(r"新华社[^\s，。；、]{0,10}?\d{1,2}月\d{1,2}日电|来源[:：]\s*新华(?:社|网)"
                           r"|新华社记者|据新华社"),
    "xh_any": re.compile(r"新华社|新华网"),
    # Mass line (accountability)
    "corrupt_case": re.compile(r"涉嫌严重违纪违法|接受[^。；\n]{0,8}?审查调查|纪律审查和监察调查|被查"
                               r"|双开|开除党籍|受贿罪|严重违纪违法问题"),
    "accident_dead": re.compile(r"(?:事故|火灾|爆炸|坍塌|垮塌|车祸|矿难|燃爆|中毒|翻沉|侧翻|相撞)"
                                r"[^。\n]{0,60}?(?:\d+|[一二三四五六七八九十两百]+)\s*(?:人|名[^。\n]{0,6}?)"
                                r"(?:死亡|遇难|罹难|身亡|丧生)"
                                r"|(?:\d+|[一二三四五六七八九十两百]+)\s*(?:人|名[^。\n]{0,6}?)"
                                r"(?:死亡|遇难|罹难|身亡|丧生)[^。\n]{0,60}?(?:事故|火灾|爆炸|坍塌|垮塌|车祸|矿难)"),
    "disaster_dead": re.compile(r"(?:地震|洪水|洪涝|山洪|台风|泥石流|滑坡|暴雨|强降雨|寒潮|冰雹|龙卷风)"
                                r"[^。\n]{0,60}?(?:\d+|[一二三四五六七八九十两百]+)\s*(?:人|名[^。\n]{0,6}?)"
                                r"(?:死亡|遇难|罹难|身亡|丧生|失联|失踪)"
                                r"|(?:\d+|[一二三四五六七八九十两百]+)\s*(?:人|名[^。\n]{0,6}?)"
                                r"(?:死亡|遇难|罹难|身亡|丧生|失联|失踪)[^。\n]{0,60}?"
                                r"(?:地震|洪水|洪涝|山洪|台风|泥石流|滑坡|暴雨|强降雨)"),
    # Bottom line (title-based, so the topic of the article, not a passing mention)
    "market_title": re.compile(r"股价|A股|港股|美股|涨停|跌停|市值|营收|净利|财报|融资|IPO|上市|募资"
                               r"|估值|基金|债券|期货|汇率|人民币兑|大盘|指数|收购|并购|分红"),
    "sport_title": re.compile(r"足球|篮球|排球|奥运|世界杯|亚运|全运会|中超|NBA|联赛|夺冠|冠军|决赛"
                              r"|马拉松|乒乓|网球|体育"),
    "ent_title": re.compile(r"电影|票房|明星|综艺|演唱会|电视剧|歌手|演员|影视|短剧|偶像|网红"),
    "crime_title": re.compile(r"警方|嫌疑人|犯罪|诈骗|刑拘|抓获|判处|获刑|判决|逮捕|杀人|盗窃|拐卖"),
}
# Secondary, added by the prereg's 22:05 note after a hand-check: lead-only (title + first 300
# body chars, so a sidebar of other headlines cannot reach) and a tighter corruption regex.
LEAD_CHARS = 300
RX["corrupt_lead"] = re.compile(r"涉嫌严重违纪违法|接受[^。；\n]{0,8}?审查调查|纪律审查和监察调查"
                                r"|被查(?![出实获扣封明到验])|双开|开除党籍|以受贿罪|严重违纪违法问题")
RX["accident_lead"] = RX["accident_dead"]
RX["disaster_lead"] = RX["disaster_dead"]
LEAD_ONLY = {"corrupt_lead", "accident_lead", "disaster_lead"}

ORDER = ["lead_title_xi", "lead_title_pbsc", "lead_body_xi", "xh_relay", "xh_any",
         "corrupt_case", "accident_dead", "disaster_dead",
         "market_title", "sport_title", "ent_title", "crime_title",
         "corrupt_lead", "accident_lead", "disaster_lead"]
TITLE_ONLY = {"lead_title_xi", "lead_title_pbsc", "market_title", "sport_title", "ent_title",
              "crime_title"}
LABEL = {
    "lead_title_xi": "Xi / 总书记 in title", "lead_title_pbsc": "PBSC member in title",
    "lead_body_xi": "习近平 in body", "xh_relay": "Xinhua relay (dateline / 来源)",
    "xh_any": "any 新华社 / 新华网", "corrupt_case": "named corruption case",
    "accident_dead": "accident with death toll", "disaster_dead": "disaster with toll",
    "market_title": "market / finance title", "sport_title": "sport title",
    "ent_title": "entertainment title", "crime_title": "crime title",
    "corrupt_lead": "corruption case, lead only (secondary)",
    "accident_lead": "accident toll, lead only (secondary)",
    "disaster_lead": "disaster toll, lead only (secondary)",
}
SOFT = ("sport_title", "ent_title", "crime_title")

TYPES = ["state_media", "party_theory", "commentary", "business_press", "research",
         "diplomacy", "central", "subnational"]
PARTY_OWNED = {"state_media", "party_theory"}
COMMERCIAL = {"commentary", "business_press"}


def _vocab(vocab_dir):
    if vocab_dir:
        sys.path.insert(0, str(vocab_dir))
        import discourse_vocab as dv            # noqa
    else:
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root))
        from web.services import discourse_vocab as dv  # noqa
    return dv


def norm_title(t):
    return re.sub(r"[\s　 《》〈〉“”\"'‘’（）()【】\[\]、，,。.:：|_-]+", "", t or "")


def rows(con, start, end):
    q = """SELECT d.id, d.site_key, d.title, substr(d.date_published,1,10), d.body_text_cn,
                  COALESCE(i.admin_level_doc, s.admin_level), COALESCE(i.genre, '')
           FROM documents d
           LEFT JOIN doc_identity i ON i.doc_id = d.id
           LEFT JOIN sites s ON s.site_key = d.site_key
           WHERE substr(d.date_published,1,10) BETWEEN ? AND ?
             AND d.date_published GLOB '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]*'"""
    return con.execute(q, (start, end))


def select(con, dv, start, end, payload=None):
    """Deduped population: one copy per (site, normalized title), the longest body."""
    best = {}
    drop = Counter()
    for did, site, title, day, body, lvl, genre in rows(con, start, end):
        sp = dv.speaker(site, lvl)
        if sp is None:
            drop["no_speaker"] += 1
            continue
        body = body or ""
        if site in dv.CHROME_SITES:
            body = dv.strip_chrome(site, body)
            if dv.article_chars(title, body) < 30:
                drop["chrome_stub"] += 1
                continue
        if len(body) < MIN_BODY:
            drop["short_body"] += 1
            continue
        key = (site, norm_title(title))
        cur = best.get(key)
        if cur is None or len(body) > cur[5]:
            best[key] = (did, site, title, day, sp, len(body), genre,
                         payload(title, body) if payload else None)
        else:
            drop["dup"] += 1
    return best, drop


def coverage(args):
    dv = _vocab(args.vocab_dir)
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    best, drop = select(con, dv, *WINDOW)
    by_site = defaultdict(lambda: [0, 0, None, None])
    for did, site, title, day, sp, blen, genre, _ in best.values():
        r = by_site[(sp, site)]
        r[0] += 1
        r[1] += blen
        r[2] = day if r[2] is None or day < r[2] else r[2]
        r[3] = day if r[3] is None or day > r[3] else r[3]
    print("dropped:", dict(drop))
    tot = Counter()
    for (sp, site), (n, bl, a, b) in sorted(by_site.items(), key=lambda x: (x[0][0], -x[1][0])):
        tot[sp] += n
        if sp in ("central", "subnational") and n < 500:
            continue
        print(f"{sp}\t{site}\t{n}\tmedian_len~{bl // max(n, 1)}\t{a}\t{b}")
    print("types:", dict(tot), "sites:", Counter(sp for sp, _ in by_site))


def measure(args):
    dv = _vocab(args.vocab_dir)
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    def flags(title, body):
        text = (title or "") + "\n" + body
        lead = (title or "") + "\n" + body[:LEAD_CHARS]
        return [1 if RX[k].search((title or "") if k in TITLE_ONLY
                                  else lead if k in LEAD_ONLY else text) else 0
                for k in ORDER]

    best, drop = select(con, dv, *WINDOW, payload=flags)
    print("dropped:", dict(drop), "kept:", len(best), file=sys.stderr)
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["id", "site", "type", "day", "genre", "blen"] + ORDER)
        for did, site, title, day, sp, blen, genre, fl in best.values():
            w.writerow([did, site, sp, day, genre, blen] + fl)


# ---------------------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------------------
def load(path):
    out = []
    with open(path) as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            for k in ORDER:
                row[k] = int(row[k])
            row["blen"] = int(row["blen"])
            out.append(row)
    return out


def rate(rs, k):
    return 1000.0 * sum(r[k] for r in rs) / len(rs) if rs else float("nan")


def soft(r):
    return 1 if any(r[k] for k in SOFT) else 0


def site_means(rs, k, types, exclude=()):
    """Unweighted mean over sites (n >= MIN_SITE) of per-site rates, within each type."""
    by = defaultdict(list)
    for r in rs:
        if r["site"] in exclude:
            continue
        by[(r["type"], r["site"])].append(r)
    out = {}
    for t in types:
        vals = [rate(v, k) for (tt, s), v in by.items() if tt == t and len(v) >= MIN_SITE]
        out[t] = (statistics.mean(vals) if vals else float("nan"), len(vals))
    return out


def fmt(x):
    return "" if x != x else f"{x:.1f}"


def analyze(args):
    rs = load(args.flags)
    for r in rs:
        r["soft"] = soft(r)
    keys = ORDER + ["soft"]
    LABEL["soft"] = "soft news (any of the three)"
    rs_w = [r for r in rs if r["day"] >= WINDOW[0]]
    print(f"rows {len(rs_w)}")

    print("\n## A. Pooled rate per 1,000 deduped documents, by speaker type")
    by_t = defaultdict(list)
    for r in rs_w:
        by_t[r["type"]].append(r)
    ts = [t for t in TYPES if by_t[t]]
    print("| measure | " + " | ".join(f"{t} (n={len(by_t[t]):,})" for t in ts) + " |")
    print("|---|" + "---|" * len(ts))
    for k in keys:
        print(f"| {LABEL[k]} | " + " | ".join(fmt(rate(by_t[t], k)) for t in ts) + " |")

    print("\n## B. Unweighted mean of site rates (sites with n >= %d), by type" % MIN_SITE)
    print("| measure | " + " | ".join(ts) + " |")
    print("|---|" + "---|" * len(ts))
    for k in keys:
        sm = site_means(rs_w, k, ts)
        print(f"| {LABEL[k]} | " + " | ".join(f"{fmt(sm[t][0])} ({sm[t][1]})" for t in ts) + " |")

    print("\n## C. Per media site (rate per 1,000)")
    by_s = defaultdict(list)
    for r in rs_w:
        if r["type"] not in ("central", "subnational"):
            by_s[(r["type"], r["site"])].append(r)
    cols = ["lead_title_xi", "lead_body_xi", "xh_relay", "xh_any", "corrupt_case",
            "accident_dead", "disaster_dead", "corrupt_lead", "accident_lead", "market_title",
            "soft"]
    print("| type | site | n | " + " | ".join(LABEL[k] for k in cols) + " |")
    print("|---|---|---|" + "---|" * len(cols))
    for (t, s), v in sorted(by_s.items(), key=lambda x: (TYPES.index(x[0][0]), -len(x[1]))):
        if len(v) < 30:
            continue
        print(f"| {t} | {s} | {len(v):,} | " + " | ".join(fmt(rate(v, k)) for k in cols) + " |")

    # registered contrasts: party-owned media (site mean) vs commercial media (site mean)
    print("\n## D. Registered contrasts: Party-owned vs commercial media, site-mean ratio")
    po = [s for (t, s) in by_s if t in PARTY_OWNED and len(by_s[(t, s)]) >= MIN_SITE]
    cm = [s for (t, s) in by_s if t in COMMERCIAL and len(by_s[(t, s)]) >= MIN_SITE]
    print("party-owned sites:", po, " commercial sites:", cm)
    site_rows = {s: v for (t, s), v in by_s.items()}

    def grp(sites, k, excl=()):
        vals = [rate(site_rows[s], k) for s in sites if s not in excl]
        return statistics.mean(vals) if vals else float("nan")

    def perm_p(k, excl=(), n_perm=0):
        """Exact permutation p (two-sided) of the difference of site means over all labellings."""
        from itertools import combinations
        a = [s for s in po if s not in excl]
        b = [s for s in cm if s not in excl]
        allv = {s: rate(site_rows[s], k) for s in a + b}
        obs = statistics.mean(allv[s] for s in a) - statistics.mean(allv[s] for s in b)
        sites = a + b
        cnt = tot = 0
        for comb in combinations(sites, len(a)):
            ca = set(comb)
            d = (statistics.mean(allv[s] for s in ca)
                 - statistics.mean(allv[s] for s in sites if s not in ca))
            tot += 1
            if abs(d) >= abs(obs) - 1e-12:
                cnt += 1
        return obs, cnt / tot, tot

    print("| measure | Party-owned site mean | commercial site mean | ratio | diff | exact perm p (labellings) |")
    print("|---|---|---|---|---|---|")
    for k in keys:
        a, b = grp(po, k), grp(cm, k)
        obs, p, tot = perm_p(k)
        ratio = a / b if b else float("inf")
        print(f"| {LABEL[k]} | {fmt(a)} | {fmt(b)} | {ratio:.2f} | {obs:+.1f} | {p:.3f} ({tot}) |")

    print("\n## E. Robustness")
    for name, excl in [("drop stdaily (science paper)", {"stdaily"}),
                       ("drop qbitai (AI-only outlet)", {"qbitai"}),
                       ("drop xinhua (relay measure is by construction)", {"xinhua"}),
                       ("drop guancha", {"guancha"})]:
        print(f"\n### {name}")
        print("| measure | Party-owned | commercial | ratio |")
        print("|---|---|---|---|")
        for k in ["lead_title_xi", "lead_body_xi", "xh_relay", "corrupt_case", "accident_dead",
                  "disaster_dead", "market_title", "soft"]:
            a, b = grp(po, k, excl), grp(cm, k, excl)
            print(f"| {LABEL[k]} | {fmt(a)} | {fmt(b)} | {(a / b if b else float('inf')):.2f} |")

    print("\n### dense window (%s on), pooled by type" % DENSE_START)
    rs_d = [r for r in rs_w if r["day"] >= DENSE_START]
    by_td = defaultdict(list)
    for r in rs_d:
        by_td[r["type"]].append(r)
    print("| measure | " + " | ".join(f"{t} (n={len(by_td[t]):,})" for t in ts) + " |")
    print("|---|" + "---|" * len(ts))
    for k in keys:
        print(f"| {LABEL[k]} | " + " | ".join(fmt(rate(by_td[t], k)) for t in ts) + " |")

    print("\n### genre news only (doc_identity.genre='news'), pooled by type")
    by_tg = defaultdict(list)
    for r in rs_w:
        if r["genre"] == "news":
            by_tg[r["type"]].append(r)
    tg = [t for t in ts if len(by_tg[t]) >= 50]
    print("| measure | " + " | ".join(f"{t} (n={len(by_tg[t]):,})" for t in tg) + " |")
    print("|---|" + "---|" * len(tg))
    for k in keys:
        print(f"| {LABEL[k]} | " + " | ".join(fmt(rate(by_tg[t], k)) for t in tg) + " |")

    # Xinhua relay share among non-Xinhua media
    print("\n### Xinhua relay share, media sites other than xinhua and jjckb (Xinhua's own paper)")
    for t in ["state_media", "party_theory", "commentary", "business_press"]:
        v = [r for r in by_t[t] if r["site"] not in ("xinhua", "jjckb")]
        if v:
            print(f"{t}: n={len(v):,} relay={rate(v, 'xh_relay'):.1f} any={rate(v, 'xh_any'):.1f}")

    # conditional: among accident/corruption documents, share that are Xinhua relays
    print("\n### Among accountability documents, share that are Xinhua relays (non-xinhua sites)")
    for k in ["corrupt_case", "accident_dead", "disaster_dead"]:
        for t in ["state_media", "commentary", "business_press"]:
            v = [r for r in by_t[t] if r[k] and r["site"] not in ("xinhua", "jjckb")]
            if v:
                print(f"{k} {t}: n={len(v)} xinhua_relay_share={rate(v, 'xh_relay') / 10:.1f}%")


# ---------------------------------------------------------------------------------------
# timing test
# ---------------------------------------------------------------------------------------
EVENTS = {}   # filled from the prereg's rule by --events (see find_events)


def events(args):
    """Timing test: for each registered event, every deduped document (any speaker type) whose
    title or first 400 body characters names the event's key string, dated within
    [event_day - 3, event_day + 30]."""
    dv = _vocab(args.vocab_dir)
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    ev = [line.rstrip("\n").split("\t") for line in open(args.event_list) if line.strip()
          and not line.startswith("#")]
    rxs = [(name, re.compile(pat)) for name, _d, pat in ev]

    def hits(title, body):
        head = (title or "") + "\n" + body[:400]
        return ([name for name, rx in rxs if rx.search(head)],
                1 if RX["xh_relay"].search((title or "") + "\n" + body) else 0)

    best, _ = select(con, dv, *WINDOW, payload=hits)
    from datetime import date, timedelta
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["event", "event_day", "id", "site", "type", "day", "lag", "xh_relay", "title"])
        for name, day0, pat in ev:
            d0 = date.fromisoformat(day0)
            lo, hi = (d0 - timedelta(days=3)).isoformat(), (d0 + timedelta(days=30)).isoformat()
            for did, site, title, day, sp, blen, genre, (names, xr) in best.values():
                if lo <= day <= hi and name in names:
                    lag = (date.fromisoformat(day) - d0).days
                    w.writerow([name, day0, did, site, sp, day, lag, xr, (title or "")[:80]])


def analyze_events(args):
    """Per event x speaker type: documents, first-day lag, Xinhua-relay share."""
    by = defaultdict(list)
    with open(args.flags) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            by[(r["event"], r["type"])].append(r)
    evs = sorted({e for e, _ in by})
    print("| event | " + " | ".join(TYPES) + " |")
    print("|---|" + "---|" * len(TYPES))
    for e in evs:
        cells = []
        for t in TYPES:
            v = by.get((e, t), [])
            if not v:
                cells.append("-")
                continue
            lag = min(int(r["lag"]) for r in v)
            xr = 100.0 * sum(int(r["xh_relay"]) for r in v) / len(v)
            sites = len({r["site"] for r in v})
            cells.append(f"{len(v)} docs / {sites} sites, lag {lag}, relay {xr:.0f}%")
        print(f"| {e} | " + " | ".join(cells) + " |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--vocab-dir")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--events", action="store_true")
    ap.add_argument("--analyze-events", action="store_true")
    ap.add_argument("--event-list")
    ap.add_argument("--flags")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.coverage:
        coverage(a)
    elif a.measure:
        measure(a)
    elif a.analyze:
        analyze(a)
    elif a.events:
        events(a)
    elif a.analyze_events:
        analyze_events(a)


if __name__ == "__main__":
    main()
