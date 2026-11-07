# -*- coding: utf-8 -*-
"""Merge Chinese text + authored English + measured corpus facts -> data.js.

The merge is keyed on the ARTICLE NUMBER, never on a list index, so adding an
English article later cannot shift the alignment of the ones already done. A
block with no English renders Chinese-only and counts against the coverage
badge, which is why partial translation is safe to ship.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
cn = json.load(open(os.path.join(HERE, "dossier_cn.json")))
facts = json.load(open(os.path.join(HERE, "dossier_facts.json")))


def load_en(key):
    p = os.path.join(HERE, "en", key + ".json")
    return json.load(open(p)) if os.path.exists(p) else {}


# Order is the notice's OWN citation order, not alphabetical and not by size.
AUTH_ORDER = ["cybersec", "dsl", "pipl", "antifraud", "telecom", "rwjg"]

META = {
  "notice": {
    "label_en": "Notice on Strengthening Network-Access Administration of Agent Terminal Equipment",
    "docnum": "工信厅信管〔2026〕42号",
    "issuer_cn": "工业和信息化部办公厅",
    "issuer_en": "General Office, Ministry of Industry and Information Technology",
    "signed": "2026-10-24", "published": "2026-11-06",
  },
  "npcdecision": {
    "label_en": "Decision of the NPC Standing Committee on Strengthening the Protection of Online Information",
    "kind_cn": "\u5168\u56fd\u4eba\u5927\u5e38\u59d4\u4f1a\u51b3\u5b9a",
    "kind_en": "NPC Standing Committee decision",
  },
  "twin2013": {
    "label_en": "Notice on Strengthening Network-Access Administration of Mobile Smart Terminals",
    "docnum": "工信部电管〔2013〕120号",
    "issuer_cn": "工业和信息化部",
    "issuer_en": "Ministry of Industry and Information Technology",
    "signed": "2013-04-11", "published": "2013-04-11",
  },
  "cybersec": {"label_en": "Cybersecurity Law of the People’s Republic of China",
               "kind_cn": "法律", "kind_en": "Statute (NPC Standing Committee)"},
  "dsl":      {"label_en": "Data Security Law of the People’s Republic of China",
               "kind_cn": "法律", "kind_en": "Statute (NPC Standing Committee)"},
  "pipl":     {"label_en": "Personal Information Protection Law of the People’s Republic of China",
               "kind_cn": "法律", "kind_en": "Statute (NPC Standing Committee)"},
  "antifraud":{"label_en": "Anti‑Telecom and Online Fraud Law of the People’s Republic of China",
               "kind_cn": "法律", "kind_en": "Statute (NPC Standing Committee)"},
  "telecom":  {"label_en": "Telecommunications Regulations of the People’s Republic of China",
               "kind_cn": "行政法规", "kind_en": "Administrative regulation (State Council)"},
  "rwjg":     {"label_en": "Measures for the Administration of Network Access of Telecommunications Equipment",
               "kind_cn": "部门规章", "kind_en": "Ministerial rule (MIIT / former MII)"},
}

ANNOT = json.load(open(os.path.join(HERE, "annotations.json")))


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
            # Documents with no 第N条 structure (both notices) key English by index.
            idx = len([x for x in blocks if x["t"] in ("para", "head")])
            seq = en.get("blocks", [])
            blocks.append({"t": "para", "cn": b["cn"],
                           "en": seq[idx] if idx < len(seq) else en.get("_head", "")})
    # For the notices, English is keyed by block index over ALL blocks.
    if "blocks" in en:
        seq = en["blocks"]
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
    doc.update(META.get(key, {}))
    if key in facts:
        doc["facts"] = facts[key]
    if key in ANNOT:
        doc["annot"] = ANNOT[key]
    return doc


ALL = ["notice", "twin2013", "npcdecision"] + AUTH_ORDER
data = {
    "docs": {k: build_doc(k) for k in ALL},
    "main": "notice",
    "authOrder": AUTH_ORDER,             # the notice's own citation order
    "twinRefs": ["npcdecision", "telecom", "rwjg"],   # what the 2013 twin cites
    "built": "2026-11-06",
}

# Coverage, printed so a partial pass is never reported as complete.
print("%-12s %-44s %7s %6s %6s %5s" % ("key", "title", "chars", "blocks", "en", "pct"))
rows = [data["docs"][k] for k in ALL]
for d in rows:
    n = d["n_art"] or len([b for b in d["blocks"] if b["t"] == "para"])
    ne = d["n_art_en"] or len([b for b in d["blocks"] if b["t"] == "para" and b["en"]])
    d["cov"] = [ne, n]
    print("%-12s %-44s %7d %6d %6d %4d%%"
          % (d["key"], d["title_cn"][:42], d["chars"], n, ne,
             round(100 * ne / n) if n else 0))

out = os.path.join(HERE, "artifact", "data.js")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f:
    f.write("window.DOSSIER = ")
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
print("\nWROTE %s (%d bytes)" % (out, os.path.getsize(out)))
