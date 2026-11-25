#!/usr/bin/env python3
"""Verify and summarise data/purges/officials.json.

Every evidence item labelled "corpus" carries a doc_id and a quote. This script
re-reads each document and requires the quote to be an EXACT substring of its
title or body_text_cn (no normalisation: a quote that needs whitespace folding
to match is a quote nobody can find by Ctrl-F). It then

  * stamps each corpus evidence item with site / url / doc_date / doc_title /
    where ("title" | "body") / verified,
  * resolves 20th Central Committee membership (full | alternate) for every
    name in a plenum expulsion list, from the two name-list documents,
  * derives per-person `corpus_verified` and the headline `summary`,
  * writes the file back (unless --check).

Exit status is 1 if ANY corpus quote fails, so a commit can be gated on it.

The corpus lives only on the droplet, so there are two ways to read it:

    python3 scripts/rnd/purges/build_purges.py --ssh root@104.236.88.45
    python3 scripts/rnd/purges/build_purges.py --db /path/to/documents.db

--ssh pipes a small read-only fetch script over ssh stdin and gets back the
needed rows as JSON; verification itself runs locally in both modes, through
the same verify() function the test exercises.
"""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "purges" / "officials.json"
CC20_FULL, CC20_ALT = 900207119, 900207120       # 二十届中央委员会委员 / 候补委员名单 (ce)
TIERS = ["正国级", "副国级", "CMC member"]
TYPES = ["a", "b", "c", "d"]

_FETCH = r'''
import json, sqlite3, sys
ids = %s
c = sqlite3.connect("file:documents.db?mode=ro", uri=True)
out = {}
for k in range(0, len(ids), 400):
    chunk = ids[k:k + 400]
    for r in c.execute("SELECT id, site_key, url, date_published, title, body_text_cn FROM documents "
                       "WHERE id IN (%%s)" %% ",".join("?" * len(chunk)), chunk):
        out[str(r[0])] = {"site": r[1], "url": r[2], "date": r[3], "title": r[4], "body": r[5]}
sys.stdout.write(json.dumps(out, ensure_ascii=False))
'''


def walk_corpus_evidence(node):
    """Yield every dict labelled 'corpus', anywhere in the structure."""
    if isinstance(node, dict):
        if node.get("label") == "corpus":
            yield node
        for v in node.values():
            yield from walk_corpus_evidence(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_corpus_evidence(v)


def fetch_local(db, ids):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out = {}
    for i in ids:
        r = c.execute("SELECT id, site_key, url, date_published, title, body_text_cn "
                      "FROM documents WHERE id=?", (i,)).fetchone()
        if r:
            out[str(r[0])] = {"site": r[1], "url": r[2], "date": r[3], "title": r[4], "body": r[5]}
    return out


def fetch_ssh(host, remote_dir, ids):
    script = _FETCH % json.dumps(sorted(ids))
    p = subprocess.run(["ssh", host, f"cd {remote_dir} && .venv/bin/python3 -"],
                       input=script.encode(), capture_output=True)
    if p.returncode != 0:
        sys.exit("remote fetch failed:\n" + p.stderr.decode()[-2000:])
    return json.loads(p.stdout.decode())


def verify(data, docs):
    """Check every corpus quote against `docs` ({str(id): row}); stamp results.

    Returns the list of failures, each (doc_id, quote, reason). Mutates `data`.
    """
    failures = []
    for ev in walk_corpus_evidence(data):
        did, quote = ev.get("doc_id"), ev.get("quote")
        ev["verified"] = False
        if not did or not quote:
            failures.append((did, quote, "corpus evidence needs doc_id and quote"))
            continue
        doc = docs.get(str(did))
        if doc is None:
            failures.append((did, quote, "document not found"))
            continue
        if quote in (doc.get("body") or ""):
            where = "body"
        elif quote in (doc.get("title") or ""):
            where = "title"
        else:
            failures.append((did, quote, "quote is not a substring of title or body_text_cn"))
            continue
        ev.update(verified=True, where=where, site=doc.get("site"), url=doc.get("url"),
                  doc_date=(doc.get("date") or "")[:10], doc_title=doc.get("title"))
    return failures


def name_set(body):
    return {re.sub(r"[（(].*?[）)]", "", tok) for tok in re.split(r"\s+", body or "") if tok}


def resolve_membership(data, docs):
    full, alt = docs.get(str(CC20_FULL)), docs.get(str(CC20_ALT))
    if not (full and alt):
        return ["20th CC name-list documents not found (%d, %d)" % (CC20_FULL, CC20_ALT)]
    fs, as_ = name_set(full["body"]), name_set(alt["body"])
    for row in data.get("cc_expulsions", []):
        if row.get("congress") != 20 or not row.get("expelled"):
            continue
        m = {n: "full" if n in fs else "alternate" if n in as_ else "not found" for n in row["expelled"]}
        for o in row.get("other", []):
            n = o["name"]
            o["membership"] = "full" if n in fs else "alternate" if n in as_ else "not found"
        row["membership"] = m
        row["membership_source"] = {"full_list_doc": CC20_FULL, "alternate_list_doc": CC20_ALT,
                                    "method": "exact name token in the list body, parenthetical notes stripped"}
    return []


def ev_ok(ev):
    return ev.get("label") == "corpus" and ev.get("verified")


def summarise(data):
    for p in data["persons"]:
        p["corpus_verified"] = any(e.get("establishes_removal") and any(ev_ok(v) for v in e["evidence"])
                                   for e in p["events"])
        n_c = sum(1 for e in p["events"] if any(ev_ok(v) for v in e["evidence"]))
        p["events_with_corpus_evidence"] = "%d of %d" % (n_c, len(p["events"]))
    cells = {}
    for t in TIERS:
        for ty in TYPES:
            ps = [p for p in data["persons"] if p["tier"] == t and p["removal_type"] == ty]
            pre = [p for p in ps if "removed_before_18th_congress" in p.get("flags", [])]
            post = [p for p in ps if p not in pre]
            cells["%s|%s" % (t, ty)] = {
                "since_18th_congress": [p["name_cn"] for p in post],
                "of_which_corpus_verified": [p["name_cn"] for p in post if p["corpus_verified"]],
                "of_which_not_corpus_verified": [p["name_cn"] for p in post if not p["corpus_verified"]],
                "flagged_before_18th_congress": [p["name_cn"] for p in pre],
                "investigation_only": [p["name_cn"] for p in post
                                       if "investigation_only_no_disposal_yet" in p.get("flags", [])],
            }
    dn = [p for p in data["persons"] if p["tier"] in ("正国级", "副国级")]
    post = [p for p in dn if "removed_before_18th_congress" not in p.get("flags", [])]
    head = {
        "definition": "副国级 or above (rank at removal or highest previously held), removed since the 18th Party "
                      "Congress (Nov 2012), all removal types; CMC members who were not vice-chairs are excluded "
                      "and shown in their own tier.",
        "total_all_types": len(post),
        "by_type": {ty: len([p for p in post if p["removal_type"] == ty]) for ty in TYPES},
        "corpus_verified_all_types": len([p for p in post if p["corpus_verified"]]),
        "of_which_正国级": len([p for p in post if p["tier"] == "正国级"]),
        "plus_flagged_before_congress": [p["name_cn"] for p in dn if p not in post],
        "cmc_member_tier": len([p for p in data["persons"] if p["tier"] == "CMC member"]),
        "cmc_member_tier_corpus_verified": len([p for p in data["persons"]
                                                if p["tier"] == "CMC member" and p["corpus_verified"]]),
    }
    cc = []
    for row in data.get("cc_expulsions", []):
        ok = any(ev_ok(v) for v in row["evidence"])
        m = row.get("membership") or {}
        cc.append({"plenum": row["plenum"], "date": row["date"],
                   "expelled": len(row["expelled"]) if row.get("expelled") else None,
                   "full_members": sum(1 for v in m.values() if v == "full") if m else None,
                   "alternate_members": sum(1 for v in m.values() if v == "alternate") if m else None,
                   "evidence": "corpus" if ok else row["evidence"][0]["label"]})
    c20 = [r for r in cc if r["plenum"].startswith("20-")]
    head_cc = {
        "20th_cc_full_members_expelled_corpus_verified": sum(r["full_members"] or 0 for r in c20 if r["evidence"] == "corpus"),
        "20th_cc_full_members_expelled_incl_web": sum(r["full_members"] or 0 for r in c20),
        "20th_cc_alternates_expelled_corpus_verified": sum(r["alternate_members"] or 0 for r in c20 if r["evidence"] == "corpus"),
        "20th_cc_alternates_expelled_incl_web": sum(r["alternate_members"] or 0 for r in c20),
        "note": "Central Committee full membership is a proxy for 正部级 and its military equivalents, not the rank itself. "
                "18th CC rows cannot be split into full and alternate members from the corpus (no 18th CC name list is held).",
    }
    data["summary"] = {"headline": head, "cells": cells, "cc_expulsions_by_plenum": cc, "cc_totals": head_cc,
                       "timing": timing(data)}
    return data["summary"]


FIRST_ACTIONS = {"investigation_announced", "removed_from_post", "expelled", "demoted", "suspended"}
WINDOW = 24                                    # months


def _m(s):
    """'YYYY-MM[-DD]' -> month index."""
    return int(s[:4]) * 12 + int(s[5:7]) - 1


def timing(data):
    """Timing only, no causal reading: does a listed institutional change fall in the
    24 months after a person's first official action, and how often does one fall in
    ANY 24-month window (the base rate)? The change list is our own selection, so
    both numbers describe that list."""
    changes = sorted(_m(c["date"]) for c in data.get("institutional_changes", []))
    if not changes:
        return None
    as_of = _m(data["meta"]["as_of"])
    start = _m("2012-11")
    hit = lambda t: [c for c in changes if t < c <= t + WINDOW]
    closed = range(start, as_of - WINDOW + 1)
    base = sum(1 for t in closed if hit(t))
    rows = []
    for p in data["persons"]:
        if p["tier"] == "CMC member":
            continue
        ds = [e["date"] for e in p["events"] if e["action"] in FIRST_ACTIONS and e.get("date")]
        if not ds:
            continue
        first = min(ds)
        t = _m(first)
        rows.append({"name_cn": p["name_cn"], "first_action": first,
                     "window_closed": t + WINDOW <= as_of,
                     "changes_in_window": [c["date"] + " " + c["system"] for c in data["institutional_changes"]
                                           if t < _m(c["date"]) <= t + WINDOW]})
    done = [r for r in rows if r["window_closed"]]
    return {"window_months": WINDOW, "n_changes_listed": len(changes),
            "base_rate": {"months_with_a_change_in_next_24": base, "months_observed": len(closed),
                          "share": round(base / len(closed), 3),
                          "span": "2012-11 to the last month whose 24-month window has closed"},
            "persons": rows,
            "persons_closed_window": len(done),
            "persons_closed_window_with_change": sum(1 for r in done if r["changes_in_window"]),
            "caveat": "The list of institutional changes is hand-selected (8 items) and the corpus dates several of "
                      "them only through retrospective documents. Timing only; no causal claim."}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--db", help="local documents.db (read-only)")
    ap.add_argument("--ssh", help="user@host holding documents.db")
    ap.add_argument("--remote-dir", default="/root/china-governance")
    ap.add_argument("--check", action="store_true", help="verify only; do not rewrite the data file")
    a = ap.parse_args()
    if bool(a.db) == bool(a.ssh):
        ap.error("give exactly one of --db or --ssh")
    data = json.load(open(a.data, encoding="utf-8"))
    ids = {ev["doc_id"] for ev in walk_corpus_evidence(data) if ev.get("doc_id")} | {CC20_FULL, CC20_ALT}
    docs = fetch_local(a.db, ids) if a.db else fetch_ssh(a.ssh, a.remote_dir, ids)
    failures = verify(data, docs)
    problems = resolve_membership(data, docs)
    s = summarise(data)
    n = sum(1 for _ in walk_corpus_evidence(data))
    print("corpus quotes: %d checked, %d failed, %d documents" % (n, len(failures), len(ids)))
    for did, quote, why in failures:
        print("  FAIL doc %s: %s\n       %r" % (did, why, quote))
    for p in problems:
        print("  PROBLEM", p)
    h = s["headline"]
    print("headline: %d at 副国级+ since the 18th Congress (a=%d b=%d c=%d d=%d), %d corpus-verified; "
          "flagged pre-congress: %s; CMC-member tier: %d (%d corpus-verified)" % (
              h["total_all_types"], h["by_type"]["a"], h["by_type"]["b"], h["by_type"]["c"], h["by_type"]["d"],
              h["corpus_verified_all_types"], "、".join(h["plus_flagged_before_congress"]) or "none",
              h["cmc_member_tier"], h["cmc_member_tier_corpus_verified"]))
    for k, v in s["cells"].items():
        if v["since_18th_congress"] or v["flagged_before_18th_congress"]:
            print("  %-14s %s | not corpus-verified: %s" % (k, "、".join(v["since_18th_congress"]),
                                                            "、".join(v["of_which_not_corpus_verified"]) or "none"))
    for r in s["cc_expulsions_by_plenum"]:
        print("  plenum %-22s expelled=%s full=%s alt=%s [%s]" % (r["plenum"], r["expelled"], r["full_members"],
                                                                 r["alternate_members"], r["evidence"]))
    if failures or problems:
        print("NOT WRITTEN: fix the failures above")
        return 1
    if not a.check:
        json.dump(data, open(a.data, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("wrote", a.data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
