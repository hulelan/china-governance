"""Government structure service — loads org-chart YAML and joins live doc counts.

The chart's content lives in data/structure.yaml. This module reads that file
once (cached at module load) and exposes a `get_structure(db)` coroutine that
joins each node with a live document count via the documents table.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_YAML_PATH = Path(__file__).parent.parent.parent / "data" / "structure.yaml"

_CACHED: dict | None = None


def _load_yaml() -> dict:
    global _CACHED
    if _CACHED is None:
        with _YAML_PATH.open(encoding="utf-8") as f:
            _CACHED = yaml.safe_load(f)
    return _CACHED


async def get_structure(db) -> dict:
    """Return the org chart organized by tier, with live doc counts attached.

    Shape:
        {
          "tiers": [
            {"id", "label", "intro", "nodes": [
                {"id", "name_en", "name_cn", "desc", "parent", "mirrors",
                 "rank", "note", "site_key", "doc_count", "children": [...]}
            ]},
            ...
          ],
          "node_by_id": {...},  # flat index for cross-references
          "totals": {"crawled": N, "total": M, "crawled_docs": N},
        }
    """
    data = _load_yaml()
    tiers = data["tiers"]
    nodes = data["nodes"]

    # 1) Build flat index
    by_id: dict[str, dict] = {}
    for n in nodes:
        n = dict(n)              # copy so we don't mutate the cached YAML
        n["children"] = []
        n["doc_count"] = 0
        by_id[n["id"]] = n

    # 2) Wire up parent → children for in-tier tree rendering
    for n in by_id.values():
        parent_id = n.get("parent")
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(n["id"])

    # 3) Live join with documents table
    site_keys = [n["site_key"] for n in by_id.values() if n.get("site_key")]
    if site_keys:
        placeholders = ",".join(f"${i+1}" for i in range(len(site_keys)))
        rows = await db.fetch(
            f"SELECT site_key, COUNT(*) FROM documents "
            f"WHERE site_key IN ({placeholders}) GROUP BY site_key",
            *site_keys,
        )
        counts = {r[0]: r[1] for r in rows}
        for n in by_id.values():
            sk = n.get("site_key")
            if sk:
                n["doc_count"] = counts.get(sk, 0)

    # 4) Group by tier (preserving tier order from YAML, node order within tier)
    nodes_by_tier: dict[str, list[dict]] = {t["id"]: [] for t in tiers}
    for n in nodes:                          # iterate original list for stable order
        if n["tier"] in nodes_by_tier:
            nodes_by_tier[n["tier"]].append(by_id[n["id"]])

    tier_views = []
    for t in tiers:
        tier_views.append({
            "id": t["id"],
            "label": t["label"],
            "intro": t.get("intro", "").strip(),
            "nodes": nodes_by_tier[t["id"]],
        })

    # 5) Headline totals
    crawled = [n for n in by_id.values() if n.get("site_key")]
    totals = {
        "total": len(by_id),
        "crawled": len(crawled),
        "crawled_docs": sum(n["doc_count"] for n in crawled),
    }

    return {"tiers": tier_views, "node_by_id": by_id, "totals": totals}
