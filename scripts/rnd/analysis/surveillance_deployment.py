"""The DEPLOYMENT side of AI-tocracy (Beraja/Kao/Yang/Yuchtman, NBER w29466 / QJE 2023).

WHY THIS AND NOT THE PAPER. Their causal chain — local unrest → AI procurement → later
suppression + firm innovation — is out of reach and `related-literature.md` measured why:
政府采购 ∩ 视频监控 is 285 documents (2.9% of 9,664), ∩ 人脸识别 52, ∩ 雪亮工程 29, none
carrying contract values or vendor names, and we hold no protest data at all. What IS
available is the thing the three AI memos do not cover: the programmes themselves are
nameable and datable, so the DIFFUSION of deployment is measurable where its causes are not.

Those memos are about REGULATING AI. This is about DEPLOYING it, which is a different
object with a different level signature.

THE INSTRUCTION THIS FOLLOWS, from the note that scoped it: "whoever runs it starts with
the panel rather than the headline." 雪亮工程 has a suggestive shape (3 docs in 2017, a
2018 local burst, a level inversion by 2021, a 2022 peak of 43, decline since) that was
deliberately NOT reported, because 173 documents is too thin for the fixed-site panel every
series on this corpus needs. So this tool reports the panel verdict FIRST for every term,
and `thin` is an answer rather than something to argue past.

Two controls, both in code rather than in prose:
  * `fts.py` routing — 技防 is 2 characters and a trigram query reports a clean 0;
  * `panel.py` — the fixed-site share beside the raw count, with the sign-flip verdict.

And one lesson from CLAUDE.md applied explicitly: `media` is its own `admin_level`, so
"non-central" is NOT "sub-national". A central-vs-rest cut on this vocabulary would read
Xinhua coverage as local deployment.

  python3 scripts/rnd/analysis/surveillance_deployment.py
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

# Named deployment programmes and the hardware/terms they are built from. Counts in the
# comments are the 2026-10-09 figures this study was scoped from.
DEPLOY = (
    "智慧城市",        # 2,391
    "视频监控",        # 2,116
    "技防",            #   911  (2 chars — segmented index only)
    "社会治安防控",    #   644
    "人脸识别",        #   578
    "雪亮工程",        #   173  (expected `thin`)
    "公共安全视频",    #   171
    "智慧警务",        #    82  (expected `thin`)
)

# The REGULATION vocabulary, for the same-measure contrast in section 4. The AI memos'
# report cascade shares, which are a different unit entirely — comparing a cascade share
# to a vocabulary share would be the error this file exists to avoid.
REGULATE = (
    "生成式人工智能",
    "算法推荐",
    "个人信息保护",
    "数据安全",
    "深度合成",
    "算法备案",
)

# The level axis, split three ways on purpose (CLAUDE.md: `media` is its own level).
LEVELS = {
    "central": ("central",),
    "sub-national gov": ("provincial", "municipal", "district", "department"),
    "media": ("media",),
}


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
    a = ap.parse_args()
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)

    heading("1. Register — which index can see each term, and is it absent or invisible?")
    fts.report(conn, DEPLOY)

    heading("2. THE PANEL VERDICT FIRST (the instruction this study was given)")
    p = panel.build_panel(conn, first_year=a.first_year)
    print("panel: %d sites of %d candidates, %s-%s (min %d dated bodied docs/yr)"
          % (len(p.sites), p.n_candidate_sites, p.years[0], p.years[-1], p.min_per_year))
    print()
    print("  %-14s %-16s %8s %8s %8s  %s"
          % ("term", "index", "n_panel", "raw rho", "panel rho", "verdict"))
    series = {}
    for t in DEPLOY:
        s = panel.series(conn, t, p)
        series[t] = s
        print("  %-14s %-16s %8d %+8.2f %+9.2f  %s"
              % (t, s.index_used, sum(s.panel.values()), s.raw_rho, s.panel_rho, s.verdict))
    usable = [t for t, s in series.items() if s.verdict == "ok"]
    thin = [t for t, s in series.items() if s.verdict == "thin"]
    flipped = [t for t, s in series.items() if s.verdict == "sign_flip"]
    print()
    print("  usable: %s" % (", ".join(usable) or "none"))
    print("  THIN (state n, assert no trend): %s" % (", ".join(thin) or "none"))
    print("  SIGN FLIP (raw is composition-driven): %s" % (", ".join(flipped) or "none"))

    heading("3. Level signature — three ways, because `media` is not sub-national")
    print("  %-14s %7s | %s" % ("term", "total", "  ".join("%-16s" % k for k in LEVELS)))
    for t in DEPLOY:
        ids, _idx = fts.term_ids(conn, t)
        if not ids:
            continue
        idl = list(ids)
        counts = {k: 0 for k in LEVELS}
        for chunk in (idl[i:i + 900] for i in range(0, len(idl), 900)):
            q = ",".join("?" * len(chunk))
            for lvl, n in conn.execute(f"""
                SELECT COALESCE(i.admin_level_doc,'?'), COUNT(*)
                FROM doc_identity i WHERE i.doc_id IN ({q}) GROUP BY 1
            """, chunk):
                for k, vals in LEVELS.items():
                    if lvl in vals:
                        counts[k] += n
        tot = sum(counts.values())
        print("  %-14s %7d | %s" % (t, len(ids), "  ".join(
            "%-16s" % ("%d (%.0f%%)" % (counts[k], 100 * counts[k] / tot) if tot else "0")
            for k in LEVELS)))
    print()
    print("  NOTE: the three columns need not sum to `total` — a document with no")
    print("  doc_identity row, or a level outside these three groups, is counted in none.")

    heading("4. The contrast: REGULATING AI vs DEPLOYING it, on the SAME measure")
    print("  A cascade share from another memo is not comparable to a vocabulary share,")
    print("  so the regulation vocabulary is re-measured here the identical way.\n")
    print("  %-14s %7s | %s" % ("term", "total", "  ".join("%-16s" % k for k in LEVELS)))
    for t in REGULATE:
        ids, _idx = fts.term_ids(conn, t)
        if not ids:
            print("  %-14s %7s | (absent)" % (t, 0))
            continue
        idl = list(ids)
        counts = {k: 0 for k in LEVELS}
        for chunk in (idl[i:i + 900] for i in range(0, len(idl), 900)):
            q = ",".join("?" * len(chunk))
            for lvl, n in conn.execute(f"""
                SELECT COALESCE(i.admin_level_doc,'?'), COUNT(*)
                FROM doc_identity i WHERE i.doc_id IN ({q}) GROUP BY 1
            """, chunk):
                for k, vals in LEVELS.items():
                    if lvl in vals:
                        counts[k] += n
        tot = sum(counts.values())
        print("  %-14s %7d | %s" % (t, len(ids), "  ".join(
            "%-16s" % ("%d (%.0f%%)" % (counts[k], 100 * counts[k] / tot) if tot else "0")
            for k in LEVELS)))


if __name__ == "__main__":
    main()
