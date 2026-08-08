"""Source-TYPE ontology service.

Loads data/source_ontology.yaml — a hierarchical tree of source *types* (what
KIND of body published a document: central ministry, provincial department,
district, news media, think-tank, ...) — and exposes helpers to map between
site_keys and type-nodes.

The tree is loaded and indexed once at import (cached at module level). The
YAML file is small and static, so this is cheap.

Key entry points
    site_to_type(site_key)   -> leaf node id (str), or 'other' if unmapped
    type_to_sites(node_id)   -> list[str] of every site_key under a node
                                (works for a leaf OR a whole branch)
    sites_excluding(node_id) -> list[str] of every KNOWN site_key NOT under node
                                (e.g. sites_excluding('media') = "everything but news")
    tree()                   -> the nested tree with .sites attached to each node
    node_ids()               -> set of all node ids
    leaves()                 -> list of leaf nodes (flat)

`type_to_sites`/`sites_excluding` return only site_keys the ontology explicitly
knows about (via exact key or a prefix seen in the loaded corpus). To resolve an
arbitrary site_key at query time (including brand-new crawlers), use
`site_to_type`, which also honors prefixes and falls back to 'other'.
"""
from __future__ import annotations

import copy
import threading
from pathlib import Path

import yaml

_YAML_PATH = Path(__file__).parent.parent.parent / "data" / "source_ontology.yaml"

_lock = threading.Lock()
_STATE: dict | None = None


def _build() -> dict:
    """Parse the YAML and build lookup indexes. Returns a state dict."""
    with _YAML_PATH.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    tree = raw.get("tree", [])

    # Flat index of every node (branch + leaf) by id.
    nodes_by_id: dict[str, dict] = {}
    # Leaf id -> {"site_keys": [...], "prefixes": [...]}
    leaf_rules: dict[str, dict] = {}
    # node id -> set of descendant leaf ids (a leaf maps to {itself}).
    descendant_leaves: dict[str, set[str]] = {}
    # child id -> parent id, for ancestor walks.
    parent_of: dict[str, str] = {}

    def walk(node: dict, parent_id: str | None):
        nid = node["id"]
        nodes_by_id[nid] = node
        if parent_id is not None:
            parent_of[nid] = parent_id
        children = node.get("children")
        if children:
            leaves_here: set[str] = set()
            for child in children:
                walk(child, nid)
                leaves_here |= descendant_leaves[child["id"]]
            descendant_leaves[nid] = leaves_here
        else:
            # Leaf.
            leaf_rules[nid] = {
                "site_keys": list(node.get("site_keys") or []),
                "prefixes": list(node.get("prefixes") or []),
            }
            descendant_leaves[nid] = {nid}

    for top in tree:
        walk(top, None)

    # site_key -> leaf id (exact matches). Prefix matches resolved lazily.
    exact: dict[str, str] = {}
    prefixes: list[tuple[str, str]] = []  # (prefix, leaf_id)
    for leaf_id, rule in leaf_rules.items():
        for sk in rule["site_keys"]:
            exact[sk] = leaf_id
        for pfx in rule["prefixes"]:
            prefixes.append((pfx, leaf_id))
    # Longest prefix first so more-specific rules win.
    prefixes.sort(key=lambda t: len(t[0]), reverse=True)

    return {
        "raw": raw,
        "tree": tree,
        "nodes_by_id": nodes_by_id,
        "leaf_rules": leaf_rules,
        "descendant_leaves": descendant_leaves,
        "parent_of": parent_of,
        "exact": exact,
        "prefixes": prefixes,
    }


def _state() -> dict:
    global _STATE
    if _STATE is None:
        with _lock:
            if _STATE is None:
                _STATE = _build()
    return _STATE


def reload() -> None:
    """Drop the cached state (test/helper hook)."""
    global _STATE
    with _lock:
        _STATE = None


# ── Public helpers ────────────────────────────────────────────────────────

def site_to_type(site_key: str) -> str:
    """Return the leaf node id a site_key maps to, or 'other' if unmapped.

    Resolution order: exact site_key match, then longest matching prefix.
    """
    if not site_key:
        return "other"
    st = _state()
    hit = st["exact"].get(site_key)
    if hit:
        return hit
    for pfx, leaf_id in st["prefixes"]:
        if site_key.startswith(pfx):
            return leaf_id
    return "other"


def leaf_for(site_key: str) -> str:
    """Alias for site_to_type."""
    return site_to_type(site_key)


def type_to_sites(node_id: str) -> list[str]:
    """Every KNOWN site_key under a node (leaf or branch).

    Only returns site_keys explicitly listed in the ontology (exact keys). Prefix
    rules match unknown/new keys at query time via site_to_type, so they are not
    enumerable here without a corpus scan.
    """
    st = _state()
    if node_id not in st["descendant_leaves"]:
        return []
    out: list[str] = []
    for leaf_id in st["descendant_leaves"][node_id]:
        out.extend(st["leaf_rules"][leaf_id]["site_keys"])
    return out


def type_to_prefixes(node_id: str) -> list[str]:
    """Every site_key prefix rule under a node (leaf or branch)."""
    st = _state()
    if node_id not in st["descendant_leaves"]:
        return []
    out: list[str] = []
    for leaf_id in st["descendant_leaves"][node_id]:
        out.extend(st["leaf_rules"][leaf_id]["prefixes"])
    return out


def sites_excluding(node_id: str, all_site_keys=None) -> list[str]:
    """Site_keys that do NOT belong to `node_id`'s branch.

    If `all_site_keys` (the live corpus site list) is provided, every key in it
    is classified via site_to_type and filtered — this is the reliable path,
    because it also excludes prefix-matched keys (e.g. new fj_* departments).

    Without it, falls back to the ontology's explicitly-listed keys only.
    """
    st = _state()
    target_leaves = st["descendant_leaves"].get(node_id, set())
    if all_site_keys is not None:
        return [sk for sk in all_site_keys
                if site_to_type(sk) not in target_leaves]
    # Fallback: explicit keys from every OTHER leaf.
    out: list[str] = []
    for leaf_id, rule in st["leaf_rules"].items():
        if leaf_id not in target_leaves:
            out.extend(rule["site_keys"])
    return out


def sites_under(node_id: str, all_site_keys) -> list[str]:
    """Every live site_key that resolves into `node_id`'s branch.

    Pass the live corpus site list so prefix-matched keys (e.g. fj_* provincial
    departments, or a brand-new one) are included. Use this to build the
    `include_sites` / `exclude_sites` lists for the query services — e.g.
    exclude_sites = sites_under('media', all_site_keys) hides all news.
    """
    st = _state()
    target = st["descendant_leaves"].get(node_id, set())
    return [sk for sk in all_site_keys if site_to_type(sk) in target]


def is_under(site_key: str, node_id: str) -> bool:
    """True if site_key resolves to a leaf within node_id's branch."""
    st = _state()
    return site_to_type(site_key) in st["descendant_leaves"].get(node_id, set())


def node_ids() -> set[str]:
    """All node ids (branches + leaves)."""
    return set(_state()["nodes_by_id"].keys())


def node(node_id: str) -> dict | None:
    """The raw node dict for an id, or None."""
    return _state()["nodes_by_id"].get(node_id)


def leaves() -> list[dict]:
    """Flat list of leaf node dicts."""
    st = _state()
    return [st["nodes_by_id"][lid] for lid in st["leaf_rules"]]


def tree() -> list[dict]:
    """The nested tree (deep copy), with a `sites` list attached to each node.

    Safe to hand to a template — mutating it will not corrupt the cache.
    """
    st = _state()
    t = copy.deepcopy(st["tree"])

    def annotate(n: dict):
        n["sites"] = type_to_sites(n["id"])
        for c in n.get("children", []) or []:
            annotate(c)

    for top in t:
        annotate(top)
    return t


def validate(all_site_keys) -> dict:
    """Check coverage against a live site_key list.

    Returns {"unmapped": [...], "counts": {node_id: n}, "total": N}. `unmapped`
    are keys that fell through to 'other' (excluding keys explicitly placed in
    the 'other' leaf on purpose).
    """
    st = _state()
    other_explicit = set(st["leaf_rules"].get("other", {}).get("site_keys", []))
    unmapped, counts = [], {}
    for sk in all_site_keys:
        leaf_id = site_to_type(sk)
        counts[leaf_id] = counts.get(leaf_id, 0) + 1
        if leaf_id == "other" and sk not in other_explicit:
            unmapped.append(sk)
    return {"unmapped": unmapped, "counts": counts, "total": len(all_site_keys)}
