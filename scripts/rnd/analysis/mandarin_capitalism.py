"""Replicate the PREMISE of Chang & Xiong, "Monetary Policy in Mandarin Capitalism"
(NBER w35562, 2026), on the policy-document record.

THEIR CLAIM. China's repeated credit booms produce no lasting inflation because the
regime is oriented to PRODUCTION: credit sustains output and firm balance sheets rather
than final demand, so policy preserves productive capacity instead of managing demand.

WHY THIS CORPUS CAN SAY SOMETHING. Their object is the credit/output relationship, which
needs macro series we do not hold. But the claim rests on a premise about the STATED
ORIENTATION of credit policy, and that is a document fact. The sharp test is conditional,
not marginal: among documents that talk about credit at all, do they talk about production
or about demand? A marginal count of 消费 against 产能 across the whole corpus would answer
a different and much less interesting question.

THE FALSIFIABLE PART. This corpus's best-documented cascade is 以旧换新/提振消费 — an
explicitly DEMAND-side campaign running 2024-26 (`consumption-diffusion.md`). If the regime
is production-oriented in the way w35562 argues, the credit-conditional language should
still be production-dominated, and the consumption campaign should show up as a demand
channel that is NOT a credit channel. If instead credit documents turned demand-side, the
premise is time-bound rather than structural.

Two controls are mandatory here and both are in code:
  * every term is routed through `fts.py`, because 消费 / 内需 / 产能 / 信贷 / 贷款 are all
    TWO characters and invisible to the trigram index (a clean, silent 0 — CLAUDE.md);
  * every trend goes through `panel.py`, which reports the fixed-site share beside the raw
    count and refuses to let a composition artifact read as a trend.

  python3 scripts/rnd/analysis/mandarin_capitalism.py
  python3 scripts/rnd/analysis/mandarin_capitalism.py --first-year 2013
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_here = Path(__file__).resolve()
ROOT = _here.parents[3] if len(_here.parents) > 3 else Path.cwd()
sys.path.insert(0, str(ROOT))

from scripts.rnd.analysis import fts, panel  # noqa: E402

# The credit channel: how policy names the thing being extended.
CREDIT = ("信贷", "贷款", "融资", "再贷款", "社会融资规模")

# What the credit is FOR. Kept deliberately short and concrete — an abstract term like
# 高质量发展 appears on both sides of the production/demand divide and would only blur it.
PRODUCTION = ("实体经济", "制造业", "产能", "产业链", "技术改造", "固定资产投资",
              "供给侧", "保供", "设备更新")
DEMAND = ("消费", "内需", "扩大内需", "促消费", "以旧换新", "消费券",
          "居民收入", "需求侧")


def heading(s):
    print()
    print("=" * 78)
    print(s)
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(ROOT / "documents.db"))
    ap.add_argument("--first-year", type=int, default=2013)
    ap.add_argument("--min-per-year", type=int, default=None)
    a = ap.parse_args()

    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)

    heading("1. The term register — which index can see each term at all")
    print("CREDIT:")
    fts.report(conn, CREDIT)
    print("PRODUCTION:")
    fts.report(conn, PRODUCTION)
    print("DEMAND:")
    fts.report(conn, DEMAND)

    heading("2. THE BASELINE — the corpus's own tilt, without which 61% means nothing")
    print("These are long documents; a 政府工作报告 mentions everything. So the conditional")
    print("shares below are only interpretable against the unconditional ones.\n")
    n_total = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE COALESCE(body_text_cn,'') != ''").fetchone()[0]
    fam = {}
    for name, terms in (("production", PRODUCTION), ("demand", DEMAND)):
        u = set()
        for t in terms:
            u |= fts.term_ids(conn, t)[0]
        fam[name] = u
        print("  P(%s)        = %6.1f%%  (%d of %d bodied documents)"
              % (name, 100 * len(u) / n_total, len(u), n_total))
    print("  P(production) / P(demand) = %.2f   <- the corpus's baseline tilt"
          % (len(fam["production"]) / max(len(fam["demand"]), 1)))

    heading("3. THE CONDITIONAL TEST — what do CREDIT documents talk about?")
    print("Share of documents mentioning each credit term that ALSO mention each purpose.")
    print("This is the premise of w35562: credit directed at production, not demand.\n")
    for base in CREDIT:
        try:
            prod = fts.cooccurrence(conn, base, PRODUCTION)
            dem = fts.cooccurrence(conn, base, DEMAND)
        except ValueError as e:
            print("  %s: %s" % (base, e))
            continue
        ids, _ = fts.term_ids(conn, base)
        n = len(ids)
        # union share: a document counts once for the family, not once per term
        p_ids, d_ids = fam["production"], fam["demand"]
        pc, dc = len(ids & p_ids) / n, len(ids & d_ids) / n
        pb = len(p_ids) / n_total
        db = len(d_ids) / n_total
        print("  %-12s n=%-7d  production %5.1f%% (lift %4.2fx)   demand %5.1f%% (lift %4.2fx)"
              % (base, n, 100 * pc, pc / pb if pb else 0, 100 * dc, dc / db if db else 0))
        print("     ratio production:demand = %.2f   (corpus baseline %.2f)"
              % (pc / dc if dc else 0, pb / db if db else 0))
        print("     top production: %s" % ", ".join(
            "%s %.0f%%" % (c, 100 * s) for c, _n, s, _i in prod[:4]))
        print("     top demand    : %s" % ", ".join(
            "%s %.0f%%" % (c, 100 * s) for c, _n, s, _i in dem[:4]))

    heading("4. Did the orientation CHANGE? (fixed-site panel)")
    kw = {"first_year": a.first_year}
    if a.min_per_year is not None:
        kw["min_per_year"] = a.min_per_year
    p = panel.build_panel(conn, **kw)
    print("panel: %d sites of %d candidates, %s-%s (min %d/yr)"
          % (len(p.sites), p.n_candidate_sites, p.years[0], p.years[-1], p.min_per_year))
    print()
    for term in ("信贷", "实体经济", "产能", "消费", "内需", "以旧换新", "设备更新"):
        s = panel.series(conn, term, p)
        print("  %-8s [%-9s] raw rho %+.2f  panel rho %+.2f  n_panel %-6d  %s"
              % (term, s.index_used, s.raw_rho, s.panel_rho,
                 sum(s.panel.values()), s.verdict))
    print()
    print("verdict key: ok = panel and raw agree; sign_flip = raw is composition-driven;")
    print("            thin = too few panel docs to state a trend.")


if __name__ == "__main__":
    main()
