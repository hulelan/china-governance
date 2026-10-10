"""Parse the 公开07 "三公"经费支出决算表 / 预算表 as a table, with its own validator.

Feasibility and failure analysis: docs/working/sangong-feasibility.md. A regex over the
whole body validated only 160 of 4,378 documents, because the figures live in a table
that PDF extraction renders as flowed text and narrative 预算草案 reports carry dozens
of unrelated numbers. This reads the NAMED table instead.

THE SCHEMA is fixed and published (公开07 表), 12 columns:

    预算数:  1 合计  2 因公出国(境)费  3 公务用车小计  4 购置费  5 运行费  6 公务接待费
    决算数:  7 合计  8 因公出国(境)费  9 公务用车小计 10 购置费 11 运行费 12 公务接待费

so a row carries FOUR accounting identities, which the documents assert themselves:

    c1 == c2 + c3 + c6      c3 == c4 + c5
    c7 == c8 + c9 + c12     c9 == c10 + c11

A random grab of 12 numbers essentially never satisfies all four, so the validator is
strong enough that a parse either IS the table or is rejected. Two observations per
document — planned and executed — and the gap between them is itself a quantity: whether
austerity shows up as lower plans or as underspending against plan.

  python3 scripts/rnd/analysis/sangong_table.py                 # report
  python3 scripts/rnd/analysis/sangong_table.py --csv out.csv    # the panel
  python3 scripts/rnd/analysis/sangong_table.py --rejects 20     # why rows fail
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

_here = Path(__file__).resolve()
ROOT = _here.parents[3] if len(_here.parents) > 3 else Path.cwd()
DB = ROOT / "documents.db"

# PARSE BY LABEL, NOT BY POSITION. The first version of this read 12 columns after a
# "1 2 ... 12" marker run and validated only 58 of 4,350 documents (worse than the naive
# regex's 160). The data showed why: there are at least THREE layouts, and in one of them
# the column ORDER DIFFERS —
#
#   A  公开07 表 决算: 12 positional columns, 合计 出国 用车(小计 购置 运行) 接待, twice
#   B  city-level:     label-interleaved, "一、因公出国（境）支出 300" … "三、公务接待费 566"
#   C  per-unit:       header names the order as 总计 出国 **接待** 用车, then one row per
#                      sub-unit (本级, 宝安分局, 罗湖分局 …) — many rows per document
#
# Layout C puts 接待 BEFORE 用车, so a positional parser is wrong by construction rather
# than merely incomplete. A label-anchored parser handles all three, and C yields a whole
# sub-panel from one document.
#
# The validator stays the documents' own accounting identity:
#     total == out + car + host        and, when the split is present, car == buy + run
# It is what makes a label grab trustworthy: a wrong number essentially never balances.
TOTAL_LAB = re.compile(r"三公[”\"]?经费(?:合计|总计|支出合计)?|^\s*总\s*计|合\s*计")
LABELS = (
    ("out",  re.compile(r"因公出国[（(]?境?[）)]?(?:费|支出)?")),
    ("car",  re.compile(r"公务用车(?:购置及运行(?:维护)?(?:费|支出)?|费|支出)")),
    ("host", re.compile(r"公务接待(?:费|支出)?")),
    ("buy",  re.compile(r"公务用车购置费?")),
    ("run",  re.compile(r"公务用车运行(?:维护)?费?")),
)
# A figure adjacent to a label: allow thousands separators and 0-2 decimals.
FIG = re.compile(r"-?\d[\d,]*(?:\.\d{1,4})?")
# A COLUMN-NUMBER RUN ends a layout-A header: "… 小计 公务用车购置费 公务用车运行费
# 1 2 3 4 5 6 7 8 9 10 11 12". The identity is happy to build 7 == 1 + 3 + 3 out of it
# (合计 = 出国 + 用车小计 + 接待 read as INDICES), and the resulting row `7.0 1.0 3.0
# 3.0` recurs verbatim across 江门市政府办公室, 大鹏新区发展和财政局, 深圳市住房和建设局
# and 广州市人民政府办公厅 — unrelated units cannot coincidentally spend identical
# amounts, so the numbers are the SCHEMA, not money. Figures are taken after the run.
MARKER_RUN = re.compile(
    r'(?<![\d.])1\s+2\s+3\s+4(?:\s+5)?(?:\s+6)?(?:\s+7)?(?:\s+8)?'
    r'(?:\s+9)?(?:\s+10)?(?:\s+11)?(?:\s+12)?(?![\d.])')
TOL = 0.05
MAX_WANYUAN = 100_000      # 10亿元 — a plausibility bound; the identities alone do not
                           # bound SCALE (0+0+0 and x+0+0 both balance), and the first
                           # version accepted a row reading 3,439,824.70万元.

# AND A GRANULARITY BOUND. Published 三公 figures carry two decimals by convention, while
# a positional marker never does. 109 surviving rows had all four figures whole and <= 12 —
# the 公开07 column indices (7 == 1 + 3 + 3) and narrative item numbers (1.因公出国… 2.公务
# 接待… 3.公务用车). The tell they are not money: 广州市人民政府机关事务管理局 — the body
# that manages the government car fleet — came out at 3.0万元, and 韶关市人民政府办公室 at
# 10.0 against 83.6 in a year that parsed cleanly. The cost of the bound is a genuine unit
# reporting a whole <= 12万元 in every field at once, which the two-decimal convention makes
# rare; rows under 12万元 WITH decimals are untouched (p25 of the panel is 4.85万元).
MARKER_MAX = 12

FIELDS = ("total", "out", "car", "host", "buy", "run")


def _f(s):
    return float(s.replace(",", ""))


def _figs_after(seg, pos, n=4, window=120, floor=0):
    """The first n figures within `window` characters after an IN-SEG offset.

    NOTE the coordinate system: `pos` must be an offset into `seg`, not into the full
    body. Getting that wrong is what made the first label-anchored version return ZERO
    rows — `mt.end()` is a full-body offset, and used as a seg index it looked past the
    end of a 700-character slice for every label beyond position 700.
    """
    pos = max(pos, floor)
    out = []
    for x in FIG.findall(seg[pos:pos + window]):
        try:
            v = _f(x)
        except ValueError:
            continue
        # YEARS ARE NOT MONEY. Layout C carries a 年度 column (2020, 2021, 2022 …) and
        # the candidate search happily balanced combinations built from it: the first run
        # reported 因公出国 at 76% of the total with a p90 of exactly 2022.00, where the
        # hand-checked rows are car-dominant. A bare 4-digit integer in the year range is
        # therefore excluded. A genuine 三公 total of exactly 2022万元 with no decimals
        # would be lost, which is the right trade: conflating it with a year is worse.
        if "." not in x and 1990 <= v <= 2035:
            continue
        out.append(v)
        if len(out) >= n:
            break
    return out


def parse(body: str):
    """-> (list of row dicts, None) or (None, reason).

    CANDIDATES, NOT POSITIONS. "The first figure after the label" is wrong in layout A,
    where the first number after 三公经费支出决算表 is the `07` of 公开07 表. So each field
    offers a few candidate figures and the ACCOUNTING IDENTITY selects the combination
    that balances — the validator is strong enough to do the choosing, which removes the
    need to encode where in each layout the number sits.
    """
    if not body or "三公" not in body:
        return None, "no_anchor"
    rows, seen = [], set()
    for mt in re.finditer(r"三公[”\"]?经费(?:合计|总计|支出合计)?", body):
        base = mt.start()
        seg = body[base:base + 900]
        tot_off = mt.end() - base                 # IN-SEG offset (see _figs_after)
        # A HEADER ROW IS NOT A DATA ROW. In layout C the header names the column
        # order (总计 因公出国 公务接待 公务用车) and the per-field labels then
        # anchor onto the FIRST DATA ROW's figures, which can balance against that
        # row's own total and yield a phantom sub-unit. The tell is that several
        # labels sit between the anchor and the first figure. Layout B has exactly
        # one (一、因公出国（境）支出 300 …), so the bar is two.
        _ff = FIG.search(seg, tot_off)
        if _ff and sum(1 for _, lab in LABELS[:3]
                       if (m := lab.search(seg, tot_off))
                       and m.start() < _ff.start()) >= 2:
            continue
        # Past any column-number run (see MARKER_RUN), for BOTH the total and the
        # per-field candidates — the run sits between the header labels and the first
        # data row, so every field would otherwise read the schema.
        _mr = MARKER_RUN.search(seg)
        floor = _mr.end() if _mr else 0
        tot_cands = _figs_after(seg, tot_off, n=6, window=200, floor=floor)
        if not tot_cands:
            continue
        cands = {}
        for key, lab in LABELS:
            ml = lab.search(seg)
            cands[key] = _figs_after(seg, ml.end(), n=3, floor=floor) if ml else []
        if not all(cands.get(k) for k in ("out", "car", "host")):
            continue
        hit = None
        for tot in tot_cands:
            if not (0 < tot <= MAX_WANYUAN):
                continue
            for o in cands["out"]:
                for c in cands["car"]:
                    for h in cands["host"]:
                        if abs(tot - (o + c + h)) > TOL:
                            continue
                        # the 用车 split, when both parts are present, must also balance
                        split = None
                        for bq in cands.get("buy") or [None]:
                            for rq in cands.get("run") or [None]:
                                if bq is not None and rq is not None \
                                        and abs(c - (bq + rq)) <= TOL:
                                    # FIRST balancing pair, not the last: the
                                    # candidate lists overlap (the `buy` label
                                    # matches inside 公务用车购置及运行费), so
                                    # several pairs can sum to `car` and only the
                                    # nearest-to-label one has 购置/运行 the right
                                    # way round.
                                    split = (bq, rq)
                                    break
                            if split:
                                break
                        if all(v == int(v) and v <= MARKER_MAX
                                   for v in (tot, o, c, h)):
                            continue        # positional markers, not money
                        hit = {"total": tot, "out": o, "car": c, "host": h,
                               "buy": split[0] if split else None,
                               "run": split[1] if split else None}
                        break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                break
        if not hit:
            continue
        sig = (hit["total"], hit["out"], hit["car"], hit["host"])
        if sig in seen:
            continue
        seen.add(sig)
        rows.append(hit)
    if not rows:
        return None, "no_balancing_row"
    return rows, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--csv")
    ap.add_argument("--rejects", type=int, default=0, help="show N rejected docs")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = conn.execute("""
        SELECT id, site_key, title, date_published, COALESCE(body_text_cn,'')
        FROM documents WHERE body_text_cn LIKE '%三公%经费%'
    """).fetchall()
    print("documents naming 三公经费: %d" % len(rows))

    ok, why = [], Counter()
    rejects = []
    n_docs_ok = 0
    for did, sk, t, dp, b in rows:
        got, reason = parse(b)
        if got is None:
            why[reason] += 1
            if len(rejects) < args.rejects:
                rejects.append((did, sk, reason, t))
            continue
        n_docs_ok += 1
        yr = None
        ym = re.search(r"(20\d\d)\s*年", t or "")
        if ym:
            yr = int(ym.group(1))            # the FISCAL year from the title
        # A document may yield several rows (layout C: one per sub-unit).
        for i, d in enumerate(got):
            ok.append(dict(doc_id=did, site=sk, pub=(dp or "")[:10], fiscal_year=yr,
                           row_in_doc=i, title=t, **d))

    print("  VALIDATED rows: %d  (from %d documents; a document can yield several)"
          % (len(ok), n_docs_ok))
    print("  rejected:")
    for r, n in why.most_common():
        print("    %-26s %d" % (r, n))

    if ok:
        yrs = Counter(r["fiscal_year"] for r in ok if r["fiscal_year"])
        print("\n  by fiscal year:",
              " ".join("%s:%d" % kv for kv in sorted(yrs.items())))
        st = Counter(r["site"] for r in ok)
        print("  by site:", " ".join("%s:%d" % kv for kv in st.most_common(10)))
        print("  distinct units (by title stem):",
              len({re.sub(r"20\d\d\s*年度?", "", r["title"] or "") for r in ok}))
        nz = [r for r in ok if r["total"] > 0]
        print("  rows with non-zero 三公 total: %d" % len(nz))
        if nz:
            ex = sorted(r["total"] for r in nz)
            print("  三公 total (万元) median %.2f, p90 %.2f, max %.2f"
                  % (ex[len(ex) // 2], ex[int(len(ex) * .9)], ex[-1]))
            car = sum(r["car"] for r in nz) / sum(r["total"] for r in nz)
            host = sum(r["host"] for r in nz) / sum(r["total"] for r in nz)
            out = sum(r["out"] for r in nz) / sum(r["total"] for r in nz)
            print("  composition of the total: 公务用车 %.0f%%, 公务接待 %.0f%%, "
                  "因公出国 %.0f%%" % (100 * car, 100 * host, 100 * out))

    for did, sk, reason, t in rejects:
        print("  REJECT %-10s %-10s %-24s %s" % (did, sk, reason, (t or "")[:40]))

    if args.csv and ok:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(ok[0].keys()))
            w.writeheader()
            w.writerows(ok)
        print("\nwrote %s (%d rows)" % (args.csv, len(ok)))


if __name__ == "__main__":
    sys.exit(main())
