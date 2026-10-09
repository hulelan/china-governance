"""Fixed-site panels, and the sign-flip check that makes them mandatory.

Six memos state that a series on this corpus needs a fixed-site panel; two built
one by hand (`authority_invocation.py`, `site_selection_gdp.py`) and
`one-vote-veto.md` §limitations ships without one and says so. The reason is
`rmb-coverage.md` §4 trap 3: the corpus grows by ACQUISITION, not only by
publication — 2026 holds ~3x 2024's documents because we crawled more sites — so
a raw count series measures our crawl schedule as much as China's policy output.
There the 美元:人民币 ratio HALVED on a fixed panel while RISING uncontrolled. A
sign reversal, not a magnitude error.

So this module does not merely offer a panel. `series()` always returns raw and
panel together plus a `verdict`, and the verdict compares the two trend SIGNS.
A caller cannot get the raw series without also being told whether the panel
contradicts it. That is the one check this project has repeatedly needed and
repeatedly had to remember by hand.

Definitions
-----------
A panel site is one holding >= `min_per_year` dated documents in EVERY complete
year of the window. The final year is treated as partial (a crawl mid-year is not
a publication drought) and is reported but never gates membership.

Verdicts
--------
  ok            panel and raw agree in sign; report either, prefer panel
  sign_flip     they DISAGREE — the raw series is composition-driven, report panel only
  thin          fewer than MIN_SERIES_DOCS documents on the panel; state n, do not trend
  empty         the term is absent from the panel

Usage
  python3 scripts/rnd/analysis/panel.py --describe
  python3 scripts/rnd/analysis/panel.py --term 出口管制 --term 视频监控
  python3 scripts/rnd/analysis/panel.py --term 雪亮工程 --level central
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))

from fts import term_ids, like_count  # noqa: E402

DB = ROOT / "documents.db"

# Below this many panel documents a term gets a count, never a trend. 雪亮工程
# (173 corpus-wide, a handful of sites) is the motivating case: related-literature.md
# records its suggestive 2017->2022 shape and deliberately refuses to call it a finding.
MIN_SERIES_DOCS = 120

# A panel year needs this many documents from a site. 30 is what authority_invocation.py
# used; it is a floor on "this site was actively publishing", not a sample-size claim.
DEFAULT_MIN_PER_YEAR = 30


@dataclass(frozen=True)
class Panel:
    """The site set a series may be counted over, plus why it is that set."""
    sites: frozenset
    years: tuple          # complete years every panel site covers
    partial: tuple        # trailing year(s) reported but not gating
    min_per_year: int
    level: str | None
    n_candidate_sites: int
    denom: dict           # year -> panel documents that year (the honest denominator)

    def __str__(self):
        return (f"panel: {len(self.sites)} of {self.n_candidate_sites} sites, "
                f"{self.years[0]}-{self.years[-1]} (>={self.min_per_year}/yr)"
                + (f", level={self.level}" if self.level else ""))


@dataclass(frozen=True)
class Series:
    """A term's yearly counts, raw and panelled, with the sign check applied."""
    term: str
    index_used: str
    raw: dict
    panel: dict
    denom: dict
    verdict: str
    raw_rho: float
    panel_rho: float

    @property
    def n_panel(self):
        return sum(self.panel.values())

    @property
    def reportable(self):
        """True only when a TREND may be stated. 'thin'/'empty' still permit counts."""
        return self.verdict in ("ok", "sign_flip")

    def share(self):
        """Panel count as a share of panel output — the composition-free quantity."""
        return {y: (self.panel.get(y, 0) / self.denom[y] if self.denom.get(y) else 0.0)
                for y in sorted(self.denom)}


def _spearman(pairs):
    """Rank correlation of (x, y) without scipy. Returns 0.0 for <3 points."""
    pairs = [(x, y) for x, y in pairs if y is not None]
    n = len(pairs)
    if n < 3:
        return 0.0

    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:                      # average ties, or a flat series reads as a trend
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return 0.0 if dx == 0 or dy == 0 else num / (dx * dy)


def build_panel(conn, *, min_per_year=DEFAULT_MIN_PER_YEAR, first_year=2013,
                last_year=None, level=None, require_body=True):
    """Sites publishing >= min_per_year dated docs in every complete year of the window.

    `level` filters on doc_identity.admin_level_doc (per-DOCUMENT level), never on
    sites.admin_level — CLAUDE.md: 21% of documents differ from their site's level,
    and `department` is a kind of body, not a tier.
    """
    body = "AND COALESCE(d.body_text_cn,'') != ''" if require_body else ""
    join = ""
    where_level = ""
    if level:
        join = "JOIN doc_identity i ON i.doc_id = d.id"
        where_level = "AND i.admin_level_doc = ?"
    params = [level] if level else []

    rows = conn.execute(f"""
        SELECT d.site_key, CAST(strftime('%Y', d.date_written, 'unixepoch') AS INT) yr,
               COUNT(*)
        FROM documents d {join}
        WHERE d.date_written > 0 {body} {where_level}
        GROUP BY d.site_key, yr
    """, params).fetchall()

    if last_year is None:
        last_year = max((y for _, y, _ in rows if y), default=first_year)
    cnt = {(sk, y): n for sk, y, n in rows if y is not None}
    candidates = {sk for sk, _ in cnt}

    complete = tuple(y for y in range(first_year, last_year))   # last_year is partial
    partial = (last_year,)
    if not complete:
        complete, partial = (first_year,), ()

    sites = frozenset(sk for sk in candidates
                      if all(cnt.get((sk, y), 0) >= min_per_year for y in complete))
    denom = {y: sum(cnt.get((sk, y), 0) for sk in sites) for y in complete + partial}
    return Panel(sites, complete, partial, min_per_year, level, len(candidates), denom)


# Below this |rho| a trend is not asserted in either direction, so two weak
# opposite-signed rhos are noise rather than a contradiction worth flagging.
RHO_FLOOR = 0.3


def classify(n_panel, raw_rho, panel_rho):
    """The verdict, as a pure function so it is testable without FTS tables.

    Order matters: `thin` wins over `sign_flip`, because with too few documents
    both rhos are unreliable and "the raw series contradicts the panel" would be
    an overclaim about noise.
    """
    if n_panel < MIN_SERIES_DOCS:
        return "thin"
    if (raw_rho * panel_rho < 0
            and abs(raw_rho) > RHO_FLOOR and abs(panel_rho) > RHO_FLOOR):
        return "sign_flip"
    return "ok"


def series(conn, term, panel, *, column="title_and_body"):
    """A term's yearly counts raw and panelled, with the sign-flip verdict.

    Term lookup goes through fts.term_ids, which routes to the index that can
    actually see the term (a 2-char term is invisible to the trigram index and
    returns a clean 0 — see fts.py).
    """
    ids, index_used = term_ids(conn, term)
    if not ids:
        return Series(term, index_used, {}, {}, panel.denom, "empty", 0.0, 0.0)

    years = panel.years + panel.partial
    raw = {y: 0 for y in years}
    pan = {y: 0 for y in years}
    idl = list(ids)
    for chunk in (idl[i:i + 900] for i in range(0, len(idl), 900)):
        q = ",".join("?" * len(chunk))
        for sk, yr, n in conn.execute(f"""
            SELECT site_key, CAST(strftime('%Y', date_written, 'unixepoch') AS INT) yr,
                   COUNT(*)
            FROM documents WHERE id IN ({q}) AND date_written > 0
            GROUP BY site_key, yr
        """, chunk):
            if yr in raw:
                raw[yr] += n
                if sk in panel.sites:
                    pan[yr] += n

    n_panel = sum(pan.values())
    # Trend on the SHARE for the panel (composition-free) and on the COUNT for raw,
    # because the raw series' whole problem is that it has no honest denominator.
    raw_rho = _spearman([(y, raw[y]) for y in panel.years])
    sh = {y: (pan[y] / panel.denom[y] if panel.denom.get(y) else 0.0) for y in panel.years}
    panel_rho = _spearman([(y, sh[y]) for y in panel.years])

    return Series(term, index_used, raw, pan, panel.denom,
                  classify(n_panel, raw_rho, panel_rho), raw_rho, panel_rho)


_VERDICT_NOTE = {
    "ok": "panel and raw agree in sign — report the panel share",
    "sign_flip": "RAW CONTRADICTS PANEL — the raw series is composition-driven, report panel only",
    "thin": f"fewer than {MIN_SERIES_DOCS} panel docs — state n, do NOT state a trend",
    "empty": "absent from the panel",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--term", action="append", default=[],
                    help="a lexical term to series (repeatable)")
    ap.add_argument("--level", help="doc_identity.admin_level_doc filter")
    ap.add_argument("--min-per-year", type=int, default=DEFAULT_MIN_PER_YEAR)
    ap.add_argument("--first-year", type=int, default=2013)
    ap.add_argument("--describe", action="store_true", help="print the panel and exit")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    p = build_panel(conn, min_per_year=args.min_per_year,
                    first_year=args.first_year, level=args.level)
    print(p)
    print(f"  sites: {' '.join(sorted(p.sites))}\n")
    print("  panel documents per year:")
    for y in p.years + p.partial:
        tag = "  (partial)" if y in p.partial else ""
        print(f"    {y}  {p.denom.get(y, 0):>7,}{tag}")
    if args.describe or not args.term:
        return

    for term in args.term:
        s = series(conn, term, p)
        print(f"\n=== {term}  [index={s.index_used}]  verdict={s.verdict.upper()} ===")
        print(f"  {_VERDICT_NOTE[s.verdict]}")
        if s.verdict == "empty":
            print(f"  (LIKE on title finds {like_count(conn, term)} titles — "
                  "if nonzero the term is present but unindexable)")
            continue
        print(f"  panel n={s.n_panel:,}   raw rho={s.raw_rho:+.3f}   "
              f"panel-share rho={s.panel_rho:+.3f}")
        print(f"  {'year':<6}{'raw':>8}{'panel':>8}{'denom':>9}{'share':>9}")
        sh = s.share()
        for y in p.years + p.partial:
            star = " *" if y in p.partial else ""
            print(f"  {y:<6}{s.raw.get(y, 0):>8,}{s.panel.get(y, 0):>8,}"
                  f"{s.denom.get(y, 0):>9,}{sh.get(y, 0) * 100:>8.2f}%{star}")


if __name__ == "__main__":
    main()
