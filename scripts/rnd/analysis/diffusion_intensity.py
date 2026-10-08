#!/usr/bin/env python3
"""Diffusion-intensity index (IP&M 2025) rebuilt on the resolved citation graph.

Their index has two dimensions -- hierarchical effectiveness (the administrative
authority of the adopting documents) and textual intensity (how much text the
adopter devotes) -- applied to 9,091 low-carbon documents. Two things only our
scale can test:

  * are the dimensions independent? If not, the composite adds nothing. (They
    are: Spearman -0.085. The reason is that textual intensity is nearly FLAT
    across the hierarchy, so an adopter's level does not predict its length.)
  * what does "hierarchical effectiveness" measure when summed over adopters?
    (The adopter COUNT: rho +0.957. Use the per-adopter mean and report n
    separately -- they point in opposite directions, rho -0.271.)

Read-only. See docs/research/diffusion-intensity-index.md for the writeup.

    python3 scripts/rnd/analysis/diffusion_intensity.py
    python3 scripts/rnd/analysis/diffusion_intensity.py --min-adopters 10
    python3 scripts/rnd/analysis/diffusion_intensity.py --weights 4,2,1
"""
import argparse
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

# scripts/rnd/<theme>/<file>.py -> repo root is parents[3] (scripts/README.md).
# Tolerate being run from a copy at a shallower path: a module-level parents[3]
# raises IndexError at import time, which is a silly way for a read-only
# analysis script to die.
_P = Path(__file__).resolve().parents
ROOT = _P[3] if len(_P) > 3 else Path.cwd()
LEVELS = ("provincial", "municipal", "district")


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return float("nan")
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def spearman(xs, ys):
    """Rank correlation with average ranks for ties (no scipy on the droplet)."""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def load(conn):
    """Confirmed adoption events with a body on both sides."""
    return conn.execute(f"""
        SELECT e.anchor_id, e.topic, e.source_level, e.lag_days,
               LENGTH(sd.body_text_cn), LENGTH(ad.body_text_cn)
        FROM diffusion_events e
        JOIN documents sd ON sd.id = e.source_id
        JOIN documents ad ON ad.id = e.anchor_id
        WHERE e.anchor_level = 'central' AND e.source_implementing = 1
          AND e.match_type IN ('citation', 'title_reissue')
          AND e.source_level IN ({','.join('?' * len(LEVELS))})
          AND sd.body_text_cn != '' AND ad.body_text_cn != ''
    """, LEVELS).fetchall()


def build(rows, weights, min_adopters):
    per = defaultdict(list)
    for aid, topic, lvl, lag, slen, alen in rows:
        per[aid].append((topic, lvl, lag, slen, alen))

    anchors = []
    for aid, evs in per.items():
        if len(evs) < min_adopters:
            continue
        h_sum = sum(weights[l] for _, l, _, _, _ in evs)
        anchors.append(dict(
            aid=aid, n=len(evs), H_sum=h_sum, H_mean=h_sum / len(evs),
            T=median([s for _, _, _, s, _ in evs]),
            E=median([s / a for _, _, _, s, a in evs if a]),
            lag=median([g for _, _, g, _, _ in evs if g is not None]),
            topic=next((t for t, _, _, _, _ in evs if t), ""),
        ))
    return anchors


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(ROOT / "documents.db"))
    ap.add_argument("--min-adopters", type=int, default=5,
                    help="per-anchor floor; a distribution needs a few (default 5)")
    ap.add_argument("--weights", default="3,2,1",
                    help="provincial,municipal,district authority weights (theirs: 3,2,1)")
    ap.add_argument("--min-anchors-per-topic", type=int, default=8)
    args = ap.parse_args()

    w = [float(x) for x in args.weights.split(",")]
    if len(w) != 3:
        ap.error("--weights needs exactly three comma-separated numbers")
    weights = dict(zip(LEVELS, w))

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.execute("PRAGMA cache_size=-20000")
    rows = load(conn)
    anchors = build(rows, weights, args.min_adopters)
    print(f"adoption events usable: {len(rows):,}")
    print(f"anchors with >={args.min_adopters} adopters: {len(anchors):,}  "
          f"weights={weights}")
    if len(anchors) < 2:
        print("not enough anchors to correlate"); return

    H = [a["H_mean"] for a in anchors]
    Hs = [a["H_sum"] for a in anchors]
    T = [a["T"] for a in anchors]
    E = [a["E"] for a in anchors]
    N = [float(a["n"]) for a in anchors]

    print("\n--- are the two dimensions independent? (Spearman over anchors) ---")
    for label, pair in (("H_mean (authority per adopter) vs T (text length)", (H, T)),
                        ("H_mean                         vs E (elaboration)", (H, E)),
                        ("H_sum  (raw effectiveness)     vs T               ", (Hs, T)),
                        ("H_sum                          vs n_adopters      ", (Hs, N)),
                        ("T                              vs n_adopters      ", (T, N)),
                        ("H_mean                         vs n_adopters      ", (H, N))):
        print(f"  {label} : {spearman(*pair):+.3f}")
    print("  (H_sum vs n is near-identity by construction — that IS the finding)")

    print("\n--- textual intensity BY adopter level ---")
    by = defaultdict(list)
    for _aid, _tp, lvl, _lag, slen, alen in rows:
        by[lvl].append((slen, slen / alen if alen else None))
    for lvl in LEVELS:
        v = by[lvl]
        if not v:
            continue
        print(f"  {lvl:<11} n={len(v):>6,}  median chars={median([a for a, _ in v]):>7,.0f}"
              f"  median elaboration={median([b for _, b in v if b]):.2f}")

    print("\n--- per-area index ---")
    tp = defaultdict(list)
    for a in anchors:
        if a["topic"]:
            tp[a["topic"]].append(a)
    print(f"  {'area':<22}{'anchors':>8}{'med n':>7}{'H_mean':>9}"
          f"{'T chars':>10}{'elab':>7}{'lag d':>8}")
    out = []
    for t, A in tp.items():
        if len(A) < args.min_anchors_per_topic:
            continue
        lg = [a["lag"] for a in A if not math.isnan(a["lag"])]
        out.append((median([a["H_mean"] for a in A]), t, len(A),
                    median([float(a["n"]) for a in A]), median([a["T"] for a in A]),
                    median([a["E"] for a in A]), median(lg) if lg else float("nan")))
    for h, t, n, mn, t_, e_, l in sorted(out, reverse=True):
        print(f"  {t:<22}{n:>8}{mn:>7.0f}{h:>9.2f}{t_:>10,.0f}{e_:>7.2f}{l:>8.0f}")

    print("\n--- does breadth trade off against authority? quintiles of n_adopters ---")
    srt = sorted(anchors, key=lambda a: a["n"])
    k = max(1, len(srt) // 5)
    for i in range(0, len(srt), k):
        chunk = srt[i:i + k]
        if len(chunk) < k // 2:
            break
        print(f"  n={median([float(a['n']) for a in chunk]):>5.0f}  "
              f"H_mean={median([a['H_mean'] for a in chunk]):.2f}  "
              f"T={median([a['T'] for a in chunk]):>7,.0f}  "
              f"elab={median([a['E'] for a in chunk]):.2f}  anchors={len(chunk)}")


if __name__ == "__main__":
    main()
