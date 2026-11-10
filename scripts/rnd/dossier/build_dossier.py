# -*- coding: utf-8 -*-
"""Merge Chinese text + authored English + measured corpus facts -> one reader.

    python3 scripts/rnd/dossier/build_dossier.py --set agent-terminals \
        --cn dossier_cn.json --facts dossier_facts.json --out-dir <dir>

Everything specific to one dossier (ids, labels, drawer copy, English, notes)
lives in data/dossier/<set>/; this file and parallel-reader.html are shared.
The merge is keyed on the ARTICLE NUMBER, never on a list index, so adding an
English article later cannot shift the alignment of the ones already done. A
block with no English renders Chinese-only and counts against the coverage
badge, which is why partial translation is safe to ship.
"""
import argparse, html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

ap = argparse.ArgumentParser()
ap.add_argument("--set", required=True)
ap.add_argument("--cn", required=True, help="output of dump_texts.py")
ap.add_argument("--facts", default=None, help="output of measure_auth.py (optional)")
ap.add_argument("--out-dir", required=True)
args = ap.parse_args()

SET = os.path.join(REPO, "data", "dossier", args.set)
M = json.load(open(os.path.join(SET, "meta.json")))
cn = json.load(open(args.cn))
facts = json.load(open(args.facts)) if args.facts else {}
_annot_p = os.path.join(SET, "annotations.json")
ANNOT = json.load(open(_annot_p)) if os.path.exists(_annot_p) else {}


def load_en(key):
    p = os.path.join(SET, "en", key + ".json")
    return json.load(open(p)) if os.path.exists(p) else {}


def chapter_en(key, zh):
    return load_en(key).get("_chapters", {}).get(zh, "")


def build_doc(key):
    src, en = cn[key], load_en(key)
    blocks, cur_chapter = [], None
    n_art = n_art_en = 0
    for b in src["articles"]:
        if b.get("chapter"):
            cur_chapter = b["chapter"]
            blocks.append({"t": "chapter", "cn": b["chapter"],
                           "en": chapter_en(key, b["chapter"])})
        elif b.get("section"):
            blocks.append({"t": "section", "cn": b["section"],
                           "en": chapter_en(key, b["section"])})
        elif b.get("toc"):
            blocks.append({"t": "toc", "cn": b["cn"], "en": ""})
        elif b.get("appendix"):
            blocks.append({"t": "appendix", "cn": b["cn"],
                           "en": en.get("_appendix", "")})
        elif b.get("no"):
            n_art += 1
            e = en.get(b["no"], "")
            if e:
                n_art_en += 1
            blocks.append({"t": "art", "no": b["no"], "n": b.get("n"),
                           "cn": b["cn"], "en": e, "ch": cur_chapter})
        else:
            blocks.append({"t": "para", "cn": b["cn"], "en": ""})
    # Paragraph documents (notices, a plan) carry no article numbers, so their
    # English is a list over ALL blocks. A length mismatch means the Chinese
    # split changed under a finished translation: refuse rather than misalign.
    if "blocks" in en:
        seq = en["blocks"]
        if len(seq) > len(blocks):
            raise SystemExit(f"{key}: {len(seq)} English blocks for {len(blocks)} Chinese")
        for i, blk in enumerate(blocks):
            blk["en"] = seq[i] if i < len(seq) else ""
    elif en.get("_head") and blocks and blocks[0]["t"] == "para":
        blocks[0]["en"] = en["_head"]

    doc = {
        "key": key, "id": src["id"], "site": src["site"],
        "title_cn": src["title"], "date": src["date"], "url": src["url"],
        "chars": src["chars"], "blocks": blocks,
        "n_art": n_art, "n_art_en": n_art_en,
    }
    doc.update(M.get("meta", {}).get(key, {}))
    if key in facts:
        doc["facts"] = facts[key]
    if key in ANNOT:
        doc["annot"] = ANNOT[key]
    if "cited_by" in src:
        doc["cited_by"] = src["cited_by"]
    return doc


ALL = M["order"]
data = {
    "docs": {k: build_doc(k) for k in ALL},
    "main": M["main"],
    "chain": M.get("chain", []),
    "chainTitle": M.get("chainTitle", "Cited authorities"),
    "chainIntro": M.get("chainIntro", []),
    "drawerLabel": M.get("drawerLabel", "references"),
    "extraRefs": M.get("extraRefs", []),
    "citedByIntro": M.get("citedByIntro", []),
    "footNote": M.get("footNote", ""),
    "built": M.get("built", ""),
}

# Coverage, printed so a partial pass is never reported as complete.
print("%-12s %-44s %7s %6s %6s %5s" % ("key", "title", "chars", "blocks", "en", "pct"))
for k in ALL:
    d = data["docs"][k]
    n = d["n_art"] or len([b for b in d["blocks"] if b["t"] == "para"])
    ne = d["n_art_en"] or len([b for b in d["blocks"] if b["t"] == "para" and b["en"]])
    d["cov"] = [ne, n]
    print("%-12s %-44s %7d %6d %6d %4d%%"
          % (k, d["title_cn"][:42], d["chars"], n, ne, round(100 * ne / n) if n else 0))

os.makedirs(args.out_dir, exist_ok=True)
js = os.path.join(args.out_dir, "data.js")
with open(js, "w") as f:
    f.write("window.DOSSIER = ")
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
page = open(os.path.join(HERE, "parallel-reader.html")).read()
assert page.count("__PAGE_TITLE__") == 1
page = page.replace("__PAGE_TITLE__", html.escape(M.get("page_title", "Parallel Reader")))
open(os.path.join(args.out_dir, "parallel-reader.html"), "w").write(page)
print("\nWROTE %s (%d bytes) + parallel-reader.html" % (js, os.path.getsize(js)))
