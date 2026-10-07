"""Unified (source, parent) pair set for the diffusion-fidelity analyses.

`fidelity-jiangsu.md` §7 found that the citation path sees fewer than half of the
renamed re-issuances the identity layer detects: of the `doc_identity.localized_of`
pairs whose trigger is a provincial text, only 300/645 (GD) and 26/59 (JS) also appear
as resolved citation edges, and the citation-invisible pairs overlap the parent text at
a median 0.41 with 23% relay. `diffusion-fidelity.md` and `fidelity-provincial.md`
built their pair sets from citations (+ `title_reissue`), so their relay figures are
floors. This module is the shared builder those memos lacked: one row per
(source document, parent instrument), carrying every channel that produced it.

Channels (``sources=``):
  citation       a resolved `citations` edge source → parent member, or a
                 `diffusion_events` row with match_type='citation' (the latter adds
                 exact 《》-core refs the resolver left unresolved).
  title_reissue  `diffusion_events` match_type='title_reissue' (the title carries
                 the parent's genre stem; already-cited pairs are excluded there by
                 construction, so overlap with `citation` here comes from the raw edges).
  localized_of   `doc_identity.localized_of` (the source's title stem reappears on a
                 higher text in its own jurisdictional chain; a renaming detector
                 independent of citations and of body text).
  topic_genre    optional, off by default (probable-but-unconfirmed implementation).

Pair rules, identical across channels (so the Venn compares like with like):
  * levels from `doc_identity.admin_level_doc`, never `sites.admin_level`;
    hop = parent level → source level, one of C→P, P→M, M→D, C→M, C→D, P→D;
  * parent canonicalised to its instrument (`instrument_id`): a citation to a mirror
    lands on the canonical member, so channels that name different copies of one text
    meet on one row; source and parent must be different instruments;
  * parent is a framework instrument (`is_framework` + not ABOUT genre + not
    NONISSUE_RE) when ``require_framework`` (default);
  * a non-central parent must share the source's province
    (`build_diffusion_events.province_of`, site-derived); central parents need none;
  * source dated on or after parent (lag_days >= 0; no upper cap, the cap is the
    caller's), Suzhou dates repaired from the URL (fidelity-jiangsu.md §7).

Scoring (moved here from the memo-era sketch in `fidelity-provincial.md` Appendix B /
`diffusion-fidelity.md` Appendix B; no script held it): both bodies > ``min_body``
chars, HTML + whitespace stripped, 150k cap, character 5-grams,
ovlp_src = |S∩A|/|S|, ovlp_anc, jaccard, a boilerplate-stripped ovlp_src_nb, and the
band relay > 0.7 / mid 0.3–0.7 / elab < 0.3.

    python3 scripts/rnd/analysis/pairs.py --report [--db PATH] [--workers 2]
    python3 scripts/rnd/analysis/pairs.py --self-test
    python3 scripts/rnd/analysis/pairs.py --csv out.csv        # the pair table

Library use:
    from pairs import build_pairs
    rows = build_pairs(conn, hops=("P→M",), sources=("citation", "localized_of"))

Read-only: opens nothing for writing and never touches the DB. Memo: pair-channels.md.
"""
import argparse
import csv
import re
import sqlite3
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

_HERE = Path(__file__).resolve()
ROOT = _HERE.parents[3]
DEFAULT_DB = ROOT / "documents.db"
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parents[1] / "citations"))
from build_diffusion_events import (  # noqa: E402
    ABOUT_GENRES, IMPLEMENTING_IDENTITY_GENRES, NONISSUE_RE, _lag, is_framework, identity_has_kind,
    load_site_names, province_of,
)

DEFAULT_HOPS = ("C→P", "P→M", "M→D", "C→M")
ALL_HOPS = ("C→P", "P→M", "M→D", "C→M", "C→D", "P→D")
DEFAULT_SOURCES = ("citation", "title_reissue", "localized_of")
ALL_SOURCES = DEFAULT_SOURCES + ("topic_genre",)
LEVEL_CODE = {"central": "C", "provincial": "P", "municipal": "M", "district": "D"}

# --- 5-gram scoring (from the memo sketches) ---------------------------------
N = 5
BODY_CAP = 150_000
MIN_BODY = 500
RELAY_T, MID_T = 0.7, 0.3
_TAG, _WS = re.compile(r"<[^>]+>"), re.compile(r"\s+")
_FORWARD_RE = re.compile(r"转发")
_SUZHOU_URL_DATE = re.compile(r"/((?:19|20)\d\d)(0[1-9]|1[0-2])/")
BOILER_SAMPLE, BOILER_SHARE = 1000, 0.02


def norm_body(text):
    return _WS.sub("", _TAG.sub("", text or ""))[:BODY_CAP]


def grams(text):
    return {text[i:i + N] for i in range(len(text) - N + 1)}


def band(ovlp):
    if ovlp is None:
        return None
    return "relay" if ovlp > RELAY_T else ("mid" if ovlp >= MID_T else "elab")


def score_bodies(src_body, par_body, boiler=frozenset(), par_grams=None):
    """ovlp_src, ovlp_anc, jaccard, ovlp_src_nb for one (source, parent) body pair.
    Pass ``par_grams`` (grams of the normalised parent) to reuse across sources."""
    S = grams(norm_body(src_body))
    A = par_grams if par_grams is not None else grams(norm_body(par_body))
    if not S or not A:
        return None
    inter = len(S & A)
    S_nb, A_nb = S - boiler, A - boiler
    nb = len(S_nb & A_nb) / len(S_nb) if S_nb else None
    return {
        "ovlp_src": inter / len(S),
        "ovlp_anc": inter / len(A),
        "jaccard": inter / (len(S) + len(A) - inter),
        "ovlp_src_nb": nb,
    }


# --- Load -----------------------------------------------------------------------
def _d10(s):
    return (s or "")[:10]


def _suzhou_date(url, fallback):
    m = _SUZHOU_URL_DATE.search(url or "")
    return f"{m.group(1)}-{m.group(2)}-15" if m else fallback


def load_docs(conn, repair_suzhou_dates=True):
    """id -> dict of the metadata every pair row carries (no bodies)."""
    load_site_names(conn)
    site_level = dict(conn.execute("SELECT site_key, admin_level FROM sites"))
    docs = {}
    kind_col = "i.instrument_kind" if identity_has_kind(conn) else "NULL"
    for row in conn.execute(
            f"""SELECT d.id, d.site_key, d.title, d.date_published, d.algo_doc_type, d.url,
                      i.admin_level_doc, i.instrument_id, i.instrument_role, i.genre,
                      i.date_quality, i.lead_issuer, i.localized_of, i.province, {kind_col}
               FROM documents d JOIN doc_identity i ON i.doc_id = d.id"""):
        (did, site, title, dp, dtype, url, lvl, inst, role, igenre, dq, issuer, loc, iprov,
         ikind) = row
        d = _d10(dp)
        if repair_suzhou_dates and site == "suzhou":
            d = _suzhou_date(url, d)
        docs[did] = {
            "id": did, "site": site, "site_level": site_level.get(site, ""),
            "title": title or "", "date": d, "doc_type": dtype or "",
            "level": lvl or "", "inst": inst if inst is not None else did,
            "role": role or "unique", "genre": igenre or "", "date_quality": dq or "",
            "issuer": issuer or "", "localized_of": loc,
            "kind": ikind,  # doc_identity.instrument_kind (A7); None -> old framework gate
            # per-document province (doc_identity A6) first — npc 地方法规 carry no site
            # province — else the site's
            "prov": iprov or province_of(site),
        }
    return docs


def canonical_map(docs):
    """instrument_id -> canonical doc id (unique docs are their own canonical)."""
    canon = {}
    for d in docs.values():
        if d["role"] == "canonical" or d["inst"] == d["id"]:
            canon.setdefault(d["inst"], d["id"])
    return canon


def parent_is_framework(p):
    """Same path as build_diffusion_events.can_anchor: identity `instrument_kind`
    first (A7), the old algo_doc_type + title gate only when the row has no kind."""
    return (is_framework(p["doc_type"], p["title"], p.get("kind"))
            and p["genre"] not in ABOUT_GENRES
            and not NONISSUE_RE.search(p["title"]))


# --- Build ----------------------------------------------------------------------
def _channel_edges(conn, docs, sources):
    """Yield (source_id, parent_doc_id, channel) from every requested channel."""
    if "citation" in sources:
        for s, t in conn.execute("SELECT source_id, target_id FROM citations WHERE target_id IS NOT NULL"):
            yield s, t, "citation"
    de_types = [c for c in ("citation", "title_reissue", "topic_genre") if c in sources]
    if de_types and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='diffusion_events'").fetchone():
        q = ",".join("?" * len(de_types))
        for s, a, mt in conn.execute(
                f"SELECT source_id, anchor_id, match_type FROM diffusion_events WHERE match_type IN ({q})",
                de_types):
            yield s, a, mt
    if "localized_of" in sources:
        for d in docs.values():
            if d["localized_of"] is not None:
                yield d["id"], d["localized_of"], "localized_of"


def build_pairs(conn, hops=DEFAULT_HOPS, sources=DEFAULT_SOURCES, require_framework=True,
                score=True, min_body=MIN_BODY, workers=1, boiler=True, docs=None,
                repair_suzhou_dates=True, verbose=False):
    """One row per (source_id, parent instrument). See the module docstring for rules.

    Returns a list of dicts with: source_id, parent_id, hop, channels (set),
    source_/parent_ {instrument_id, level, genre, doc_type, issuer, date, province,
    site, site_level, title, date_quality}, lag_days, forwarding (转发 in source
    title), source_implementing, parent_framework, and when ``score``: scored,
    source_len, parent_len, ovlp_src, ovlp_anc, jaccard, ovlp_src_nb, band.
    """
    t0 = time.time()
    hops = set(hops)
    docs = docs if docs is not None else load_docs(conn, repair_suzhou_dates)
    canon = canonical_map(docs)
    pairs = {}  # (source_id, parent_inst) -> row
    dropped = Counter()  # (channel, reason) -> n  (a channel's edge can fail only one rule)
    for s_id, p_doc, ch in _channel_edges(conn, docs, sources):
        s, p0 = docs.get(s_id), docs.get(p_doc)
        if not s or not p0:
            dropped[(ch, "no_identity")] += 1
            continue
        p = docs.get(canon.get(p0["inst"], p_doc), p0)
        if s["inst"] == p["inst"]:
            dropped[(ch, "same_instrument")] += 1
            continue
        sc, pc = LEVEL_CODE.get(s["level"]), LEVEL_CODE.get(p["level"])
        if not sc or not pc:
            dropped[(ch, "level")] += 1
            continue
        hop = f"{pc}→{sc}"
        if hop not in hops:
            dropped[(ch, "hop")] += 1
            continue
        key = (s_id, p["inst"])
        row = pairs.get(key)
        if row is not None:
            row["channels"].add(ch)
            row["parent_member_ids"].add(p_doc)
            continue
        if p["level"] != "central" and (not s["prov"] or s["prov"] != p["prov"]):
            dropped[(ch, "province")] += 1
            continue
        fw = parent_is_framework(p)
        if require_framework and not fw:
            dropped[(ch, "framework")] += 1
            continue
        lag = _lag(s["date"], p["date"]) if s["date"] and p["date"] else None
        if lag is None or lag < 0:
            dropped[(ch, "lag")] += 1
            continue
        pairs[key] = {
            "source_id": s_id, "parent_id": p["id"], "hop": hop, "channels": {ch},
            "parent_member_ids": {p_doc},  # the copies the channels actually named
            "source_instrument_id": s["inst"], "parent_instrument_id": p["inst"],
            "source_level": s["level"], "parent_level": p["level"],
            "source_genre": s["genre"], "parent_genre": p["genre"],
            "source_doc_type": s["doc_type"], "parent_doc_type": p["doc_type"],
            "source_issuer": s["issuer"], "parent_issuer": p["issuer"],
            "source_date": s["date"], "parent_date": p["date"],
            "source_date_quality": s["date_quality"], "parent_date_quality": p["date_quality"],
            "source_province": s["prov"], "parent_province": p["prov"],
            "source_site": s["site"], "parent_site": p["site"],
            "source_site_level": s["site_level"], "parent_site_level": p["site_level"],
            "source_title": s["title"], "parent_title": p["title"],
            "lag_days": lag,
            "forwarding": bool(_FORWARD_RE.search(s["title"])),
            "source_implementing": int(s["genre"] in IMPLEMENTING_IDENTITY_GENRES
                                       or ch == "title_reissue"),
            "parent_framework": fw,
        }
    rows = list(pairs.values())
    if verbose:
        print(f"  pairs: {len(rows)} built in {time.time() - t0:.1f}s")
        for ch in sorted({c for c, _ in dropped}):
            per = {r: n for (c, r), n in dropped.items() if c == ch}
            print(f"    dropped {ch:<14} " + "  ".join(f"{r}={n}" for r, n in sorted(per.items())))
    if score:
        score_pairs(conn, rows, min_body=min_body, workers=workers, boiler=boiler, verbose=verbose)
    return rows


# --- Score ----------------------------------------------------------------------
def _fetch_bodies(conn, ids, min_body):
    """id -> body (capped in SQL) for ids whose body clears the floor; chunked IN."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        q = ",".join("?" * len(chunk))
        for did, body, n in conn.execute(
                f"SELECT id, substr(body_text_cn, 1, {BODY_CAP}), length(body_text_cn) "
                f"FROM documents WHERE id IN ({q}) AND length(body_text_cn) > ?",
                chunk + [min_body]):
            out[did] = (body, n)
    return out


def build_boiler(conn, universe_ids, min_body=MIN_BODY):
    """5-grams present in >= BOILER_SHARE of a stride sample of the pair universe
    (the memos sampled the whole corpus with ORDER BY random(); that is a full body
    scan, so the sample here is deterministic and drawn from the docs being scored)."""
    ids = sorted(universe_ids)
    if not ids:
        return frozenset()
    step = max(1, len(ids) // BOILER_SAMPLE)
    sample = ids[::step][:BOILER_SAMPLE]
    bodies = _fetch_bodies(conn, sample, min_body)
    df = Counter()
    for body, _ in bodies.values():
        df.update(grams(norm_body(body)))
    floor = max(2, int(len(bodies) * BOILER_SHARE))
    return frozenset(g for g, n in df.items() if n >= floor)


def _score_groups(conn, groups, min_body, boiler):
    """groups: list of (parent_id, [parent body candidate ids], [source_ids]).
    The parent body is the canonical member's when it clears the floor, else the
    first named member's that does (a canonical chosen for genre/level/date may be a
    body-less gazette or list-chrome copy). Returns {(src, par): (scores|None,
    source_len, parent_len, parent_body_id)}."""
    out = {}
    ids = {s for _, _, ss in groups for s in ss} | {c for _, cands, _ in groups for c in cands}
    bodies = _fetch_bodies(conn, ids, min_body)
    for par, cands, srcs in groups:
        pid = next((c for c in cands if c in bodies), None)
        pb = bodies.get(pid) if pid is not None else None
        A = grams(norm_body(pb[0])) if pb else None
        for src in srcs:
            sb = bodies.get(src)
            if not pb or not sb or not A:
                out[(src, par)] = (None, sb[1] if sb else 0, pb[1] if pb else 0, pid)
                continue
            out[(src, par)] = (score_bodies(sb[0], None, boiler, par_grams=A), sb[1], pb[1], pid)
    return out


def _score_shard(db_path, groups, min_body, boiler, batch=40):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    out = {}
    for i in range(0, len(groups), batch):
        out.update(_score_groups(conn, groups[i:i + batch], min_body, boiler))
    conn.close()
    return out


def score_pairs(conn, rows, min_body=MIN_BODY, workers=1, boiler=True, verbose=False):
    """Attach 5-gram scores to rows in place (parent grams built once per parent)."""
    t0 = time.time()
    db_path = _db_path_of(conn)
    by_parent, cands = defaultdict(list), defaultdict(set)
    for r in rows:
        by_parent[r["parent_id"]].append(r["source_id"])
        cands[r["parent_id"]] |= r.get("parent_member_ids", set())
    groups = [(p, [p] + sorted(cands[p] - {p}), ss) for p, ss in by_parent.items()]
    universe = {p for p, _, _ in groups} | {s for _, _, ss in groups for s in ss}
    B = build_boiler(conn, universe, min_body) if boiler else frozenset()
    groups.sort(key=lambda g: -len(g[2]))
    results = {}
    if workers > 1 and db_path and len(groups) > workers:
        shards = [groups[k::workers] for k in range(workers)]
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for part in ex.map(_score_shard, [db_path] * workers, shards,
                               [min_body] * workers, [B] * workers):
                results.update(part)
    elif db_path:
        results = _score_shard(db_path, groups, min_body, B)
    else:  # in-memory DB (self-test): score on the live connection
        results = _score_groups(conn, groups, min_body, B)
    for r in rows:
        sc, slen, plen, pid = results.get((r["source_id"], r["parent_id"]), (None, 0, 0, None))
        r["source_len"], r["parent_len"], r["parent_body_id"] = slen, plen, pid
        r["scored"] = sc is not None
        for k in ("ovlp_src", "ovlp_anc", "jaccard", "ovlp_src_nb"):
            r[k] = sc[k] if sc else None
        r["band"] = band(sc["ovlp_src"]) if sc else None
    if verbose:
        n = sum(r["scored"] for r in rows)
        print(f"  scored {n}/{len(rows)} pairs in {time.time() - t0:.1f}s "
              f"(boiler {len(B)} grams, workers {workers})")


def _db_path_of(conn):
    for _, name, path in conn.execute("PRAGMA database_list"):
        if name == "main":
            return path or None
    return None


# --- Report ---------------------------------------------------------------------
def _pct(a, b):
    return f"{100 * a / b:5.1f}%" if b else "   –  "


def _fid(rows):
    """n_scored, median, relay%, mid%, elab% over scored rows."""
    sc = [r for r in rows if r.get("scored")]
    if not sc:
        return 0, None, None, None, None
    v = [r["ovlp_src"] for r in sc]
    bands = Counter(r["band"] for r in sc)
    n = len(sc)
    return n, statistics.median(v), bands["relay"] / n, bands["mid"] / n, bands["elab"] / n


def _fid_line(label, rows, width=34):
    n, med, rl, md, el = _fid(rows)
    if not n:
        return f"  {label:<{width}} {len(rows):>6} {'–':>7}"
    return (f"  {label:<{width}} {len(rows):>6} {n:>7} {med:>7.3f} "
            f"{100 * rl:>6.1f} {100 * md:>6.1f} {100 * el:>6.1f} {round(rl * n):>8}")


def combo_label(chs):
    short = {"citation": "cit", "title_reissue": "title", "localized_of": "loc", "topic_genre": "topic"}
    return "+".join(short[c] for c in sorted(chs, key=list(short).index))


def report(rows, hops=DEFAULT_HOPS, provinces=("gd", "js", "bj", "cq", "sd", "fj")):
    print("\n== 1. Pairs by hop × channel combination (Venn) ==")
    combos = sorted({combo_label(r["channels"]) for r in rows},
                    key=lambda c: (c.count("+"), c))
    print(f"  {'hop':<6}" + "".join(f"{c:>12}" for c in combos) + f"{'total':>10}")
    for hop in hops:
        hr = [r for r in rows if r["hop"] == hop]
        cnt = Counter(combo_label(r["channels"]) for r in hr)
        print(f"  {hop:<6}" + "".join(f"{cnt.get(c, 0):>12}" for c in combos) + f"{len(hr):>10}")
    print("  per channel (a pair counts in every channel that produced it):")
    for hop in hops:
        hr = [r for r in rows if r["hop"] == hop]
        per = Counter(c for r in hr for c in r["channels"])
        print(f"    {hop:<6} " + "  ".join(f"{c}={per[c]}" for c in sorted(per)))

    print("\n== 2. localized_of pairs invisible to the citation channel ==")
    print("  'with body' = source body > floor (a citation can only be extracted from a body;"
          " npc law entries and metadata-only sources never cite anything).")
    print(f"  {'hop':<6}{'province':<10}{'loc pairs':>10}{'no citation':>13}{'share':>8}"
          f"{'with body':>11}{'no cit.':>9}{'share':>8}{'  med ovlp (invisible)':>24}{'relay':>8}")
    for hop in hops:
        hr = [r for r in rows if r["hop"] == hop and "localized_of" in r["channels"]]
        if not hr:
            continue
        for prov in list(provinces) + ["all"]:
            pr = hr if prov == "all" else [r for r in hr if r["source_province"] == prov]
            if not pr:
                continue
            inv = [r for r in pr if "citation" not in r["channels"]]
            wb = [r for r in pr if r.get("source_len", 0) > 0]
            wb_inv = [r for r in wb if "citation" not in r["channels"]]
            n, med, rl, _, _ = _fid(inv)
            print(f"  {hop:<6}{prov:<10}{len(pr):>10}{len(inv):>13}{_pct(len(inv), len(pr)):>8}"
                  f"{len(wb):>11}{len(wb_inv):>9}{_pct(len(wb_inv), len(wb)):>8}"
                  f"{(f'{med:.3f} (n={n})' if n else '–'):>24}{(f'{100 * rl:.1f}%' if n else '–'):>8}")

    hdr = (f"  {'subset':<34} {'pairs':>6} {'scored':>7} {'median':>7} {'relay':>6} {'mid':>6} "
           f"{'elab':>6} {'n relay':>8}")
    print("\n== 3. Fidelity by channel combination ==")
    for hop in hops:
        hr = [r for r in rows if r["hop"] == hop]
        if not hr:
            continue
        print(f"  -- {hop}")
        print(hdr)
        for c in combos:
            cr = [r for r in hr if combo_label(r["channels"]) == c]
            if cr:
                print(_fid_line(c, cr))
        print(_fid_line("citation (any)", [r for r in hr if "citation" in r["channels"]]))
        print(_fid_line("union (all channels)", hr))

    print("\n== 4. Floor correction: P→M, citation-only pair set vs union ==")
    print(hdr)
    pm = [r for r in rows if r["hop"] == "P→M"]
    for prov in list(provinces) + ["all"]:
        pr = pm if prov == "all" else [r for r in pm if r["source_province"] == prov]
        if not pr:
            continue
        cit = [r for r in pr if "citation" in r["channels"]]
        print(_fid_line(f"{prov}: citation (memo basis)", cit))
        print(_fid_line(f"{prov}: union", pr))
        city = [r for r in pr if r["source_site_level"] == "municipal"]
        print(_fid_line(f"{prov}: city portals, citation", [r for r in city if "citation" in r["channels"]]))
        print(_fid_line(f"{prov}: city portals, union", city))
        imp = [r for r in pr if r["source_implementing"]]
        print(_fid_line(f"{prov}: implementing, citation", [r for r in imp if "citation" in r["channels"]]))
        print(_fid_line(f"{prov}: implementing, union", imp))
    print("\n  Relay band > 0.7, mid 0.3–0.7, elab < 0.3 on ovlp_src (share of the source's 5-grams in the parent).")


# --- CSV ------------------------------------------------------------------------
def write_csv(rows, path):
    if not rows:
        return
    cols = [k for k in rows[0] if k not in ("channels", "parent_member_ids")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["channels"] + cols)
        for r in rows:
            w.writerow(["|".join(sorted(r["channels"]))] + [r.get(c) for c in cols])


# --- Self-test ------------------------------------------------------------------
def _fake_body(seed, n=1200):
    """Deterministic pseudo-Chinese body: n chars drawn from a seeded LCG."""
    x, out = seed * 2654435761 % (2 ** 32), []
    for _ in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        out.append(chr(0x4E00 + x % 3000))
    return "".join(out)


def _self_test_db():
    c = sqlite3.connect(":memory:")
    c.executescript("""
    CREATE TABLE sites(site_key TEXT PRIMARY KEY, name TEXT, admin_level TEXT);
    CREATE TABLE documents(id INTEGER PRIMARY KEY, site_key TEXT, title TEXT, date_published TEXT,
                           algo_doc_type TEXT, url TEXT, body_text_cn TEXT);
    CREATE TABLE doc_identity(doc_id INTEGER PRIMARY KEY, admin_level_doc TEXT, level_source TEXT,
                              instrument_id INTEGER, instrument_role TEXT, genre TEXT,
                              date_quality TEXT, lead_issuer TEXT, localized_of INTEGER, province TEXT,
                              instrument_kind TEXT);
    CREATE TABLE citations(id INTEGER PRIMARY KEY, source_id INTEGER, target_ref TEXT, target_id INTEGER,
                           citation_type TEXT, source_level TEXT, target_level TEXT);
    CREATE TABLE diffusion_events(id INTEGER PRIMARY KEY, source_id INTEGER, anchor_id INTEGER,
                                  match_type TEXT, lag_days INTEGER, anchor_level TEXT);
    """)
    c.executemany("INSERT INTO sites VALUES (?,?,?)", [
        ("gov", "State Council", "central"), ("gd", "广东省", "provincial"),
        ("huizhou", "Huizhou", "municipal"), ("jieyang", "Jieyang", "municipal"),
        ("suzhou", "Suzhou Municipality", "municipal"), ("szlhq", "Longhua District", "district"),
        ("fgw", "深圳市发展和改革委员会", "department"),
    ])
    B = _fake_body
    half = B(1)[:600] + B(9)[:600]           # half the central text, half new
    docs = [
        # id, site, title, date, doc_type, url, body, level, inst, role, genre, dq, issuer, localized_of
        (1, "gov", "国务院关于印发推动消费品以旧换新行动方案的通知", "2024-03-01", "action_plan", "", B(1),
         "central", 1, "canonical", "promulgation", "good", "国务院", None),
        (2, "gd", "广东省推动消费品以旧换新行动方案", "2024-04-01", "action_plan", "", B(1),
         "provincial", 2, "unique", "implementing", "good", "广东省人民政府", 1),
        (3, "huizhou", "惠州市推动消费品以旧换新行动方案", "2024-05-01", "action_plan", "", B(1),
         "municipal", 3, "unique", "implementing", "good", "惠州市人民政府", 2),
        (4, "jieyang", "揭阳市推动消费品以旧换新实施方案", "2024-06-01", "action_plan", "", half,
         "municipal", 4, "unique", "implementing", "good", "揭阳市人民政府", 2),
        (5, "suzhou", "苏州市推动消费品以旧换新实施方案", "2024-06-01", "action_plan",
         "http://www.suzhou.gov.cn/szsrmzf/szfwj/202406/x.shtml", B(5),
         "municipal", 5, "unique", "implementing", "good", "苏州市人民政府", None),
        (6, "gd", "《广东省推动消费品以旧换新行动方案》解读", "2024-04-02", "explainer", "", B(1),
         "provincial", 6, "unique", "explainer", "good", "", None),
        (7, "huizhou", "惠州市关于早于省文的通知", "2024-03-15", "notice", "", B(7),
         "municipal", 7, "unique", "promulgation", "good", "", None),
        (8, "szlhq", "龙华区短文", "2024-07-01", "notice", "", B(8)[:100],
         "district", 8, "unique", "promulgation", "good", "", None),
        (9, "fgw", "深圳市发展改革委转发广东省推动消费品以旧换新行动方案的通知", "2024-05-10",
         "notice", "", B(1), "municipal", 9, "unique", "implementing", "good", "", None),
        (10, "huizhou", "转载：广东省推动消费品以旧换新行动方案", "2024-04-05", "action_plan", "", B(1),
         "provincial", 2, "mirror", "promulgation", "good", "", None),   # mirror of 2
        (11, "szlhq", "龙华区推动消费品以旧换新工作方案", "2024-08-01", "work_plan", "", B(11),
         "district", 11, "unique", "implementing", "good", "", 3),
        (12, "suzhou", "苏州市工作要点", "2023-02-09", "notice",
         "http://www.suzhou.gov.cn/szsrmzf/szfwj/202206/y.shtml", B(12),
         "municipal", 12, "unique", "promulgation", "good", "", None),
    ]
    c.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?)", [d[:7] for d in docs])
    # instrument_kind (A7) mirrors the old gate here so the fixture's expectations hold
    # through the identity path; a NULL would exercise the fallback instead.
    c.executemany("INSERT INTO doc_identity VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  [(d[0], d[7], "test", d[8], d[9], d[10], d[11], d[12], d[13], None,
                    "framework" if is_framework(d[4], d[2]) else "other") for d in docs])
    c.executemany("INSERT INTO citations(source_id, target_ref, target_id, citation_type, source_level, target_level) "
                  "VALUES (?,?,?,?,?,?)", [
        (2, "x", 1, "named", "provincial", "central"),     # C→P citation (+ localized_of 2→1)
        (3, "x", 10, "named", "municipal", "provincial"),  # cites the MIRROR of 2 → canonicalised to 2
        (5, "x", 2, "named", "municipal", "provincial"),   # cross-province (js→gd): dropped
        (7, "x", 2, "named", "municipal", "provincial"),   # negative lag: dropped
        (3, "x", 6, "named", "municipal", "provincial"),   # parent is an explainer: dropped
        (8, "x", 3, "named", "district", "municipal"),     # M→D, source body < 500: kept, unscored
        (10, "x", 2, "named", "provincial", "provincial"), # same instrument: dropped
        (9, "x", 2, "named", "municipal", "provincial"),   # 转发 notice, relay
        (12, "x", 1, "named", "municipal", "central"),     # Suzhou stamped 2023 → URL says 2022-06 < anchor: dropped
    ])
    c.executemany("INSERT INTO diffusion_events(source_id, anchor_id, match_type, lag_days, anchor_level) "
                  "VALUES (?,?,?,?,?)", [
        (4, 1, "title_reissue", 92, "central"),   # C→M title_reissue
        (3, 2, "citation", 30, "provincial"),     # duplicate of the raw edge (via mirror) → one row
        (4, 2, "topic_genre", 61, "provincial"),  # off by default
    ])
    c.commit()
    return c


def self_test():
    conn = _self_test_db()
    rows = build_pairs(conn, hops=ALL_HOPS, sources=DEFAULT_SOURCES, boiler=False)
    by = {(r["source_id"], r["parent_id"]): r for r in rows}
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    check("1 C→P citation+localized_of merge on one row, relay (identical bodies)",
          (2, 1) in by and by[(2, 1)]["hop"] == "C→P"
          and by[(2, 1)]["channels"] == {"citation", "localized_of"} and by[(2, 1)]["band"] == "relay")
    check("2 citation to a mirror is canonicalised to the instrument's canonical (3→10 lands on 2)",
          (3, 2) in by and (3, 10) not in by and by[(3, 2)]["hop"] == "P→M")
    check("3 raw edge + diffusion_events citation + localized_of dedup to one row with channels {citation, localized_of}",
          (3, 2) in by and by[(3, 2)]["channels"] == {"citation", "localized_of"})
    check("4 cross-province P→M edge dropped (suzhou→gd)", (5, 2) not in by)
    check("5 negative lag dropped", (7, 2) not in by)
    check("6 explainer parent dropped by the framework filter", (3, 6) not in by)
    check("7 M→D pair with a short source body is kept but unscored",
          (8, 3) in by and by[(8, 3)]["hop"] == "M→D" and by[(8, 3)]["scored"] is False)
    check("8 same-instrument (mirror) pair dropped", (10, 2) not in by)
    check("9 title_reissue only C→M pair, mid band (half the central text)",
          (4, 1) in by and by[(4, 1)]["channels"] == {"title_reissue"} and by[(4, 1)]["band"] == "mid"
          and by[(4, 1)]["hop"] == "C→M")
    check("10 localized_of only M→D pair, elab band, province inherited (gd)",
          (11, 3) in by and by[(11, 3)]["channels"] == {"localized_of"} and by[(11, 3)]["band"] == "elab"
          and by[(11, 3)]["source_province"] == "gd")
    check("11 转发 forwarding flag + lag_days + implementing", (9, 2) in by and by[(9, 2)]["forwarding"]
          and by[(9, 2)]["lag_days"] == 39 and by[(9, 2)]["source_implementing"] == 1)
    check("12 Suzhou date repaired from the URL (stamped 2023-02-09 → 2022-06-15, now before the anchor → dropped)",
          (12, 1) not in by)
    check("13 topic_genre off by default", not any("topic_genre" in r["channels"] for r in rows))
    check("14 topic_genre on request", any("topic_genre" in r["channels"] for r in
          build_pairs(conn, hops=ALL_HOPS, sources=ALL_SOURCES, score=False)))
    sub = build_pairs(conn, hops=("P→M",), score=False)
    check("15 hops filter keeps only P→M", sub and all(r["hop"] == "P→M" for r in sub))
    check("16 localized_of-only P→M pair from doc 4 (4→2), mid band", (4, 2) in by
          and by[(4, 2)]["channels"] == {"localized_of"} and by[(4, 2)]["band"] == "mid")
    check("17 row count", len(rows) == 7)

    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {n}")
    if bad:
        for r in rows:
            print("   ", r["source_id"], r["parent_id"], r["hop"], sorted(r["channels"]), r["band"])
    print(f"pairs self-test: {len(checks) - len(bad)}/{len(checks)} passed")
    return not bad


# --- CLI ------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--report", action="store_true", help="build + print the Venn / floor report")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--csv", help="write the pair table to this CSV")
    ap.add_argument("--hops", default=",".join(DEFAULT_HOPS))
    ap.add_argument("--sources", default=",".join(DEFAULT_SOURCES))
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--no-score", action="store_true")
    ap.add_argument("--no-framework", action="store_true", help="keep non-framework parents")
    args = ap.parse_args(argv)
    if args.self_test:
        return 0 if self_test() else 1
    if not (args.report or args.csv):
        ap.print_help()
        return 0
    t0 = time.time()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    hops = tuple(h.strip() for h in args.hops.split(",") if h.strip())
    sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())
    rows = build_pairs(conn, hops=hops, sources=sources, require_framework=not args.no_framework,
                       score=not args.no_score, workers=args.workers, verbose=True)
    if args.report:
        report(rows, hops=hops)
    if args.csv:
        write_csv(rows, args.csv)
        print(f"  wrote {len(rows)} rows to {args.csv}")
    print(f"\n  total {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
