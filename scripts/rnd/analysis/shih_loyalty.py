"""Shih (2008) loyalty-signalling replication, Xi era, provincial government documents.

Read-only. Pre-registration: docs/working/prereg-shih-loyalty.md (written BEFORE --measure
was first run). Memo: docs/research/shih-loyalty-signalling.md.

    python3 shih_loyalty.py --coverage            # denominators only (no outcome terms)
    python3 shih_loyalty.py --measure --out /tmp/shih/flags.tsv   # one row per deduped doc
    python3 shih_loyalty.py --analyze --flags /tmp/shih/flags.tsv  # every table in the memo

Run on the droplet: --db /root/china-governance/documents.db (opened ?mode=ro).
--repo points at a checkout whose scripts/rnd/analysis holds build_diffusion_events.py
(the province_of fallback), default = this file's repo.
"""
import argparse
import csv
import math
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3] if len(_HERE.parents) > 3 else Path("/root/china-governance")

WINDOW = ("2022-01-01", "2026-11-12")   # 2022 only feeds T2
T1_START = "2023-01-01"
SUBNATIONAL = ("provincial", "municipal", "district", "department")
MIN_BODY = 200          # chars of body text; shorter rows leave the denominator

# ---- media exclusion: admin_level_doc already drops `media`, and these site sets
# (web/services/discourse_vocab.py) are dropped too in case a media row was re-levelled.
MEDIA_SITES = {"qstheory", "dangyuan", "qiushi", "hongqi", "studytimes", "gmrb_theory", "rmlt",
               "xinhua", "people", "ce", "jjckb", "stdaily", "cnr", "cctv", "chinanews",
               "people_rmrb", "peopleapp", "newscn", "xinhua_lw", "xinhua_en", "guancha", "ifeng",
               "yicai", "jiemian", "36kr", "latepost", "qbitai", "eeo", "huxiu", "tmtpost",
               "elsewhere", "21jingji", "cnfin", "eastmoney", "guandian", "qqnews", "thepaper",
               "cass", "amr", "tsinghua_aiig", "cast", "isc", "cssn"}

# ---- TERM SETS (frozen in the prereg; do not edit without an append-only note) ----
LOYALTY_A = {   # standard / centrally mandated formulations
    "A1_思想": r"习近平新时代中国特色社会主义思想",
    "A2_核心": r"以习近平同志为核心的党中央",
    "A3_重要讲话指示": r"习近平总书记[^。；\n]{0,40}?重要(?:讲话|指示|论述)",
}
LOYALTY_B = {   # discretionary / intensified personal-loyalty formulations
    "B1_两个确立": r"两个确立",
    "B2_两个维护": r"两个维护",
    "B3_坚决拥护": r"坚决拥护",
    "B4_感恩": r"感恩奋进|感恩总书记|感党恩",
    "B5_牢记嘱托": r"牢记[^。；\n]{0,8}嘱托",
    "B6_总书记亲自": r"总书记亲自",
    "B7_人民领袖": r"人民领袖",
}
PLACEBO = {
    "P1_高质量发展": r"高质量发展",
    "P2_新质生产力": r"新质生产力",
    "P3_营商环境": r"营商环境",
}
ALL_TERMS = {**LOYALTY_A, **LOYALTY_B, **PLACEBO}
_RX = {k: re.compile(v) for k, v in ALL_TERMS.items()}

# ---- TREATMENT: secretary spells (verified 2026-11-12, sources in the memo) ----------
# assoc: "core" = officials.db career record in Fujian 1985-2002 or Zhejiang 2002-2007
# (Xi's sustained provincial tenures); "sh07" = in Shanghai municipal service in 2007 only
# (Xi's seven months there); "" = none.
SPELLS = {  # province -> [(start YYYY-MM-DD, name, assoc)], in order; each runs to the next
 "bj": [("2022-11-13", "尹力", "")],
 "tj": [("2022-12-08", "陈敏尔", "core")],
 "sh": [("2022-10-28", "陈吉宁", "")],
 "cq": [("2022-12-08", "袁家军", "")],
 "he": [("2022-04-22", "倪岳峰", ""), ("2026-07-31", "罗文", "")],
 "sx": [("2022-12-29", "蓝佛安", ""), ("2023-09-28", "(vacant)", "gap"), ("2023-10-28", "唐登杰", "")],
 "ln": [("2022-11-28", "郝鹏", ""), ("2025-09-30", "许昆林", "")],
 "jl": [("2020-11-20", "景俊海", ""), ("2024-06-28", "黄强", "")],
 "hlj": [("2021-10-19", "许勤", "")],
 "js": [("2021-10-01", "吴政隆", ""), ("2023-01-03", "信长星", "")],
 "zj": [("2022-12-07", "易炼红", ""), ("2024-10-28", "王浩", "")],
 "ah": [("2021-09-30", "郑栅洁", "core"), ("2023-03-14", "韩俊", ""), ("2024-06-28", "梁言顺", ""),
        ("2026-09-23", "李乐成", "")],
 "fj": [("2022-11-27", "周祖翼", ""), ("2026-09-23", "赵龙", "")],
 "jx": [("2022-12-07", "尹弘", "sh07")],
 "sd": [("2022-12-29", "林武", "")],
 "ha": [("2021-06-01", "楼阳生", "core"), ("2024-12-31", "刘宁", ""), ("2026-09-23", "周祖翼", "")],
 "hb": [("2022-03-01", "王蒙徽", ""), ("2024-12-31", "王忠林", ""), ("2026-05-30", "关志鸥", "")],
 "hn": [("2021-10-01", "张庆伟", ""), ("2023-03-14", "沈晓明", "sh07"), ("2026-10-24", "王志军", "")],
 "gd": [("2022-10-28", "黄坤明", "core")],
 "gx": [("2021-10-01", "刘宁", ""), ("2024-12-31", "陈刚", "")],
 "hi": [("2020-11-01", "沈晓明", "sh07"), ("2023-03-14", "冯飞", "")],
 "sc": [("2022-04-22", "王晓晖", "")],
 "gz": [("2022-12-09", "徐麟", "sh07")],
 "yn": [("2021-10-19", "王宁", ""), ("2026-10-24", "莫高义", "")],
 "sn": [("2022-11-27", "赵一德", "core")],
 "gs": [("2022-12-01", "胡昌升", ""), ("2026-09-22", "吴晓军", "")],
 "qh": [("2023-01-03", "陈刚", ""), ("2024-12-31", "吴晓军", ""), ("2026-09-22", "罗东川", "")],
 "nm": [("2022-04-30", "孙绍骋", ""), ("2025-09-30", "王伟中", "")],
 "xz": [("2021-10-18", "王君正", ""), ("2026-09-22", "胡昌升", "")],
 "nx": [("2022-03-28", "梁言顺", ""), ("2024-06-28", "李邑飞", "")],
 "xj": [("2021-12-25", "马兴瑞", ""), ("2025-07-01", "陈小江", "")],
}


def spell_of(prov, d):
    """(index, name, assoc) of the secretary in post in `prov` on ISO date `d`."""
    sp = SPELLS.get(prov)
    if not sp:
        return None
    cur = None
    for i, (start, name, assoc) in enumerate(sp):
        if d >= start:
            cur = (i, name, assoc)
    return cur


def _import_province_of(repo):
    sys.path.insert(0, str(Path(repo) / "scripts" / "rnd" / "analysis"))
    sys.path.insert(0, str(Path(repo) / "scripts" / "rnd" / "citations"))
    import build_diffusion_events as bde  # noqa
    return bde


def norm_title(t):
    return re.sub(r"[\s　​‌‍﻿]+", "", t or "")


def load_rows(db, repo, with_body):
    """Yield deduped documents: one copy per (province, normalized title), the copy with the
    longest body. Returns dict key -> row dict."""
    bde = _import_province_of(repo)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    bde.load_site_names(conn)
    q = f"""SELECT d.id, d.site_key, d.title, substr(d.date_published,1,10), i.genre,
                   i.province, i.admin_level_doc, LENGTH(d.body_text_cn)
                   {", d.body_text_cn" if with_body else ""}
            FROM doc_identity i JOIN documents d ON d.id = i.doc_id
            WHERE i.admin_level_doc IN ({",".join("?" * len(SUBNATIONAL))})
              AND substr(d.date_published,1,10) BETWEEN ? AND ?"""
    best = {}
    pv_src = Counter()
    for r in conn.execute(q, (*SUBNATIONAL, *WINDOW)):
        did, site, title, d, genre, prov, lvl, blen = r[:8]
        if site in MEDIA_SITES or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or ""):
            continue
        if (blen or 0) < MIN_BODY:
            continue
        site_prov = bde.province_of(site)
        if not site_prov:          # national site (miit, npc, ...): not a provincial issuer
            pv_src["national_site_dropped"] += 1
            continue
        if prov:
            pv_src["doc_identity"] += 1
        else:
            prov = site_prov
            pv_src["site_fallback"] += 1
        key = (prov, norm_title(title))
        if key in best and best[key]["blen"] >= blen:
            continue
        row = dict(id=did, site=site, title=title, date=d, genre=genre or "", prov=prov,
                   lvl=lvl, blen=blen)
        if with_body:
            row["flags"] = flags_of((title or "") + "\n" + (r[8] or ""))
            row["nsent"] = (r[8] or "").count("。")
            row["proc"] = int(bool(PROC_RE.search(title or "")))
        best[key] = row
    return best, pv_src


# Amendment 2 (after first results): procurement / tender notices are not policy text.
PROC_RE = re.compile(r"招标|中标|成交|采购|比选|询价|竞价|竞争性磋商|拍卖|挂牌出让")


def flags_of(text):
    out = {}
    for k, rx in _RX.items():
        out[k] = len(rx.findall(text))
    return out


def coverage(args):
    best, src = load_rows(args.db, args.repo, with_body=False)
    print("province source:", dict(src))
    per = defaultdict(list)
    for r in best.values():
        per[r["prov"]].append(r)
    print("prov\tdocs\tsites\ttop_site\ttop_share\tlevels\tgenres")
    for p in sorted(per, key=lambda p: -len(per[p])):
        rows = per[p]
        sites = Counter(r["site"] for r in rows)
        top, n = sites.most_common(1)[0]
        lv = Counter(r["lvl"] for r in rows)
        gn = Counter(r["genre"] for r in rows)
        print(f"{p}\t{len(rows)}\t{len(sites)}\t{top}\t{n/len(rows):.2f}\t{dict(lv)}\t{dict(gn.most_common(4))}")


def measure(args):
    best, src = load_rows(args.db, args.repo, with_body=True)
    print("province source:", dict(src), "deduped docs:", len(best), file=sys.stderr)
    keys = list(ALL_TERMS)
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["id", "site", "date", "genre", "prov", "lvl", "blen", "nsent", "proc", *keys])
        for r in best.values():
            w.writerow([r["id"], r["site"], r["date"], r["genre"], r["prov"], r["lvl"], r["blen"],
                        r["nsent"], r["proc"],
                        *[r["flags"][k] for k in keys]])


# ==== ANALYSIS ====
import itertools  # noqa: E402

SETS = {"A": list(LOYALTY_A), "B": list(LOYALTY_B), "P": list(PLACEBO)}
for _k in PLACEBO:
    SETS[_k] = [_k]
for _k in LOYALTY_B:
    SETS[_k] = [_k]


def load_flags(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            for k in ALL_TERMS:
                r[k] = int(r[k])
            r["blen"] = int(r["blen"])
            r["nsent"] = int(r.get("nsent") or 0)
            r["proc"] = int(r.get("proc") or 0)
            rows.append(r)
    return rows


def has(r, setname):
    return any(r[k] for k in SETS[setname])


def rate(rows, setname):
    """Documents carrying >= 1 term of the set, per 1,000 documents."""
    return 1000.0 * sum(1 for r in rows if has(r, setname)) / len(rows) if rows else float("nan")


def intensity(rows, setname):
    """Term occurrences per 10,000 body characters."""
    ch = sum(r["blen"] for r in rows)
    return 1e4 * sum(r[k] for r in rows for k in SETS[setname]) / ch if ch else float("nan")


def is_treated(assoc, sh07):
    return assoc == "core" or (sh07 and assoc == "sh07")


def spells_table(rows, lo, hi, minn=150, sh07=False, out="B"):
    """Province x secretary spell cells in [lo, hi]. Returns list of dicts."""
    cells = defaultdict(list)
    meta = {}
    for r in rows:
        if not (lo <= r["date"] <= hi):
            continue
        sp = spell_of(r["prov"], r["date"])
        if not sp or sp[2] == "gap":
            continue
        key = (r["prov"], sp[0])
        cells[key].append(r)
        meta[key] = sp
    tab = []
    for key, rs in cells.items():
        if len(rs) < minn:
            continue
        i, name, assoc = meta[key]
        if assoc == "sh07" and not sh07:
            assoc_flag = None          # excluded from both groups in the primary test
        else:
            assoc_flag = is_treated(assoc, sh07)
        tab.append(dict(prov=key[0], name=name, assoc=assoc, treated=assoc_flag, n=len(rs),
                        Y=rate(rs, out), P=rate(rs, "P"), A=rate(rs, "A"), B=rate(rs, "B")))
    return tab


def contrast(tab, ykey="Y"):
    t = [c for c in tab if c["treated"] is True]
    u = [c for c in tab if c["treated"] is False]
    if not t or not u:
        return None
    m = lambda xs, k: sum(c[k] for c in xs) / len(xs)  # noqa: E731
    yt, yu, pt, pu = m(t, ykey), m(u, ykey), m(t, "P"), m(u, "P")
    if min(yt, yu, pt, pu) <= 0:
        return None
    return dict(Yt=yt, Yu=yu, Pt=pt, Pu=pu, d_rel=math.log(yt / yu) - math.log(pt / pu),
                d_abs=(yt - yu) - (pt - pu), nt=len(t), nu=len(u),
                nt_docs=sum(c["n"] for c in t), nu_docs=sum(c["n"] for c in u))


def perm_p(tab, ykey="Y", nsamp=10000, seed=7):
    """Two-sided permutation p for d_rel: exact enumeration when feasible."""
    elig = [c for c in tab if c["treated"] is not None]
    k = sum(1 for c in elig if c["treated"])
    obs = contrast(tab, ykey)
    if not obs or k == 0:
        return float("nan")
    n = len(elig)
    combos = math.comb(n, k)
    rng = random.Random(seed)
    it = (itertools.combinations(range(n), k) if combos <= 20000
          else (tuple(rng.sample(range(n), k)) for _ in range(nsamp)))
    hits = tot = 0
    for idx in it:
        s = set(idx)
        relab = [dict(c, treated=(j in s)) for j, c in enumerate(elig)]
        c = contrast(relab, ykey)
        if c is None:
            continue
        tot += 1
        hits += abs(c["d_rel"]) >= abs(obs["d_rel"]) - 1e-12
    return hits / tot if tot else float("nan")


def fmt(x, d=1):
    return "nan" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def print_t1(label, tab, ykey="Y"):
    c = contrast(tab, ykey)
    print(f"\n### {label}")
    print("| province | secretary | assoc | n | B /1k | A /1k | P /1k |")
    print("|---|---|---|---|---|---|---|")
    for x in sorted(tab, key=lambda c: (-(c['treated'] is True), -c["n"])):
        print(f"| {x['prov']} | {x['name']} | {x['assoc'] or '-'} | {x['n']} | {fmt(x['B'])} | "
              f"{fmt(x['A'])} | {fmt(x['P'])} |")
    if c:
        print(f"\nassoc spells {c['nt']} ({c['nt_docs']} docs) vs non {c['nu']} ({c['nu_docs']} docs): "
              f"Y {fmt(c['Yt'])} vs {fmt(c['Yu'])}; P {fmt(c['Pt'])} vs {fmt(c['Pu'])}; "
              f"D_rel {fmt(c['d_rel'], 3)}; D_abs {fmt(c['d_abs'])}; perm p {fmt(perm_p(tab, ykey), 3)}")
    else:
        print("\n(no contrast: a group is empty)")
    return c


def t1c(rows, sh07=False, minn=100, out="B"):
    """Year-standardized: contrast within each calendar year, weighted by treated docs."""
    acc = []
    for y in ("2023", "2024", "2025", "2026"):
        tab = spells_table(rows, f"{y}-01-01", f"{y}-12-31", minn=minn, sh07=sh07, out=out)
        c = contrast(tab)
        if c:
            acc.append((y, c))
    print("\n### T1c year-standardized (spell cells >= %d docs within the year)" % minn)
    print("| year | assoc cells (docs) | non cells (docs) | B assoc | B non | P assoc | P non | D_rel |")
    print("|---|---|---|---|---|---|---|---|")
    for y, c in acc:
        print(f"| {y} | {c['nt']} ({c['nt_docs']}) | {c['nu']} ({c['nu_docs']}) | {fmt(c['Yt'])} | "
              f"{fmt(c['Yu'])} | {fmt(c['Pt'])} | {fmt(c['Pu'])} | {fmt(c['d_rel'], 3)} |")
    w = sum(c["nt_docs"] for _, c in acc)
    if w:
        print(f"\nweighted mean D_rel = {fmt(sum(c['d_rel'] * c['nt_docs'] for _, c in acc) / w, 3)}")


def window_rates(rows, prov, lo, hi):
    rs = [r for r in rows if r["prov"] == prov and lo <= r["date"] <= hi]
    return rs


def t2(rows):
    pre, post = ("2022-03-01", "2022-09-30"), ("2023-01-15", "2023-08-15")
    gain, lose = {"gd", "sn"}, {"bj", "sh", "cq"}
    print("\n### T2 within-province, 2022 reshuffle (pre 2022-03-01..09-30, post 2023-01-15..08-15)")
    print("| province | group | n pre | n post | B pre | B post | P pre | P post | ln dB - ln dP |")
    print("|---|---|---|---|---|---|---|---|---|")
    res = defaultdict(list)
    for prov in sorted({r["prov"] for r in rows}):
        if prov == "ah":
            continue
        a, b = window_rates(rows, prov, *pre), window_rates(rows, prov, *post)
        grp = "gainer" if prov in gain else "loser" if prov in lose else "control"
        if len(a) < 100 or len(b) < 100:
            if grp != "control":
                print(f"| {prov} | {grp} | {len(a)} | {len(b)} | (too few) | | | | |")
            continue
        B0, B1, P0, P1 = rate(a, "B"), rate(b, "B"), rate(a, "P"), rate(b, "P")
        st = (math.log(B1 / B0) - math.log(P1 / P0)) if min(B0, B1, P0, P1) > 0 else float("nan")
        res[grp].append(st)
        print(f"| {prov} | {grp} | {len(a)} | {len(b)} | {fmt(B0)} | {fmt(B1)} | {fmt(P0)} | {fmt(P1)} | {fmt(st, 3)} |")
    for g, v in res.items():
        print(f"{g}: mean {fmt(sum(v) / len(v), 3)} over {len(v)} provinces")


def t3(rows, minn=60):
    print("\n### T3 new-secretary arrival (pre = 120 d before; post = days 15-135 after)")
    print("| province | arrival | secretary | n pre | n post | B pre | B post | P pre | P post | stat | 坚决拥护 pre | post |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    out = []
    for prov, sp in SPELLS.items():
        for start, name, assoc in sp:
            if not ("2024-06-01" <= start <= "2026-07-01") or name == "(vacant)":
                continue
            d0 = date.fromisoformat(start)
            pre = ((d0.toordinal() - 120), d0.toordinal() - 1)
            post = (d0.toordinal() + 15, d0.toordinal() + 135)
            iso = lambda o: date.fromordinal(o).isoformat()  # noqa: E731
            a = window_rates(rows, prov, iso(pre[0]), iso(pre[1]))
            b = window_rates(rows, prov, iso(post[0]), iso(post[1]))
            if len(a) < minn or len(b) < minn:
                print(f"| {prov} | {start} | {name} | {len(a)} | {len(b)} | (too few) | | | | | | |")
                continue
            B0, B1, P0, P1 = rate(a, "B"), rate(b, "B"), rate(a, "P"), rate(b, "P")
            st = (math.log(B1 / B0) - math.log(P1 / P0)) if min(B0, B1, P0, P1) > 0 else float("nan")
            out.append(st)
            print(f"| {prov} | {start} | {name} | {len(a)} | {len(b)} | {fmt(B0)} | {fmt(B1)} | {fmt(P0)} | "
                  f"{fmt(P1)} | {fmt(st, 3)} | {fmt(rate(a, 'B3_坚决拥护'))} | {fmt(rate(b, 'B3_坚决拥护'))} |")
    if out:
        print(f"pooled mean stat {fmt(sum(out) / len(out), 3)} over {len(out)} switches")


def t4(rows, lo, hi, minn=300):
    per = defaultdict(list)
    for r in rows:
        if lo <= r["date"] <= hi:
            per[r["prov"]].append(r)
    provs = [p for p in per if len(per[p]) >= minn]
    print(f"\n### T4 distribution {lo}..{hi}, provinces with >= {minn} docs (n = {len(provs)})")
    print("| province | n | B /1k | A /1k | P /1k | B/P |")
    print("|---|---|---|---|---|---|")
    vals = {"B": [], "A": [], "P": []}
    for p in sorted(provs, key=lambda p: -rate(per[p], "B")):
        b, a, pl = rate(per[p], "B"), rate(per[p], "A"), rate(per[p], "P")
        vals["B"].append(b); vals["A"].append(a); vals["P"].append(pl)  # noqa: E702
        print(f"| {p} | {len(per[p])} | {fmt(b)} | {fmt(a)} | {fmt(pl)} | {fmt(b / pl, 2)} |")
    for k, v in vals.items():
        mu = sum(v) / len(v)
        sd = (sum((x - mu) ** 2 for x in v) / (len(v) - 1)) ** 0.5
        med = sorted(v)[len(v) // 2]
        within = sum(1 for x in v if abs(x - med) <= 0.25 * med) / len(v)
        print(f"{k}: mean {fmt(mu)} sd {fmt(sd)} CV {fmt(sd / mu, 3)}; min {fmt(min(v))} max {fmt(max(v))}; "
              f"share within +-25% of median {fmt(within, 2)}")


def loso(rows):
    """Drop each province's largest site (over the whole file)."""
    big = {}
    for p in {r["prov"] for r in rows}:
        big[p] = Counter(r["site"] for r in rows if r["prov"] == p).most_common(1)[0][0]
    return [r for r in rows if r["site"] != big[r["prov"]]], big


def per_term(rows, lo, hi):
    t = [r for r in rows if lo <= r["date"] <= hi and (sp := spell_of(r["prov"], r["date"])) and sp[2] == "core"]
    u = [r for r in rows if lo <= r["date"] <= hi and (sp := spell_of(r["prov"], r["date"])) and sp[2] == ""]
    print(f"\n### per-term rates {lo}..{hi}, documents pooled (assoc n={len(t)}, non n={len(u)})")
    print("| term | assoc /1k | non /1k | ratio |")
    print("|---|---|---|---|")
    for k in list(LOYALTY_A) + list(LOYALTY_B) + list(PLACEBO):
        a = 1000 * sum(1 for r in t if r[k]) / len(t)
        b = 1000 * sum(1 for r in u if r[k]) / len(u)
        print(f"| {k} | {fmt(a)} | {fmt(b)} | {fmt(a / b if b else float('nan'), 2)} |")


def trend(rows):
    print("\n### national trend, all provinces pooled, by half-year")
    print("| half | n | B /1k | A /1k | P /1k | 两个确立 | 新质生产力 |")
    print("|---|---|---|---|---|---|---|")
    per = defaultdict(list)
    for r in rows:
        per[r["date"][:4] + ("H1" if r["date"][5:7] <= "06" else "H2")].append(r)
    for h in sorted(per):
        rs = per[h]
        print(f"| {h} | {len(rs)} | {fmt(rate(rs, 'B'))} | {fmt(rate(rs, 'A'))} | {fmt(rate(rs, 'P'))} | "
              f"{fmt(rate(rs, 'B1_两个确立'))} | {fmt(rate(rs, 'P2_新质生产力'))} |")


def clean(rows):
    """Amendment 2 population: >= 3 sentence stops in the body, not a procurement notice."""
    return [r for r in rows if r["nsent"] >= 3 and not r["proc"]]


def gdp_pc(path=None):
    path = path or (_ROOT / "data" / "provincial_gdp.csv")
    sys.path.insert(0, str(_HERE.parent))
    from geo import PROVINCE_CODE  # noqa
    short = {k.replace("省", "").replace("市", "").replace("壮族自治区", "").replace("回族自治区", "")
             .replace("维吾尔自治区", "").replace("自治区", ""): v for k, v in PROVINCE_CODE.items()}
    out = {}
    with open(path) as f:
        for r in csv.DictReader(line for line in f if not line.startswith("#")):
            if r["year"] == "2024" and r["province"] in short:
                out[short[r["province"]]] = float(r["gdp_per_capita_yuan"])
    return out


def spearman(x, y):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    a, b = rk(x), rk(y)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    den = (sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b)) ** 0.5
    return num / den


def _ols(X, Y):
    """Least squares by normal equations (3 regressors), Gauss-Jordan."""
    k = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) for j in range(k)] + [sum(x[i] * y for x, y in zip(X, Y))] for i in range(k)]
    for i in range(k):
        piv = A[i][i]
        A[i] = [v / piv for v in A[i]]
        for j in range(k):
            if j != i:
                f = A[j][i]
                A[j] = [a - f * b for a, b in zip(A[j], A[i])]
    return [A[i][k] for i in range(k)]


def exploratory(rows, lo, hi, minn=300, label=""):
    per = defaultdict(list)
    for r in rows:
        if lo <= r["date"] <= hi:
            per[r["prov"]].append(r)
    provs = sorted([p for p in per if len(per[p]) >= minn], key=lambda p: -len(per[p]))
    g = gdp_pc()
    print(f"\n### exploratory {label} {lo}..{hi} (provinces >= {minn} docs, n = {len(provs)})")
    print("| province | n | GDP pc 2024 (k yuan) | B/P | 感恩 /1k | 牢记嘱托 /1k | 人民领袖 /1k | 两个确立 /1k |")
    print("|---|---|---|---|---|---|---|---|")
    xs, ys, ys2 = [], [], []
    for p in sorted(provs, key=lambda p: -g.get(p, 0)):
        rs = per[p]
        b, pl = rate(rs, "B"), rate(rs, "P")
        print(f"| {p} | {len(rs)} | {fmt(g.get(p, float('nan')) / 1000, 0)} | {fmt(b / pl if pl else float('nan'), 3)} | "
              f"{fmt(rate(rs, 'B4_感恩'))} | {fmt(rate(rs, 'B5_牢记嘱托'))} | {fmt(rate(rs, 'B7_人民领袖'))} | "
              f"{fmt(rate(rs, 'B1_两个确立'))} |")
        if p in g and pl:
            xs.append(g[p]); ys.append(b / pl); ys2.append(b)
    print(f"Spearman(GDP pc, B/P) = {fmt(spearman(xs, ys), 3)}; Spearman(GDP pc, B rate) = {fmt(spearman(xs, ys2), 3)}; n = {len(xs)}")
    # OLS: ln(B/P) = a + b ln(GDP pc) + c assoc  (assoc = core secretary in post on 2026-06-30)
    X, Y = [], []
    for p in provs:
        b, pl = rate(per[p], "B"), rate(per[p], "P")
        sp = spell_of(p, "2026-06-30")
        if p in g and b > 0 and pl > 0 and sp:
            X.append((1.0, math.log(g[p]), 1.0 if sp[2] == "core" else 0.0)); Y.append(math.log(b / pl))  # noqa: E702
    if len(X) > 4:
        beta = _ols(X, Y)
        print(f"OLS ln(B/P) = {fmt(beta[0], 2)} + {fmt(beta[1], 3)} ln(GDP pc) + {fmt(beta[2], 3)} assoc; n = {len(X)}, "
              f"assoc provinces = {int(sum(x[2] for x in X))}")
        kk = int(sum(x[2] for x in X))
        hits = tot = 0
        for idx in itertools.combinations(range(len(X)), kk):
            Xp = [(1.0, x[1], 1.0 if j in idx else 0.0) for j, x in enumerate(X)]
            tot += 1
            hits += abs(_ols(Xp, Y)[2]) >= abs(beta[2]) - 1e-12
        print(f"  exact permutation p for the assoc coefficient: {fmt(hits / tot, 3)} ({tot} relabellings)")
    for k in ("B", "A", "P"):
        v = [math.log(rate(per[p], k)) for p in provs if rate(per[p], k) > 0]
        mu = sum(v) / len(v)
        sd = (sum((x - mu) ** 2 for x in v) / (len(v) - 1)) ** 0.5
        print(f"SD of ln({k} rate) across provinces = {fmt(sd, 3)} (n = {len(v)})")
    # binomial-noise floor: expected CV of B if every province shared the pooled rate
    pooled = sum(1 for p in provs for r in per[p] if has(r, "B")) / sum(len(per[p]) for p in provs)
    cv0 = (sum(((pooled * (1 - pooled) / len(per[p])) ** 0.5) / pooled for p in provs) / len(provs))
    print(f"binomial-noise CV of B under a common rate {fmt(1000 * pooled)} /1k: about {fmt(cv0, 3)}")


def analyze(args):
    rows = load_flags(args.flags)
    print(f"rows {len(rows)}")
    T1 = (T1_START, WINDOW[1])
    T1B = ("2026-01-01", WINDOW[1])
    trend(rows)
    print("\n## T1 registered (2023-01-01..2026-11-12, spells >= 150 docs)")
    print_t1("T1 B outcome", spells_table(rows, *T1))
    print("\n## T1b (2026 only)")
    print_t1("T1b B outcome", spells_table(rows, *T1B))
    t1c(rows)
    per_term(rows, *T1B)
    per_term(rows, *T1)
    t2(rows)
    t3(rows)
    t4(rows, *T1B)
    t4(rows, *T1)
    print("\n## Robustness (D_rel; T1 and T1b)")
    lrows, big = loso(rows)
    print("largest site dropped per province:", dict(sorted(big.items())))
    variants = [
        ("leave-largest-site-out", lrows, {}, None),
        ("drop fj and zj", [r for r in rows if r["prov"] not in ("fj", "zj")], {}, None),
        ("sh07 treated", rows, {"sh07": True}, None),
        ("A outcome", rows, {"out": "A"}, None),
        ("provincial-level documents only", [r for r in rows if r["lvl"] == "provincial"], {"minn": 100}, None),
        ("genre promulgation", [r for r in rows if r["genre"] == "promulgation"], {"minn": 100}, None),
        ("genre implementing", [r for r in rows if r["genre"] == "implementing"], {"minn": 100}, None),
        ("genre readout", [r for r in rows if r["genre"] == "readout"], {"minn": 100}, None),
        ("genre other", [r for r in rows if r["genre"] == "other"], {"minn": 100}, None),
    ]
    print("| variant | window | assoc cells (docs) | non cells (docs) | Y assoc | Y non | P assoc | P non | D_rel | perm p |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for label, rs, kw, _ in variants:
        for wl, w in (("T1", T1), ("T1b", T1B)):
            tab = spells_table(rs, *w, **kw)
            c = contrast(tab)
            if not c:
                print(f"| {label} | {wl} | (empty group) | | | | | | | |")
                continue
            print(f"| {label} | {wl} | {c['nt']} ({c['nt_docs']}) | {c['nu']} ({c['nu_docs']}) | {fmt(c['Yt'])} | "
                  f"{fmt(c['Yu'])} | {fmt(c['Pt'])} | {fmt(c['Pu'])} | {fmt(c['d_rel'], 3)} | {fmt(perm_p(tab), 3)} |")
    # ---- Amendment 2: clean population -----
    cr = clean(rows)
    print(f"\n## CLEAN population (Amendment 2): {len(cr)} of {len(rows)} rows")
    print_t1("T1 clean", spells_table(cr, *T1))
    print_t1("T1b clean", spells_table(cr, *T1B))
    t1c(cr)
    t2(cr)
    t4(cr, *T1B)
    lcr, _ = loso(cr)
    for wl, w in (("T1", T1), ("T1b", T1B)):
        tab = spells_table(lcr, *w)
        c = contrast(tab)
        print(f"clean + leave-largest-site-out {wl}: D_rel {fmt(c['d_rel'], 3)} perm p {fmt(perm_p(tab), 3)} "
              f"(assoc {c['nt']} cells {c['nt_docs']} docs; non {c['nu']} cells {c['nu_docs']} docs)")
        tab = spells_table(cr, *w, sh07=True)
        c = contrast(tab)
        print(f"clean + sh07 treated {wl}: D_rel {fmt(c['d_rel'], 3)} perm p {fmt(perm_p(tab), 3)}")
    exploratory(rows, *T1B, label="registered")
    exploratory(cr, *T1B, label="clean")
    # intensity version (per 10k chars), T1b
    print("\n### intensity per 10,000 body characters, 2026, pooled by treatment")
    for lab, cond in (("assoc core", lambda a: a == "core"), ("non", lambda a: a == "")):
        rs = [r for r in rows if T1B[0] <= r["date"] <= T1B[1] and (sp := spell_of(r["prov"], r["date"])) and cond(sp[2])]
        print(f"{lab}: n {len(rs)} B {fmt(intensity(rs, 'B'), 3)} A {fmt(intensity(rs, 'A'), 3)} P {fmt(intensity(rs, 'P'), 3)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(_ROOT / "documents.db"))
    ap.add_argument("--repo", default=str(_ROOT))
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out", default="/tmp/shih/flags.tsv")
    ap.add_argument("--flags", default="/tmp/shih/flags.tsv")
    args = ap.parse_args()
    if args.coverage:
        coverage(args)
    if args.measure:
        measure(args)
    if args.analyze:
        analyze(args)


if __name__ == "__main__":
    main()
