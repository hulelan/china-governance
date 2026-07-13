"""Citation-frontier ranker — "what should we crawl next?"

The corpus grows by following its own citation graph: crawl the densest cluster
of *missing* cited documents, its bodies reveal new citations, which surface the
next cluster (see docs/working/corpus-completeness.md §B). This script ranks the
frontier so each round targets the highest recoverable payoff.

It reads the `citations` table (dangling = target_id IS NULL), buckets the
missing refs by ISSUER (formal 文号) and by inferred SOURCE (named 《》 titles),
and joins each bucket to a REACHABILITY map: do we already have a crawler that
can reach it (→ "extend"), or is it a new source (→ "build")? Output is a ranked
"crawl backlog" — most refs-recoverable first.

Usage:
    python3 scripts/rnd/citations/cluster_frontier.py            # ranked frontier
    python3 scripts/rnd/citations/cluster_frontier.py --top 40
    python3 scripts/rnd/citations/cluster_frontier.py --unreachable  # only "new source" clusters

Run it after each crawl round (and after extract_citations.py rebuilds the table)
to see the frontier move.
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
from analyze import split_formal_ref  # noqa: E402

DB_PATH = Path(__file__).parents[3] / "documents.db"

# ---------------------------------------------------------------------------
# Reachability map: issuer-prefix regex -> (label, how-to-crawl, deep_capable)
# Ordered; first match wins, so put more specific prefixes first. `cmd` is the
# concrete action to recover that cluster. `deep` = we have an archival/deep mode
# (not just a recent-window crawl), i.e. the cluster is fully recoverable today.
# ---------------------------------------------------------------------------
REACH = [
    (r"^(国发|国办|国函|国转|国科发|国资|国防)", "State Council 国务院",
     "python3 -m crawlers.gov --library --deep --categories gw", True),
    (r"^(中办|中发|中组|中宣)", "CPC Central Committee",
     "(no dedicated crawler — new source)", False),
    (r"^(财)", "Ministry of Finance / 财政",
     "python3 -m crawlers.gov --library --deep --categories bm  (or crawlers.mof)", True),
    (r"^(发改)", "NDRC 发改委",
     "python3 -m crawlers.gov --library --deep --categories bm  (or crawlers.ndrc)", True),
    (r"^(工信|工业和信息化)", "MIIT 工信部",
     "python3 -m crawlers.miit", False),
    (r"^(环发|环water|生态环境)", "MEE 生态环境部",
     "python3 -m crawlers.mee", False),
    (r"^(人社部|人社)", "MOHRSS 人社部",
     "python3 -m crawlers.gov --library --deep --categories bm", True),
    (r"^(国土资|自然资源|国土)", "MNR 自然资源部",
     "python3 -m crawlers.gov --library --deep --categories bm", True),
    (r"^(建|住建)", "MOHURD 住建部",
     "python3 -m crawlers.gov --library --deep --categories bm", True),
    (r"^(粤)", "Guangdong province 广东",
     "python3 -m crawlers.gkmlpt --site gd", False),
    (r"^(穗|广州)", "Guangzhou 广州",
     "(gkmlpt — verify Guangzhou site coverage)", False),
    (r"^(深|深圳)", "Shenzhen 深圳",
     "python3 -m crawlers.gkmlpt --site sz", False),
    (r"^(苏|苏州)", "Suzhou/Jiangsu 苏州",
     "python3 -m crawlers.suzhou / crawlers.jiangsu", False),
    (r"^(京)", "Beijing 北京",
     "python3 -m crawlers.beijing", False),
    (r"^(沪)", "Shanghai 上海",
     "python3 -m crawlers.shanghai", False),
    (r"^(渝)", "Chongqing 重庆",
     "python3 -m crawlers.chongqing", False),
    (r"^(浙)", "Zhejiang 浙江",
     "python3 -m crawlers.zhejiang", False),
    (r"^(鄂|武)", "Hubei/Wuhan 湖北",
     "python3 -m crawlers.wuhan", False),
    (r"^(珠|佛|莞|惠|中山|江门|肇|茂|湛|汕|潮|揭|云浮|阳|韶|梅|清远|河源)", "Other Guangdong cities",
     "python3 -m crawlers.gkmlpt --site <city>", False),
]


def classify_reach(issuer: str):
    """Return (label, cmd, deep) for an issuer prefix, or a 'new source' sentinel."""
    for pat, label, cmd, deep in REACH:
        if re.match(pat, issuer):
            return label, cmd, deep
    return None


def frontier(conn, top: int, unreachable_only: bool):
    rows = conn.execute(
        "SELECT target_ref FROM citations "
        "WHERE target_id IS NULL AND citation_type='formal'"
    ).fetchall()

    # bucket dangling formal refs by reachability cluster
    clusters = defaultdict(lambda: {"refs": 0, "docs": set(), "cmd": "", "deep": False,
                                    "reachable": False, "samples": []})
    unmapped = defaultdict(lambda: {"refs": 0, "docs": set()})

    for (ref,) in rows:
        parts = split_formal_ref(ref)
        issuer = parts[0] if parts else ref
        hit = classify_reach(issuer)
        if hit:
            label, cmd, deep = hit
            c = clusters[label]
            c["refs"] += 1
            c["docs"].add(ref)
            c["cmd"], c["deep"], c["reachable"] = cmd, deep, True
            if len(c["samples"]) < 3 and ref not in c["samples"]:
                c["samples"].append(ref)
        else:
            # group unmapped issuers by their first 2 chars (rough issuer family)
            key = issuer[:2] or "?"
            unmapped[key]["refs"] += 1
            unmapped[key]["docs"].add(ref)

    ranked = sorted(clusters.items(), key=lambda kv: -kv[1]["refs"])
    unmapped_ranked = sorted(unmapped.items(), key=lambda kv: -kv[1]["refs"])

    if unreachable_only:
        print("=== Unmapped issuer families (candidate NEW sources), by dangling refs ===\n")
        total = 0
        for key, d in unmapped_ranked[:top]:
            total += d["refs"]
            print(f"  {key:<8s} refs={d['refs']:>6d}  distinct_docs={len(d['docs']):>5d}")
        print(f"\n  (top {min(top,len(unmapped_ranked))} families = {total} refs; "
              f"{len(unmapped_ranked)} families total)")
        return

    print("=== CRAWL FRONTIER — reachable clusters, ranked by recoverable refs ===\n")
    print(f"  {'cluster':<28s}{'refs':>7s}{'docs':>7s}  {'deep?':<6s} action")
    print(f"  {'-'*28}{'-'*7}{'-'*7}  {'-'*6} {'-'*40}")
    for label, c in ranked[:top]:
        flag = "FULL" if c["deep"] else "recent"
        print(f"  {label:<28s}{c['refs']:>7d}{len(c['docs']):>7d}  {flag:<6s} {c['cmd']}")
        print(f"  {'':28s}{'':>7s}{'':>7s}  e.g. {', '.join(c['samples'])}")

    reach_refs = sum(c["refs"] for _, c in ranked)
    unmapped_refs = sum(d["refs"] for _, d in unmapped_ranked)
    print(f"\n  reachable (mapped) dangling refs: {reach_refs}")
    print(f"  unmapped dangling refs:           {unmapped_refs}  "
          f"(run --unreachable to see candidate new sources)")


def main():
    ap = argparse.ArgumentParser(description="Rank the citation crawl frontier")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--unreachable", action="store_true",
                    help="Show unmapped issuer families (candidate new sources)")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    frontier(conn, args.top, args.unreachable)
    conn.close()


if __name__ == "__main__":
    main()
