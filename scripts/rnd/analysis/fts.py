#!/usr/bin/env python3
"""Route a search term to the FTS index that can actually see it.

THE BUG THIS EXISTS TO PREVENT, six times in one session (2026-10-08/09):

`documents.db` carries two FTS5 indexes over the same columns, and each is blind
to a different class of term:

  doc_search      tokenize='trigram'   -> cannot match fewer than 3 characters
  doc_search_seg  jieba-segmented      -> cannot match a compound that jieba splits

Both failures return a clean **0** rather than an error, so a wrong index does not
look wrong. Measured on the live corpus:

  美元            trigram 0        seg 8,454
  李强            trigram 0        seg 1,614
  跨境人民币       trigram 587      seg 0        (jieba splits it: 跨境 + 人民币)
  耐心资本         trigram 504      seg 0

AND IT CAN REVERSE A COMPARISON, which is worse than hiding a count. Asking
whether the 尽职免责 blame-shield belongs to lending or to funds, a trigram-only
run returned:

  信贷 0%   贷款 0%   银行 0%      <- all 2-char: FALSE ZEROS
  创业投资 28%   股权投资 24%   引导基金 18%

which reads as a clean "it is about funds". Routed properly the answer is the
opposite: 融资 59%, 银行 50%, 贷款 49%, 信贷 41%. The three lending terms were
two characters and every fund term was three or four; nothing else differed.

So: never pick the index by hand. Call `term_ids` / `term_counts`, which route by
length and report which index answered.

(`web/services/documents.py` already gets this right — it tries the segmented
index first and only falls back to trigram at >= 3 chars. This module is for the
ad-hoc analysis scripts, which query one index directly.)
"""
import sqlite3

TRIGRAM_MIN = 3          # fts5 tokenize='trigram' cannot match a shorter needle
TRIGRAM = "doc_search"
SEGMENTED = "doc_search_seg"


def index_for(term: str) -> str:
    """Which index can see `term`. Length is the only thing that decides it."""
    if not term:
        raise ValueError("empty search term")
    return TRIGRAM if len(term) >= TRIGRAM_MIN else SEGMENTED


def term_ids(conn, term: str, *, index: str = None) -> tuple[set, str]:
    """(document ids containing `term`, the index that answered).

    `index` forces a choice and is only for deliberately probing a known blind
    spot — it RAISES if that index cannot see the term, because the whole point
    is that the blind case is otherwise silent.
    """
    auto = index_for(term)
    if index is None:
        index = auto
    elif index == TRIGRAM and len(term) < TRIGRAM_MIN:
        raise ValueError(
            f"{term!r} is {len(term)} chars; {TRIGRAM} needs >= {TRIGRAM_MIN} and "
            f"would return a silent 0. Use {SEGMENTED} (or drop `index=`).")
    # A phrase query keeps a trigram match contiguous; the segmented index takes
    # the bare token (quoting a single token is harmless but needless).
    arg = f'"{term}"' if index == TRIGRAM else term
    try:
        rows = conn.execute(
            f"SELECT rowid FROM {index} WHERE {index} MATCH ?", (arg,))
        return {r[0] for r in rows}, index
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            raise RuntimeError(
                f"{index} is absent from this database. Build it with "
                f"scripts/build_search_index{'_seg' if index == SEGMENTED else ''}.py") from e
        raise


def term_counts(conn, terms) -> list[tuple]:
    """[(term, n_docs, index), …] in the order given. Print the index: a reader
    who cannot see which index answered cannot tell a real 0 from a blind one."""
    out = []
    for t in terms:
        ids, idx = term_ids(conn, t)
        out.append((t, len(ids), idx))
    return out


def report(conn, terms, *, file=None) -> list[tuple]:
    """term_counts, printed with the index column, and a loud note on any zero."""
    rows = term_counts(conn, terms)
    width = max((len(t) for t, _n, _i in rows), default=4)
    for t, n, idx in rows:
        flag = "   <- zero: real, or is the term in the wrong register?" if n == 0 else ""
        print(f"  {t:<{width}}  {n:>8,}  [{idx}]{flag}", file=file)
    return rows


def cooccurrence(conn, base: str, contexts) -> list[tuple]:
    """[(context, n_both, share_of_base, index), …] — the shape that got reversed.

    Every context is routed independently, so a 2-char context and a 4-char one
    are directly comparable. That comparability is the entire point.
    """
    base_ids, _ = term_ids(conn, base)
    if not base_ids:
        raise ValueError(f"base term {base!r} matched nothing — check its register first")
    out = []
    for c in contexts:
        ids, idx = term_ids(conn, c)
        n = len(base_ids & ids)
        out.append((c, n, n / len(base_ids), idx))
    return sorted(out, key=lambda r: -r[1])


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    _P = Path(__file__).resolve().parents
    root = _P[3] if len(_P) > 3 else Path.cwd()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terms", nargs="+")
    ap.add_argument("--db", default=str(root / "documents.db"))
    ap.add_argument("--cooccur-with", metavar="BASE",
                    help="report each term's co-occurrence with BASE instead of its count")
    a = ap.parse_args()
    cx = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    cx.execute("PRAGMA cache_size=-40000")
    if a.cooccur_with:
        base_n = len(term_ids(cx, a.cooccur_with)[0])
        print(f"base {a.cooccur_with}: {base_n:,} documents")
        w = max(len(c) for c in a.terms)
        for c, n, share, idx in cooccurrence(cx, a.cooccur_with, a.terms):
            print(f"  {c:<{w}}  {n:>7,}  {100*share:>5.1f}%  [{idx}]")
    else:
        report(cx, a.terms)
