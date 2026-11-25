#!/usr/bin/env python3
"""Upgrade `web, not in corpus` evidence in data/purges/officials.json to `corpus`
once its URL has been ingested — by an EXPLICIT, hand-chosen quote per item.

Why explicit. An evidence item supports one fact (a person's event, a rank, a
plenum list). The quote that verifies it has to say THAT fact, and choosing it
is a reading job: an automatic "first sentence containing the name" would verify
an expulsion with a sentence about a promotion. So this script never picks a
quote. It has two modes:

  --list     for every `web, not in corpus` item whose url is now a stored
             document, print the item's location (a JSON path), the fact it
             supports, and the stored document's id / title / body, so a quote
             can be chosen by reading;
  --apply    read data/purges/web_upgrades.json, a list of
             {"path": [...], "url": ..., "doc_id": ..., "quote": ...},
             and for each: check the item at `path` is still `web, not in
             corpus` with that url, check the url resolves to that doc_id,
             check the quote is an EXACT substring of the doc's title or body,
             then relabel it `corpus` (doc_id, quote; the old url / fetched /
             note kept under `upgraded_from`). All-or-nothing: any failed check
             writes nothing.

Then run build_purges.py, whose verifier re-checks every corpus quote.

    python3 scripts/rnd/purges/upgrade_web_evidence.py --ssh root@104.236.88.45 --list
    python3 scripts/rnd/purges/upgrade_web_evidence.py --ssh root@104.236.88.45 --apply
    python3 scripts/rnd/purges/build_purges.py --ssh root@104.236.88.45
"""
import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "purges" / "officials.json"
UPGRADES = ROOT / "data" / "purges" / "web_upgrades.json"
WEB = "web, not in corpus"
# Event actions that can establish a removal (the ones the hand-built file marks
# establishes_removal on when corpus-backed).
REMOVAL_ACTIONS = {"investigation_announced", "removed_from_post", "demoted", "expelled",
                   "expulsion_confirmed_by_plenum", "sentenced", "indicted"}

_FETCH = r'''
import json, sqlite3, sys
urls = %s
c = sqlite3.connect("file:documents.db?mode=ro", uri=True)
out = {}
for u in urls:
    r = c.execute("SELECT id, site_key, date_published, title, body_text_cn FROM documents "
                  "WHERE url=? AND url != '' ORDER BY id LIMIT 1", (u,)).fetchone()
    if r:
        out[u] = {"id": r[0], "site": r[1], "date": r[2], "title": r[3], "body": r[4] or ""}
sys.stdout.write(json.dumps(out, ensure_ascii=False))
'''


def walk_web(node, path=()):
    """Yield (path, item) for every `web, not in corpus` item that carries a url."""
    if isinstance(node, dict):
        if node.get("label") == WEB and node.get("url"):
            yield path, node
        for k, v in node.items():
            if k != "upgraded_from":          # provenance of an upgraded item, not a live one
                yield from walk_web(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_web(v, path + (i,))


def at(data, path):
    node = data
    for k in path:
        node = node[k]
    return node


def context(data, path):
    """A one-line description of the fact the evidence at `path` supports."""
    bits = []
    node = data
    for k in path:
        node = node[k]
        if isinstance(node, dict):
            if "name_cn" in node:
                bits.append(node["name_cn"])
            elif "action" in node:
                bits.append("%s %s: %s" % (node.get("date", ""), node["action"], node.get("detail_en", "")))
            elif "plenum" in node:
                bits.append("plenum %s %s expelled=%s" % (node["plenum"], node.get("date", ""),
                                                         node.get("expelled")))
            elif "post" in node and "successor" in node:
                bits.append("succession %s -> %s" % (node["post"], node["successor"]))
            elif "measure" in node:
                bits.append("ladder %s" % node["measure"])
        elif isinstance(k, str) and k in ("rank_evidence", "stated_grounds"):
            bits.append(k)
    return " | ".join(bits)


def fetch(urls, db=None, ssh=None, remote_dir="/root/china-governance"):
    if db:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        out = {}
        for u in urls:
            r = c.execute("SELECT id, site_key, date_published, title, body_text_cn FROM documents "
                          "WHERE url=? AND url != '' ORDER BY id LIMIT 1", (u,)).fetchone()
            if r:
                out[u] = {"id": r[0], "site": r[1], "date": r[2], "title": r[3], "body": r[4] or ""}
        return out
    p = subprocess.run(["ssh", ssh, f"cd {remote_dir} && .venv/bin/python3 -"],
                       input=(_FETCH % json.dumps(sorted(urls), ensure_ascii=False)).encode(),
                       capture_output=True)
    if p.returncode != 0:
        sys.exit("remote fetch failed:\n" + p.stderr.decode()[-2000:])
    return json.loads(p.stdout.decode())


def apply(data, upgrades, docs):
    """Relabel each upgrade in `data`. Returns a list of failures; on any failure
    `data` must not be written (the caller checks)."""
    fails = []
    for u in upgrades:
        path = tuple(u["path"])
        try:
            ev = at(data, path)
        except (KeyError, IndexError, TypeError):
            fails.append((path, "path not found"))
            continue
        if ev.get("label") != WEB or ev.get("url") != u["url"]:
            fails.append((path, "item is no longer `%s` with url %s" % (WEB, u["url"])))
            continue
        doc = docs.get(u["url"])
        if not doc or doc["id"] != u["doc_id"]:
            fails.append((path, "url does not resolve to doc %s (got %s)" % (u["doc_id"], doc and doc["id"])))
            continue
        if u["quote"] not in doc["body"] and u["quote"] not in (doc["title"] or ""):
            fails.append((path, "quote is not an exact substring of doc %s" % u["doc_id"]))
            continue
        event = None
        if u.get("establishes_removal"):
            # The dataset's convention: an event's establishes_removal is set when it
            # carries corpus evidence that the event removed the person (every such
            # event in the hand-built file is a corpus one). Setting it is a per-item
            # hand decision, so it is only ever done when the upgrade entry asks.
            event = at(data, path[:-2]) if len(path) >= 2 and path[-2] == "evidence" else None
            if not isinstance(event, dict) or event.get("action") not in REMOVAL_ACTIONS:
                fails.append((path, "establishes_removal asked for a non-removal event"))
                continue
        old = {k: ev.pop(k) for k in list(ev) if k != "label"}
        if event is not None:
            event["establishes_removal"] = True
        ev.update(label="corpus", doc_id=u["doc_id"], quote=u["quote"],
                  upgraded_from={"label": WEB, **old})
        if u.get("note"):
            ev["note"] = u["note"]
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--upgrades", default=str(UPGRADES))
    ap.add_argument("--db")
    ap.add_argument("--ssh")
    ap.add_argument("--remote-dir", default="/root/china-governance")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--body-chars", type=int, default=1200, help="--list: body characters to print")
    a = ap.parse_args()
    if bool(a.db) == bool(a.ssh):
        ap.error("give exactly one of --db or --ssh")
    data = json.load(open(a.data, encoding="utf-8"))
    items = list(walk_web(data))
    docs = fetch({ev["url"] for _, ev in items}, a.db, a.ssh, a.remote_dir)

    if a.list:
        held = [(p, ev) for p, ev in items if ev["url"] in docs]
        print("%d `%s` items with a url; %d now resolve to a stored document" % (len(items), WEB, len(held)))
        for p, ev in held:
            d = docs[ev["url"]]
            print("\n=== path=%s" % json.dumps(list(p), ensure_ascii=False))
            print("fact: %s" % context(data, p))
            print("note: %s" % ev.get("note", ""))
            print("doc %s [%s] %s %s" % (d["id"], d["site"], d["date"], d["title"]))
            print(d["body"][:a.body_chars])
        return 0

    upgrades = json.load(open(a.upgrades, encoding="utf-8"))
    fails = apply(data, upgrades, docs)
    for path, why in fails:
        print("  FAIL %s: %s" % (list(path), why))
    if fails:
        print("NOT WRITTEN: %d of %d upgrades failed" % (len(fails), len(upgrades)))
        return 1
    json.dump(data, open(a.data, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("upgraded %d items; now run build_purges.py to verify and re-summarise" % len(upgrades))
    return 0


if __name__ == "__main__":
    sys.exit(main())
