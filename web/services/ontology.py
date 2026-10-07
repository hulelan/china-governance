"""Source-TYPE ontology service.

Loads data/source_ontology.yaml — a hierarchical tree of source *types* (what
KIND of body published a document: central ministry, provincial department,
district, news media, think-tank, ...) — and exposes helpers to map between
site_keys and type-nodes.

The tree is loaded and indexed once at import (cached at module level). The
YAML file is small and static, so this is cheap.

TWO RESOLUTION LAYERS (why: the hand-listed yaml rotted to 231/510 unmapped
site_keys — 21k docs in "Other" — within two months of crawler-fleet growth; a
list that must be edited for every new crawler cannot stay correct)
    1. EXPLICIT  — the yaml: exact `site_keys`, then longest matching `prefixes`.
                   This is the override layer and always wins.
    2. FALLBACK  — deterministic, from the `sites` table's `admin_level` (and
                   the govcms SITES `group` when the key is a govcms crawler):
                       central      -> central_ministry
                       provincial   -> local_province, or local_provincial_dept
                                       when the key is a `<prov>_<dept>` family key
                       department   -> local_city_dept
                       municipal    -> local_municipality
                       district     -> local_district
                       research     -> research
                       group assoc    -> research
                       group feedback -> central_legislative_judicial (central)
                                         / local_legislative (otherwise)
                   `media` is NEVER assigned by fallback: the "exclude news"
                   filter must not silently swallow a government site, so a
                   media-level key that is not listed in the yaml is UNRESOLVED
                   (-> 'other', and the validator fails on it).

The fallback needs each site_key's admin_level. Callers that already hold the
`sites` rows (get_sites()) should pass them — `sites_under(node, sites)` /
`sites_excluding(node, sites)` / `validate(sites)` accept either bare keys or
dicts/tuples carrying admin_level — which also REGISTERS the levels at module
level so later bare `site_to_type(key)` calls (templates, services) resolve too.

Key entry points
    site_to_type(site_key, admin_level=None) -> leaf node id (str); 'other' only
                                                 if neither layer can place it
    resolve(site_key, admin_level=None)      -> (leaf_id, how) where how is one of
                                                 'explicit' | 'prefix' | 'fallback'
                                                 | 'unresolved'
    type_to_sites(node_id)   -> list[str] of every EXPLICIT site_key under a node
    sites_under(node_id, sites)      -> live site_keys resolving into a branch
    sites_excluding(node_id, sites)  -> live site_keys NOT in a branch
    register_sites(sites)    -> remember admin_levels for bare-key lookups
    tree()                   -> the nested tree with .sites attached to each node
    node_ids()               -> set of all node ids
    leaves()                 -> list of leaf nodes (flat)
"""
from __future__ import annotations

import copy
import threading
from pathlib import Path

import yaml

_YAML_PATH = Path(__file__).parent.parent.parent / "data" / "source_ontology.yaml"

_lock = threading.Lock()
_STATE: dict | None = None

# site_key -> admin_level, registered from live `sites` rows (see register_sites).
_LEVELS: dict[str, str | None] = {}
# site_key -> (admin_level, group) from crawlers.govcms.SITES; loaded lazily and
# only once (None = not yet tried, {} = unavailable).
_GOVCMS: dict[str, tuple[str | None, str | None]] | None = None

# ── Fallback rules (layer 2). Kept in code, not yaml, so the yaml stays a pure
#    override list and these cannot be edited out of existence by accident. ──
FALLBACK_BY_LEVEL: dict[str, str] = {
    "central": "central_ministry",
    "provincial": "local_province",
    "department": "local_city_dept",
    "municipal": "local_municipality",
    "district": "local_district",
    "research": "research",
    # "media" deliberately absent — explicit-only.
}
# A provincial-level key with an underscore is a `<prov>_<dept>` department
# family member (fj_czt, hn_kjt, ...); whole-province portals never carry one.
PROVINCIAL_DEPT_LEAF = "local_provincial_dept"
FALLBACK_BY_GROUP: dict[str, str] = {
    "assoc": "research",
}
FEEDBACK_GROUP_LEAVES = ("central_legislative_judicial", "local_legislative")


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

    # Every fallback target must be a real leaf, or the fallback would invent
    # node ids the tree does not have. Fail at load, not at query time.
    targets = set(FALLBACK_BY_LEVEL.values()) | set(FALLBACK_BY_GROUP.values()) \
        | {PROVINCIAL_DEPT_LEAF, *FEEDBACK_GROUP_LEAVES}
    missing = targets - set(leaf_rules)
    if missing:
        raise ValueError(
            f"source_ontology.yaml lacks leaves the fallback targets: {sorted(missing)}")

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
    """Drop the cached state (test/helper hook). Registered levels are kept."""
    global _STATE
    with _lock:
        _STATE = None


# ── Site-level registry + govcms group lookup ─────────────────────────────

def _split_site(item) -> tuple[str, str | None]:
    """Accept a bare key, a (key, level) tuple, or a dict/Row with
    site_key [+ admin_level]; return (site_key, admin_level_or_None)."""
    if isinstance(item, str):
        return item, None
    if isinstance(item, (tuple, list)):
        return item[0], (item[1] if len(item) > 1 else None)
    # dict or sqlite Row-like
    try:
        sk = item["site_key"]
    except (KeyError, TypeError, IndexError):
        sk = getattr(item, "site_key")
    try:
        lvl = item["admin_level"]
    except (KeyError, TypeError, IndexError):
        lvl = getattr(item, "admin_level", None)
    return sk, lvl


def register_sites(sites) -> None:
    """Remember admin_levels from live `sites` rows so bare-key lookups
    (site_to_type(key)) can use the fallback layer. Idempotent; a level given
    explicitly on a later call overrides a previously registered one."""
    for item in sites:
        sk, lvl = _split_site(item)
        if sk and lvl:
            _LEVELS[sk] = lvl


def _govcms_meta() -> dict[str, tuple[str | None, str | None]]:
    """site_key -> (admin_level, group) from crawlers.govcms.SITES, loaded once.
    The import is stdlib-only and side-effect free; if it fails (e.g. a trimmed
    deploy without crawlers/), the fallback just loses the `group` signal."""
    global _GOVCMS
    if _GOVCMS is None:
        with _lock:
            if _GOVCMS is None:
                try:
                    from crawlers.govcms import SITES as _S  # noqa: WPS433
                    _GOVCMS = {k: (c.get("admin_level"), c.get("group"))
                               for k, c in _S.items()}
                except Exception:
                    _GOVCMS = {}
    return _GOVCMS


def _fallback_leaf(site_key: str, admin_level: str | None) -> str | None:
    """Layer 2: a leaf from admin_level / govcms group, or None if unresolvable."""
    meta = _govcms_meta().get(site_key)
    level = admin_level or _LEVELS.get(site_key) or (meta[0] if meta else None)
    group = meta[1] if meta else None

    if group == "feedback":
        return FEEDBACK_GROUP_LEAVES[0] if level == "central" else FEEDBACK_GROUP_LEAVES[1]
    if group in FALLBACK_BY_GROUP:
        return FALLBACK_BY_GROUP[group]
    if level == "provincial" and "_" in site_key:
        return PROVINCIAL_DEPT_LEAF
    return FALLBACK_BY_LEVEL.get(level or "")


# ── Public helpers ────────────────────────────────────────────────────────

def resolve(site_key: str, admin_level: str | None = None) -> tuple[str, str]:
    """Return (leaf_id, how). `how` is 'explicit' (exact yaml key), 'prefix'
    (yaml prefix rule), 'fallback' (admin_level / govcms group), or
    'unresolved' (leaf_id == 'other')."""
    if not site_key:
        return "other", "unresolved"
    st = _state()
    hit = st["exact"].get(site_key)
    if hit:
        return hit, "explicit"
    for pfx, leaf_id in st["prefixes"]:
        if site_key.startswith(pfx):
            return leaf_id, "prefix"
    fb = _fallback_leaf(site_key, admin_level)
    if fb:
        return fb, "fallback"
    return "other", "unresolved"


def site_to_type(site_key: str, admin_level: str | None = None) -> str:
    """Return the leaf node id a site_key maps to; 'other' only if neither the
    yaml nor the admin_level fallback can place it.

    Resolution order: exact yaml key, longest yaml prefix, then the
    deterministic fallback (see module docstring). Pass `admin_level` when you
    have it; otherwise the registered level (register_sites) or the govcms
    SITES entry is used.
    """
    return resolve(site_key, admin_level)[0]


def leaf_for(site_key: str, admin_level: str | None = None) -> str:
    """Alias for site_to_type."""
    return site_to_type(site_key, admin_level)


def type_to_sites(node_id: str) -> list[str]:
    """Every EXPLICIT site_key under a node (leaf or branch).

    Only returns site_keys listed in the yaml (exact keys). Prefix- and
    fallback-resolved keys need the live site list — use sites_under().
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


def _classify_live(sites) -> list[tuple[str, str]]:
    """[(site_key, leaf_id)] for live site items, registering their levels."""
    register_sites(sites)
    out = []
    for item in sites:
        sk, lvl = _split_site(item)
        out.append((sk, site_to_type(sk, lvl)))
    return out


def sites_excluding(node_id: str, all_site_keys=None) -> list[str]:
    """Site_keys that do NOT belong to `node_id`'s branch.

    If `all_site_keys` (the live corpus site list — bare keys or get_sites()
    rows) is provided, every key is classified via site_to_type and filtered —
    this is the reliable path, because it also covers prefix- and
    fallback-resolved keys (e.g. new fj_* departments, new prefecture cities).

    Without it, falls back to the ontology's explicitly-listed keys only.
    """
    st = _state()
    target_leaves = st["descendant_leaves"].get(node_id, set())
    if all_site_keys is not None:
        return [sk for sk, leaf in _classify_live(all_site_keys)
                if leaf not in target_leaves]
    # Fallback: explicit keys from every OTHER leaf.
    out: list[str] = []
    for leaf_id, rule in st["leaf_rules"].items():
        if leaf_id not in target_leaves:
            out.extend(rule["site_keys"])
    return out


def sites_under(node_id: str, all_site_keys) -> list[str]:
    """Every live site_key that resolves into `node_id`'s branch.

    Pass the live corpus site list (bare keys, or get_sites() rows — rows are
    preferred because they carry admin_level for the fallback layer) so
    prefix-/fallback-matched keys are included. Use this to build the
    `include_sites` / `exclude_sites` lists for the query services — e.g.
    exclude_sites = sites_under('media', sites) hides all news.
    """
    st = _state()
    target = st["descendant_leaves"].get(node_id, set())
    return [sk for sk, leaf in _classify_live(all_site_keys) if leaf in target]


def is_under(site_key: str, node_id: str, admin_level: str | None = None) -> bool:
    """True if site_key resolves to a leaf within node_id's branch."""
    st = _state()
    return site_to_type(site_key, admin_level) in st["descendant_leaves"].get(node_id, set())


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
    """The nested tree (deep copy), with a `sites` list (explicit keys) attached
    to each node.

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
    """Check coverage against a live site list (bare keys or get_sites() rows).

    Returns
        explicit : {site_key: leaf}  placed by a yaml exact key or prefix
        fallback : {site_key: leaf}  placed by admin_level / govcms group
        unmapped : [site_key, ...]   neither layer could place -> 'other'
                                     (excluding keys deliberately listed in 'other')
        counts   : {leaf_id: n_sites}
        total    : N
    Only `unmapped` is a failure; `fallback` is informational (it is the
    designed path for new crawlers).
    """
    st = _state()
    other_explicit = set(st["leaf_rules"].get("other", {}).get("site_keys", []))
    register_sites(all_site_keys)
    explicit, fallback, unmapped, counts = {}, {}, [], {}
    for item in all_site_keys:
        sk, lvl = _split_site(item)
        leaf_id, how = resolve(sk, lvl)
        counts[leaf_id] = counts.get(leaf_id, 0) + 1
        if how in ("explicit", "prefix"):
            explicit[sk] = leaf_id
        elif how == "fallback":
            fallback[sk] = leaf_id
        elif sk not in other_explicit:
            unmapped.append(sk)
    return {"explicit": explicit, "fallback": fallback, "unmapped": unmapped,
            "counts": counts, "total": len(all_site_keys)}
