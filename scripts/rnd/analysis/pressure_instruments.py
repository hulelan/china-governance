"""The Chinese documentary record of geoeconomic pressure, in BOTH directions.

NBER w34020 "Geoeconomic Pressure" (Clayton, Coppola, Maggiori & Schreger, Jul 2025)
classifies pressure episodes — sender government, target, instrument, named firms — by
LLM over large textual corpora, and then has to measure its own classification
uncertainty across models and prompt variants. We hold the issuing state's PRIMARY
instruments: dated, numbered (文号), naming the firms, with the official justification
text attached. That removes their particular measurement uncertainty and adds a
different limitation — an instrument is not an economic effect, and we have no
firm-level outcomes. Complement, not replication.

THE DESIGN POINT, found 2026-10-09 by nearly getting it wrong: this corpus records
pressure in BOTH directions. Of 161 candidate documents, a naive `N家X实体` extractor
reports 278 US entities AND 196 Chinese + 220 Japanese entities — because Chinese
documents also RECORD foreign measures ("美国在出口管制'实体清单'中增列40个实体",
"2021年7月美商务部'实体清单'新增34个实体 其中23个为中国实体"), and some are plain
explainers of the US system. Summing them blends two opposite quantities. So the SENDER
is classified first, and every count is reported per direction.

  python3 scripts/rnd/analysis/pressure_instruments.py            # the series
  python3 scripts/rnd/analysis/pressure_instruments.py --pairs    # instrument -> justification
  python3 scripts/rnd/analysis/pressure_instruments.py --unclassified
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

_here = Path(__file__).resolve()
# parents[3] is the repo root for scripts/rnd/<theme>/x.py; fall back to the CWD so a
# copy of this file can still be run from elsewhere with an explicit --db.
ROOT = _here.parents[3] if len(_here.parents) > 3 else Path.cwd()
DB = ROOT / "documents.db"

# --- what kind of instrument -------------------------------------------------
KIND = [
    ("unreliable_entity", re.compile(r"不可靠?实体清单")),
    ("control_list", re.compile(r"出口管制管控名单|管控名单")),
    ("concern_list", re.compile(r"关注名单")),
    ("countermeasure", re.compile(r"反制清单|反外国制裁")),
    ("entity_list_foreign", re.compile(r"实体清单")),   # last: the generic US term
]

# --- who is applying the pressure -------------------------------------------
# A FOREIGN sender is named as the actor, or the title is about a foreign regime.
FOREIGN_ACTOR = re.compile(
    r"(?:美国|美方|美商务部|美国商务部|日本|荷兰|欧盟|欧方|英国|英方|加拿大|澳大利亚)"
    r"[^，。]{0,14}?(?:列入|增列|新增|修改|实施|采取|发布|宣布|出台|制裁|管制)"
    # Bare 美 as the actor: "就美将多家中国实体列入…", "就美以涉俄为由将…". The full
    # 美国 form misses these, and they are 10+ documents of INBOUND pressure.
    r"|美(?:以[^，。]{0,10}为由)?将[^，。]{0,12}?(?:列入|纳入)"
)
# A spokesperson justification that names a CHINESE instrument and no foreign actor is
# China explaining its OWN measure ("就不可靠实体清单有关措施答记者问"). Without this the
# classifier left 10+ outbound justifications unplaced.
CN_SPOKESPERSON = re.compile(
    r"商务部(?:新闻发言人|安全与管制局负责人)[^，。]{0,20}"
    r"(?:不可靠?实体清单|管控名单|关注名单)")
FOREIGN_REGIME = re.compile(r"(?:美国|日本|欧盟|英国)[^，。]{0,10}(?:出口管制|实体清单|制度)")
# A CHINESE instrument: issued by the mechanism itself, or a 商务部 公告/令.
CN_INSTRUMENT = re.compile(
    r"^(?:不可靠?实体清单工作机制|商务部(?:\s*海关总署)?(?:公告|令)|国务院|中华人民共和国)")
CN_ACTOR = re.compile(r"(?:中方|我国|我部|中国政府)[^，。]{0,12}(?:列入|采取|决定|实施)")
# Not an episode at all.
EXPLAINER = re.compile(r"制度介绍|常见问答|有关问题答记者问|规定$|政策解读|^关注")
JUSTIFICATION = re.compile(r"答记者问|应询")

# Keywords that mean something else entirely in another domain. Found 2026-10-09 by
# reading the classifier's own "none" bucket instead of its counts: 反制 is also
# counter-DRONE equipment (民用无人驾驶航空器探测反制设备 standards), 关注名单 is also a
# Shenzhen water-bureau soil-conservation watch list, and guancha runs op-eds whose
# titles carry 反制 ("兔主席：中方严厉反制…"). Same shape as the ORG_TAIL false
# positives in the resolver work: a term borrowed by an unrelated field.
NOT_PRESSURE = re.compile(
    r"反制设备|探测反制|无线电反制"                 # counter-drone hardware standards
    r"|水土保持|重点关注名单的通告"                  # a local enforcement watch list
    r"|强制性国家标准|征求.{0,8}意见"                # standards drafting
)
# An op-ed: a commentator's name, then a colon. Keeps real instruments, which never
# carry a personal byline.
OPED = re.compile(r"^[一-鿿]{2,4}[&＆][一-鿿]{2,4}|^[一-鿿]{2,5}：")

# --- target + how many ------------------------------------------------------
COUNT_TARGET = re.compile(r"(\d+)\s*家([一-鿿]{2,8}?)(?:实体|企业|公司|机构)")
# The instrument's own 文号, read from the TITLE. Needed because doc_identity does NOT
# pool these: measured 2026-10-09, five held copies of 商务部公告2026年第11号/第12号 each
# carry a DISTINCT instrument_id (12701728, 12701729, 12704542, 12704543, 12724102), so
# instrument_role is 'unique' for every copy. That is the length-floor-on-a-folded-string
# family in CLAUDE.md: once the normalizer strips the 文号 and the date tail the core falls
# under _best_core's KEY_MIN and no instrument_key is assigned. Logged as its own defect;
# this script must not depend on that pooling being fixed.
TITLE_DOCNUM = re.compile(
    r"((?:商务部|海关总署|国务院)?(?:\s*海关总署)?(?:公告|令)\s*\d{4}\s*年第\s*\d+\s*号"
    r"|不可靠?实体清单工作机制(?:公告)?\s*[〔\[]\d{4}[〕\]]\s*\d+\s*号)")
NAMED_FIRM = re.compile(r"将([一-鿿·]{2,24}?)(?:公司|集团)")


def classify(title: str) -> tuple:
    """(kind, direction, role) — direction in {outbound, inbound, none}."""
    kind = next((k for k, p in KIND if p.search(title)), None)

    if JUSTIFICATION.search(title):
        role = "justification"
    elif EXPLAINER.search(title):
        role = "explainer"
    else:
        role = "instrument"

    # Order matters: a Chinese instrument's own masthead wins over a foreign
    # country merely appearing in the target phrase ("将16家美国实体列入").
    # ORDER IS LOAD-BEARING, and getting it wrong cost a run. The masthead test must
    # come FIRST because it is unambiguous — only China issues a 不可靠实体清单工作机制
    # 公告 or a 商务部公告 — whereas FOREIGN_ACTOR fires on a foreign country merely
    # appearing in the TARGET phrase of a Chinese instrument
    # ("…关于将斯凯迪奥公司等11家美国企业列入…" contains "美国企业列入"). Hoisting the
    # foreign test above the masthead reclassified 37 Chinese instruments as inbound and
    # collapsed the outbound count from 52 to 15.
    if CN_INSTRUMENT.match(title) or CN_ACTOR.search(title):
        direction = "outbound"
    elif FOREIGN_ACTOR.search(title):
        # Only now: a named foreign actor with no Chinese masthead is China RECORDING
        # someone else's measure ("就美将多家中国实体列入…事答记者问").
        direction = "inbound"
    elif CN_SPOKESPERSON.search(title):
        # A spokesperson naming a Chinese instrument, with no foreign actor above.
        direction = "outbound"
    elif FOREIGN_REGIME.search(title):
        direction = "inbound"
    else:
        direction = "none"
    return kind, direction, role


def load(conn):
    # instrument_id pools mirror copies of one text (doc_identity); without it an
    # entity count is summed once per COPY. Measured 2026-10-09: 日本 read 200 entities
    # where the truth is two announcements of 20, because two 公告 were each held twice
    # plus a news restatement. Same error shape as the tracker's text_median (one
    # document counted 62 times) and doc_inbound (weight split across copies).
    rows = conn.execute("""
        SELECT d.id, d.title, d.date_written, d.site_key,
               COALESCE(i.instrument_id, 0), COALESCE(d.document_number, '')
        FROM documents d LEFT JOIN doc_identity i ON i.doc_id = d.id
        WHERE d.date_written > 0 AND (
          d.title LIKE '%实体清单%' OR d.title LIKE '%管控名单%'
          OR d.title LIKE '%关注名单%' OR d.title LIKE '%反制%' OR d.title LIKE '%不可靠%')
        ORDER BY d.date_written""").fetchall()
    out, dropped = [], []
    for did, t, dw, sk, iid, docnum in rows:
        if NOT_PRESSURE.search(t) or OPED.search(t):
            dropped.append((did, t))
            continue
        kind, direction, role = classify(t)
        m = COUNT_TARGET.search(t)
        # The dedup key, best available: the pooled instrument, else the 文号, else the
        # action+target+day (a news restatement of a 公告 shares neither id nor 文号).
        # Prefer a 文号 read from the TITLE: it is the instrument's own identifier and it
        # survives the pooling failure noted above. Then the stored document_number, then
        # the instrument pool, then action+target+day for a news restatement with no number.
        tn = TITLE_DOCNUM.search(t)
        if tn:
            key = ("tnum", re.sub(r"\s+", "", tn.group(1)))
        elif docnum:
            key = ("num", re.sub(r"\s+", "", docnum))
        elif iid:
            key = ("iid", iid)
        else:
            key = ("act", m.group(0) if m else t[:18], date.fromtimestamp(dw))
        out.append({
            "id": did, "title": t, "day": date.fromtimestamp(dw), "site": sk,
            "key": key,
            "kind": kind, "direction": direction, "role": role,
            "n_entities": int(m.group(1)) if m else None,
            "target": m.group(2) if m else None,
            "firm": (NAMED_FIRM.search(t).group(1) if NAMED_FIRM.search(t) else None),
        })
    return out, dropped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--pairs", action="store_true", help="instrument -> justification lag")
    ap.add_argument("--unclassified", action="store_true", help="print direction='none'")
    ap.add_argument("--dropped", action="store_true", help="print off-domain drops")
    ap.add_argument("--target", help="print outbound instruments naming this target")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows, dropped = load(conn)
    print("pressure-related documents: %d  (%s to %s)   [%d dropped as off-domain]"
          % (len(rows), rows[0]["day"], rows[-1]["day"], len(dropped)))
    if args.dropped:
        for did, t in dropped:
            print("  DROP %-10s %s" % (did, t[:66]))

    print("\n=== direction x role ===")
    grid = Counter((r["direction"], r["role"]) for r in rows)
    print("  %-10s %-14s %s" % ("direction", "role", "n"))
    for (d, ro), n in sorted(grid.items(), key=lambda kv: (-kv[1])):
        print("  %-10s %-14s %d" % (d, ro, n))

    print("\n=== entity counts, PER DIRECTION (never summed across) ===")
    for d in ("outbound", "inbound"):
        per, seen, raw = defaultdict(int), set(), 0
        for r in rows:
            if r["direction"] == d and r["n_entities"] and r["role"] == "instrument":
                raw += r["n_entities"]
                if r["key"] in seen:
                    continue
                seen.add(r["key"])
                per[r["target"]] += r["n_entities"]
        tot = sum(per.values())
        print("  %-9s %d entities across %d targets, from %d distinct instruments "
              "(%d before dedup)" % (d, tot, len(per), len(seen), raw))
        for k, v in sorted(per.items(), key=lambda kv: -kv[1])[:6]:
            print("      %-12s %d" % (k, v))

    if args.target:
        print("\n=== outbound instruments naming %s ===" % args.target)
        for r in rows:
            if (r["direction"] == "outbound" and r["role"] == "instrument"
                    and r["target"] == args.target):
                print("  %s  n=%-5s key=%-34s %s"
                      % (r["day"], r["n_entities"], str(r["key"])[:34], r["title"][:46]))

    print("\n=== outbound instruments by year ===")
    seen_y = set()
    yr = Counter()
    for r in rows:
        if r["direction"] == "outbound" and r["role"] == "instrument" \
                and r["key"] not in seen_y:
            seen_y.add(r["key"])
            yr[r["day"].year] += 1
    for y in sorted(yr):
        print("  %s  %s" % (y, "#" * yr[y] + " %d" % yr[y]))

    if args.unclassified:
        print("\n=== direction='none' (what the classifier declines to place) ===")
        for r in rows:
            if r["direction"] == "none":
                print("  %-10s %-12s %s" % (r["id"], r["role"], r["title"][:58]))

    if args.pairs:
        print("\n=== outbound instrument -> nearest later justification (<=21d) ===")
        just = [r for r in rows if r["role"] == "justification"]
        lags = []
        for r in rows:
            if r["direction"] != "outbound" or r["role"] != "instrument":
                continue
            cand = [((j["day"] - r["day"]).days, j) for j in just
                    if 0 <= (j["day"] - r["day"]).days <= 21]
            if cand:
                lag, _ = min(cand, key=lambda x: x[0])
                lags.append(lag)
                print("  %s  lag=%-3d %s" % (r["day"], lag, r["title"][:52]))
            else:
                print("  %s  lag=--  %s" % (r["day"], r["title"][:52]))
        if lags:
            lags.sort()
            print("\n  paired %d, median lag %d d, <=1d %d (%.0f%%)"
                  % (len(lags), lags[len(lags) // 2],
                     sum(1 for x in lags if x <= 1),
                     100 * sum(1 for x in lags if x <= 1) / len(lags)))


if __name__ == "__main__":
    sys.exit(main())
