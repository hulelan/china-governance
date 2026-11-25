#!/usr/bin/env python3
"""Section registry: what each crawler is CONFIGURED to crawl, joined to what we HOLD.

Why this exists (2026-11-25). "We crawl SAMR" was true and useless: the crawler had
six sections and not the press-conference one. Site-level coverage (`site_stats`,
`docs/working/coverage.csv`) cannot see that, and the older section audit
(`docs/working/section-coverage.md`) was a one-off probe that went stale. This script
derives the section list FROM THE CRAWLER CODE on every run, so a section added to a
crawler appears here without anyone maintaining a second table.

Three things it reports that a site-level count hides:

  * per configured section: documents held, with a body, newest date;
  * sites whose crawler exposes NO section structure (`kind='unknown'`) — listed
    explicitly, with the URL path families we actually hold (`kind='observed'`),
    never silently omitted;
  * whether the nightly (`scripts/daily_sync.sh`) runs the site at all. A site can
    be fully configured and never scheduled: mfa and nea both were.

How sections are found: every module in `crawlers/` is imported and its module-level
config is read by SHAPE, not by a per-site table —
  - a module with `SITE_KEY` and a section container (`SECTIONS`, `DEPARTMENTS`,
    `CATEGORIES`, `INDEX_URLS`, ... anything matched by `_CONTAINER_RE`);
  - a registry module (`SITES` / `NFCMS_SITES` / `MINISTRIES`: site_key -> cfg),
    whose cfg may carry `sections`.
A section entry may be a str, a tuple or a dict; `_parse_entry` pulls a name, any
path/URL and any cap out of whichever it is.

How documents are attributed to a section (first hit wins):
  1. LABEL  — `classify_main_name` equals the section's name (most crawlers store it);
  2. PREFIX — the document URL's path starts with the section's directory (longest
     prefix wins; a section given as a full URL also has to match the host).
Sections configured only by an opaque id (a page_id, a channel id) can match by label
alone; if neither rule matches anything the row says `match='none'` rather than
pretending the section is empty.

Cost: one header-only scan of `documents` plus two covering-index reads (see
MAIN_SCAN_SQL below for why `url` must not ride along in the table scan); no SQL
GROUP BY. Writes `section_registry` + `section_registry_meta` in one short
transaction.

    python3 scripts/build_section_registry.py --dry-run            # print, write nothing
    python3 scripts/build_section_registry.py --write              # rebuild the table
    python3 scripts/build_section_registry.py --dry-run --out-json /tmp/sections.json \
        --out-csv docs/working/section-registry.csv
    python3 scripts/build_section_registry.py --dry-run --site samr
    python3 scripts/build_section_registry.py --dry-run --out-db /tmp/preview.db   # table, elsewhere
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import pkgutil
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "documents.db"
DAILY_SYNC = ROOT / "scripts" / "daily_sync.sh"

# Module-level attribute names that hold a site's sections. Matched by pattern so a
# new crawler that follows any existing convention is picked up with no edit here.
_CONTAINER_RE = re.compile(
    r"^(SECTIONS|SECTION_PAGES|DEPARTMENTS|CATEGORIES|CATEGORY_PATHS|[A-Z]+_CATEGORIES|"
    r"INDEX_URLS|INDEX_PAGES|[A-Z]+_CHANNELS|CHANNELS|FEEDS|[A-Z]+_FEEDS)$")
# Module-level attribute names that hold a site REGISTRY (site_key -> cfg dict).
_REGISTRY_RE = re.compile(r"^(SITES|[A-Z]+_SITES|MINISTRIES)$")
# Never crawler modules.
_SKIP_MODULES = {"base", "__init__", "baike"}
_CAP_KEY_RE = re.compile(r"(^|_)(cap|max_pages|max_docs|limit)$")
_CJK_RE = re.compile(r"[一-鿿]")
# A trailing path component that is a listing page, not a directory of articles.
_LISTING_TAIL_RE = re.compile(r"^(index|list|default)?[^/]*\.(s?html?|jsp|php|aspx?)$", re.I)

STALE_DAYS = 45      # newest held document older than this -> 'stale'
AGING_DAYS = 14


# --------------------------------------------------------------------------- #
# 1. Introspection
# --------------------------------------------------------------------------- #

def _looks_like_path(s: str) -> bool:
    if not isinstance(s, str) or not s or _CJK_RE.search(s) or " " in s:
        return False
    return s.startswith(("/", "http://", "https://")) or ("/" in s and not s.startswith("<"))


def norm_prefix(path: str, base_url: str = "") -> tuple[str, str]:
    """A configured section path/URL -> (host, directory-prefix).

    host is '' when the config gave a bare path (then only the path is compared).
    '/zw/zjwj/index.html' -> ('', '/zw/zjwj/');  '/sjj/zwgk/zcfb/list/' -> ('', '/sjj/zwgk/zcfb/')
    'http://scitech.ce.cn/sy/zx/' -> ('scitech.ce.cn', '/sy/zx/')
    """
    host = ""
    if path.startswith(("http://", "https://")):
        sp = urlsplit(path)
        host, path = sp.netloc.lower(), sp.path or "/"
    if not path.startswith("/"):
        path = "/" + path
    parts = path.split("/")
    # drop a listing filename, then a bare 'list' directory (nda: .../zcfb/list/)
    if parts and parts[-1] and _LISTING_TAIL_RE.match(parts[-1]):
        parts[-1] = ""
    elif parts and parts[-1] and "." not in parts[-1]:
        parts.append("")                      # 'tiaofasi/144941/144957' is a directory
    elif parts and parts[-1]:
        parts[-1] = ""                        # some other file: keep its directory
    while len(parts) > 2 and parts[-2].lower() in ("list",):
        parts.pop(-2)
    out = "/".join(parts)
    out = re.sub(r"/{2,}", "/", out)
    return host, out or "/"


def _parse_entry(key, value) -> dict:
    """One section entry of any shape -> {key, name, paths, cap, children}."""
    out = {"key": str(key), "name": "", "paths": [], "cap": None, "children": None}
    if isinstance(key, str) and _looks_like_path(key) and ("/" in key):
        out["paths"].append(key)

    def take_str(s: str):
        if _looks_like_path(s):
            out["paths"].append(s)
        elif _CJK_RE.search(s) and not out["name"]:
            out["name"] = s

    if isinstance(value, str):
        take_str(value)
        if not out["name"] and not out["paths"]:
            out["name"] = value               # e.g. an opaque id or an English label
    elif isinstance(value, (tuple, list)):
        for el in value:
            if isinstance(el, str):
                take_str(el)
            elif isinstance(el, bool):
                continue
            elif isinstance(el, int) and out["cap"] is None:
                out["cap"] = el               # pbc: (path, label, per-section page cap)
        if not out["name"]:
            strs = [e for e in value if isinstance(e, str) and not _looks_like_path(e)]
            if strs:
                out["name"] = strs[0]
    elif isinstance(value, dict):
        nm = value.get("name") or value.get("label") or ""
        out["name"] = nm if isinstance(nm, str) else ""
        for k, v in value.items():
            if k in ("name", "label", "note"):
                continue
            if isinstance(v, str) and _looks_like_path(v) and k not in ("base_url", "domain", "host"):
                out["paths"].append(v)
            elif (isinstance(v, str) and v and re.search(r"(path|prefix)", str(k))
                  and re.fullmatch(r"[\w.-]+", v)):
                out["paths"].append(f"/{v}/")  # xinhua: path_prefix 'tech' (no slash)
            elif isinstance(v, int) and not isinstance(v, bool) and _CAP_KEY_RE.search(str(k)):
                out["cap"] = v
        if isinstance(value.get("sections"), (dict, list, tuple)):
            out["children"] = value["sections"]
        if isinstance(value.get("base_url"), str):
            out["base_url"] = value["base_url"]
    if not out["name"]:
        out["name"] = out["key"]
    return out


def _entries(container) -> list[tuple]:
    if isinstance(container, dict):
        return list(container.items())
    out = []
    for i, el in enumerate(container):
        if isinstance(el, str):
            out.append((el, el))
        elif isinstance(el, (tuple, list)) and el and isinstance(el[0], str):
            out.append((el[0], el))
        else:
            out.append((str(i), el))
    return out


def _sections_from(container, source: str, base_url: str, parent_name: str = "") -> list[dict]:
    rows = []
    bare_list = isinstance(container, (list, tuple))
    for key, value in _entries(container):
        e = _parse_entry(key, value)
        if (bare_list and isinstance(value, str) and not e["paths"]
                and re.fullmatch(r"[\w.-]+", value)):
            e["paths"].append(f"/{value}/")    # guancha SECTION_PAGES: ['politics', ...]
        if e["children"] is not None:         # zhejiang DEPARTMENTS -> dept -> sections
            rows.extend(_sections_from(e["children"], source, base_url, e["name"]))
            continue
        labels = [e["name"]]
        if parent_name:
            labels.append(f"{parent_name} / {e['name']}")
        b = e.get("base_url") or base_url
        prefixes = []
        for p in e["paths"]:
            host, pre = norm_prefix(p, b)
            if (host, pre) not in prefixes:
                prefixes.append((host, pre))
        rows.append({
            "section_key": (f"{parent_name}/" if parent_name else "") + e["key"],
            "name": (f"{parent_name} / " if parent_name else "") + e["name"],
            "labels": labels,
            "config_path": e["paths"][0] if e["paths"] else "",
            "prefixes": prefixes,
            "cap": e["cap"],
            "source": source,
        })
    return rows


def _site_cfg(mod) -> dict:
    for attr in ("SITE_CFG", "CFG"):
        v = getattr(mod, attr, None)
        if isinstance(v, dict):
            return v
    return {}


def collect(package: str = "crawlers", modules: list | None = None) -> dict:
    """Introspect every crawler module -> {site_key: site dict}.

    site dict: {site_key, name, base_url, admin_level, module, group, tier,
                structure: 'sections'|'unknown', sections: [...], import_error?}
    `modules` (already-imported module objects) is for tests.
    """
    sites: dict[str, dict] = {}
    errors: dict[str, str] = {}
    if modules is None:
        pkg = importlib.import_module(package)
        modules = []
        for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
            if m.name in _SKIP_MODULES:
                continue
            try:
                modules.append(importlib.import_module(f"{package}.{m.name}"))
            except Exception as exc:          # a crawler that cannot import is a finding
                errors[m.name] = f"{type(exc).__name__}: {exc}"[:200]

    def add(site_key, cfg, modname, sections, source):
        s = sites.setdefault(site_key, {
            "site_key": site_key, "name": "", "base_url": "", "admin_level": "",
            "module": modname, "group": None, "tier": None, "sections": [],
        })
        s["name"] = s["name"] or str(cfg.get("name", ""))
        s["base_url"] = s["base_url"] or str(cfg.get("base_url", ""))
        s["admin_level"] = s["admin_level"] or str(cfg.get("admin_level", ""))
        s["group"] = s["group"] or cfg.get("group")
        s["tier"] = s["tier"] if s["tier"] is not None else cfg.get("tier")
        s["sections"].extend(sections)

    for mod in modules:
        modname = mod.__name__.rsplit(".", 1)[-1]
        attrs = {a: getattr(mod, a) for a in dir(mod) if a.isupper()}
        site_key = attrs.get("SITE_KEY") if isinstance(attrs.get("SITE_KEY"), str) else None
        registries = {a: v for a, v in attrs.items()
                      if _REGISTRY_RE.match(a) and isinstance(v, dict) and v
                      and all(isinstance(x, dict) for x in v.values())}
        # A registry whose cfgs carry their own site_key (sz_gazette.NFCMS_SITES) owns
        # the module's SITE_KEY too, so it is handled as a registry, not twice.
        for rname, reg in registries.items():
            for key, cfg in reg.items():
                sk = cfg.get("site_key") if isinstance(cfg.get("site_key"), str) else key
                inner = cfg.get("site_cfg") if isinstance(cfg.get("site_cfg"), dict) else cfg
                secs = []
                if isinstance(cfg.get("sections"), (dict, list, tuple)) and cfg["sections"]:
                    secs = _sections_from(cfg["sections"], f"crawlers.{modname}:{rname}[{key}].sections",
                                          str(inner.get("base_url", "")))
                merged = dict(inner)
                for k in ("group", "tier"):
                    merged.setdefault(k, cfg.get(k))
                add(sk, merged, modname, secs, rname)
        if site_key and site_key not in sites:
            cfg = _site_cfg(mod)
            secs = []
            for a, v in sorted(attrs.items()):
                if _CONTAINER_RE.match(a) and isinstance(v, (dict, list, tuple)) and v:
                    secs.extend(_sections_from(v, f"crawlers.{modname}:{a}", str(cfg.get("base_url", ""))))
            add(site_key, cfg, modname, secs, "SITE_KEY")

    for s in sites.values():
        s["structure"] = "sections" if s["sections"] else "unknown"
    if errors:
        sites["__import_errors__"] = errors      # type: ignore[assignment]
    return sites


# --------------------------------------------------------------------------- #
# 2. Is the site in the nightly?
# --------------------------------------------------------------------------- #

_FOR_RE = re.compile(r"^\s*for\s+(\w+)\s+in\s+(.+?);\s*do\s*$")
_CRAWL_RE = re.compile(r"python3\s+-m\s+crawlers\.([\w$]+)(.*)$")


def parse_schedule(sh_text: str) -> list[dict]:
    """`daily_sync.sh` -> [{module, site, group, tier, cadence}] for the DROPLET path.

    Understands exactly the shapes the script uses: `for x in a b c; do`, the
    `run_crawler` / `run_crawler_t` / `run_weekly <dow>` wrappers, a weekday `if`
    around a crawler, and the `IS_MAC` branch (skipped: the droplet is the runner).
    """
    out = []
    loop_var, loop_vals = None, []
    mac_depth = None          # nesting depth at which the IS_MAC 'then' branch opened
    depth = 0
    weekday_if = []           # stack of bools: is this `if` a weekday gate?
    lines = sh_text.replace("\\\n", " ").splitlines()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _FOR_RE.match(line)
        if m:
            loop_var, loop_vals = m.group(1), m.group(2).split()
            continue
        if line == "done":
            loop_var, loop_vals = None, []
            continue
        if re.match(r"^if\b", line):
            depth += 1
            weekday_if.append("date -u +%u" in line or "date +%u" in line)
            if "IS_MAC" in line and '"true"' in line and mac_depth is None:
                mac_depth = depth
            continue
        if line.startswith("else"):
            if mac_depth == depth:
                mac_depth = -depth           # now in the droplet branch
            continue
        if line == "fi":
            if mac_depth is not None and abs(mac_depth) == depth:
                mac_depth = None
            depth = max(0, depth - 1)
            if weekday_if:
                weekday_if.pop()
            continue
        if mac_depth is not None and mac_depth > 0:
            continue                         # Mac-only branch
        m = _CRAWL_RE.search(line)
        if not m or line.startswith(("log ", "echo ")):
            continue
        weekly = line.startswith("run_weekly") or any(weekday_if)
        vals = loop_vals if (loop_var and f"${loop_var}" in line) else [None]
        for v in vals:
            mod, rest = m.group(1), m.group(2)
            if v is not None:
                mod = mod.replace(f"${loop_var}", v)
                rest = rest.replace(f"${loop_var}", v)

            def opt(name):
                mm = re.search(rf"--{name}\s+(\S+)", rest)
                return mm.group(1) if mm else None
            out.append({"module": mod, "site": opt("site"), "group": opt("group"),
                        "tier": opt("tier"), "cadence": "weekly" if weekly else "nightly"})
    return out


def schedule_for(site: dict, sched: list[dict]) -> str:
    """'nightly' | 'weekly' | 'not scheduled' for one introspected site."""
    best = "not scheduled"
    for e in sched:
        if e["module"] != site["module"]:
            continue
        if e["site"]:
            hit = e["site"] == site["site_key"]
        elif e["group"]:
            hit = site.get("group") == e["group"]
        elif e["tier"]:
            hit = str(site.get("tier")) == e["tier"]
        else:
            # A bare module call runs every site it owns — except tier-3 sites, which
            # finmedia/theory both document as "by name only".
            hit = not (isinstance(site.get("tier"), int) and site["tier"] >= 3)
        if hit:
            if e["cadence"] == "nightly":
                return "nightly"
            best = "weekly"
    return best


# --------------------------------------------------------------------------- #
# 3. Join to the corpus
# --------------------------------------------------------------------------- #

_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")


def doc_date(date_written, date_published, max_day: str) -> str:
    """Best YYYY-MM-DD for a row, '' if none. date_written is 0 on several crawlers
    (gov, ndrc, mfa) and date_published is free text, so both are tried; a date in
    the future is a parse artefact and is dropped rather than read as 'fresh'."""
    d = ""
    if isinstance(date_published, str):
        m = _DATE_RE.match(date_published.strip())
        if m:
            d = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if not d and isinstance(date_written, int) and date_written > 0:
        d = (datetime(1970, 1, 1, tzinfo=timezone.utc)
             + timedelta(seconds=date_written, hours=8)).strftime("%Y-%m-%d")
    if d and (d > max_day or d < "1900-01-01"):
        return ""
    return d


def staleness(newest: str, today: str) -> str:
    if not newest:
        return "undated"
    age = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(newest, "%Y-%m-%d")).days
    return "fresh" if age <= AGING_DAYS else ("aging" if age <= STALE_DAYS else "stale")


def _family(path: str) -> str:
    """URL path -> its first directory ('/yaowen/liebiao/202611/x.htm' -> '/yaowen/')."""
    parts = [p for p in path.split("/") if p]
    if len(parts) <= 1:
        return "/"
    # A date directory is not a section: /20260731/<hex>/c.html, /2026-11/03/c_1.htm
    if re.fullmatch(r"\d{4}(-?\d{2}){0,2}|t?\d{6,8}", parts[0]):
        return "/<date>/"
    return f"/{parts[0]}/"


# The three reads. `url` and `classify_main_name` sit AFTER `body_text_cn` in the
# record, so selecting them in the table scan makes SQLite walk every body's overflow
# chain to reach them (~4 GB; measured 2026-11-25 at several minutes on a cold cache
# against ~5 s for the header-only scan). Each is therefore read from its own
# covering index and joined by rowid in Python. `tests/test_section_registry.py`
# asserts the two index plans, so an edit that drags the body back in fails loudly.
#
# The body flag is `octet_length(...) > 0`, NOT `body_text_cn != ''`. SQLite answers
# octet_length() from the record header (3.43+) but loads the whole value to compare
# it with '', overflow pages and all: 213 s against 54 s cold on the droplet, same
# rows, same answer (measured 2026-11-25). Older SQLite falls back to the comparison.
_HAS_OCTET_LENGTH = sqlite3.sqlite_version_info >= (3, 43, 0)
_BODY_FLAG = "octet_length(body_text_cn) > 0" if _HAS_OCTET_LENGTH else "body_text_cn != ''"
MAIN_SCAN_SQL = f"SELECT id, site_key, date_written, date_published, {_BODY_FLAG} FROM documents"
URL_SQL = "SELECT id, url FROM documents WHERE url != ''"
LABEL_SQL = ("SELECT id, classify_main_name FROM documents "
             "WHERE classify_main_name > ''")


def load_url_and_label(conn: sqlite3.Connection, only_site: str | None = None):
    """-> ({id: url}, {id: classify_main_name}) from covering indexes."""
    if only_site:            # preview path: the site index bounds it, bodies are few
        urls, labels = {}, {}
        for i, u, lab in conn.execute(
                "SELECT id, url, classify_main_name FROM documents WHERE site_key = ?", (only_site,)):
            if u:
                urls[i] = u
            if lab:
                labels[i] = lab
        return urls, labels
    urls = dict(conn.execute(URL_SQL))
    intern: dict[str, str] = {}
    labels = {i: intern.setdefault(lab, lab) for i, lab in conn.execute(LABEL_SQL)}
    return urls, labels


class _Agg:
    __slots__ = ("docs", "body", "newest", "newest_crawl", "example")

    def __init__(self):
        self.docs = 0
        self.body = 0
        self.newest = ""
        self.newest_crawl = ""
        self.example = ""

    def add(self, has_body, day, crawl, url):
        self.docs += 1
        self.body += 1 if has_body else 0
        if day and day >= self.newest:
            self.newest = day
            self.example = url or self.example
        if crawl and crawl > self.newest_crawl:
            self.newest_crawl = crawl
        if not self.example:
            self.example = url or ""


def build_rows(conn: sqlite3.Connection, sites: dict, sched: list[dict],
               today: str | None = None, only_site: str | None = None,
               observed_top: int = 8) -> list[dict]:
    """Scan `documents` once and return the registry rows."""
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    max_day = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")
    sites = {k: v for k, v in sites.items() if not k.startswith("__")}

    # per-site lookup structures
    label_ix: dict[str, dict[str, int]] = {}
    prefix_ix: dict[str, list[tuple[str, str, int]]] = {}
    for sk, s in sites.items():
        li, pi = {}, []
        for i, sec in enumerate(s["sections"]):
            for lab in sec["labels"]:
                if lab:
                    li.setdefault(lab, i)
            for host, pre in sec["prefixes"]:
                pi.append((host, pre, i))
        pi.sort(key=lambda t: -len(t[1]))     # longest prefix first
        label_ix[sk], prefix_ix[sk] = li, pi

    sec_agg: dict[tuple, _Agg] = defaultdict(_Agg)
    sec_how: dict[tuple, set] = defaultdict(set)
    site_agg: dict[str, _Agg] = defaultdict(_Agg)
    rest_agg: dict[str, _Agg] = defaultdict(_Agg)
    fam_agg: dict[tuple, _Agg] = defaultdict(_Agg)

    urls, labels = load_url_and_label(conn, only_site)
    sql, args = MAIN_SCAN_SQL, ()
    if only_site:
        sql, args = MAIN_SCAN_SQL + " WHERE site_key = ?", (only_site,)
    crawl = ""
    for doc_id, sk, dw, dp, has_body in conn.execute(sql, args):
        url = urls.get(doc_id, "")
        label = labels.get(doc_id, "")
        day = doc_date(dw, dp, max_day)
        site_agg[sk].add(has_body, day, crawl, url)
        sp = urlsplit(url) if url else None
        path = sp.path if sp else ""
        host = sp.netloc.lower() if sp else ""
        hit, how = None, ""
        if sk in label_ix:
            hit = label_ix[sk].get(label or "")
            if hit is not None:
                how = "label"
            elif path:
                for h, pre, i in prefix_ix[sk]:
                    if path.startswith(pre) and (not h or h == host):
                        hit, how = i, "prefix"
                        break
        if hit is not None:
            sec_agg[(sk, hit)].add(has_body, day, crawl, url)
            sec_how[(sk, hit)].add(how)
        else:
            rest_agg[sk].add(has_body, day, crawl, url)
            fam_agg[(sk, (host + _family(path)) if path else "(no url)")].add(has_body, day, crawl, url)

    db_sites = {}
    try:
        for sk, name, base, lvl in conn.execute("SELECT site_key, name, base_url, admin_level FROM sites"):
            db_sites[sk] = (name or "", base or "", lvl or "")
    except sqlite3.Error:
        pass

    rows = []
    all_keys = sorted(set(sites) | set(site_agg) | set(db_sites))
    if only_site:
        all_keys = [k for k in all_keys if k == only_site]
    for sk in all_keys:
        s = sites.get(sk)
        dbn = db_sites.get(sk, ("", "", ""))
        base = {
            "site_key": sk,
            "site_name": (s or {}).get("name") or dbn[0],
            "admin_level": (s or {}).get("admin_level") or dbn[2],
            "module": (s or {}).get("module", ""),
            "schedule": schedule_for(s, sched) if s else "no crawler",
        }
        sa = site_agg.get(sk, _Agg())

        def row(kind, key, name, agg, **kw):
            r = dict(base)
            r.update({
                "kind": kind, "section_key": key, "name": name,
                "config_path": kw.get("config_path", ""), "source": kw.get("source", ""),
                "cap": kw.get("cap"), "match": kw.get("match", ""),
                "docs": agg.docs, "with_body": agg.body, "newest": agg.newest,
                "newest_crawl": agg.newest_crawl, "example_url": agg.example,
                "staleness": kw.get("staleness") or (staleness(agg.newest, today) if agg.docs else "empty"),
            })
            rows.append(r)

        row("site", "", base["site_name"], sa,
            match=("sections" if s and s["sections"] else "unknown" if s else "no crawler"))
        if s is None:
            row("unknown", "", "no crawler module declares this site "
                "(ingested by URL, merged, or its crawler was removed)", _Agg(), staleness="n/a")
        elif not s["sections"]:
            row("unknown", "", "sections unknown: the crawler exposes no section structure "
                "(feed / API / dynamic category tree)", _Agg(), staleness="n/a")
        else:
            for i, sec in enumerate(s["sections"]):
                agg = sec_agg.get((sk, i), _Agg())
                how = "+".join(sorted(sec_how.get((sk, i), ()))) or "none"
                row("section", sec["section_key"], sec["name"], agg, config_path=sec["config_path"],
                    source=sec["source"], cap=sec["cap"], match=how,
                    staleness=None if agg.docs else "no docs matched")
        # What we hold that no configured section explains — and, for sites with no
        # section structure, the only section-level picture there is.
        ra = rest_agg.get(sk)
        if ra and ra.docs:
            if s and s["sections"]:
                row("unattributed", "", "held, but matched to no configured section", ra)
            fams = sorted(((k[1], a) for k, a in fam_agg.items() if k[0] == sk),
                          key=lambda t: -t[1].docs)
            for fam, a in fams[:observed_top]:
                row("observed", fam, fam, a, match="url family")
    return rows


# --------------------------------------------------------------------------- #
# 4. Output
# --------------------------------------------------------------------------- #

COLUMNS = ["site_key", "site_name", "admin_level", "module", "schedule", "kind", "section_key",
           "name", "config_path", "source", "cap", "match", "docs", "with_body", "newest",
           "newest_crawl", "staleness", "example_url"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS section_registry (
    site_key TEXT NOT NULL, site_name TEXT, admin_level TEXT, module TEXT, schedule TEXT,
    kind TEXT NOT NULL,          -- site | section | unattributed | observed | unknown
    section_key TEXT, name TEXT, config_path TEXT, source TEXT, cap INTEGER,
    match TEXT,                  -- label | prefix | label+prefix | none | url family
    docs INTEGER, with_body INTEGER, newest TEXT, newest_crawl TEXT,
    staleness TEXT, example_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_section_registry_site ON section_registry(site_key);
CREATE TABLE IF NOT EXISTS section_registry_meta (k TEXT PRIMARY KEY, v TEXT);
"""


def write_table(db_path: Path, rows: list[dict], meta: dict) -> None:
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    try:
        conn.executescript(SCHEMA)
        with conn:                            # one short transaction
            conn.execute("DELETE FROM section_registry")
            conn.executemany(
                f"INSERT INTO section_registry ({', '.join(COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in COLUMNS)})",
                [tuple(r.get(c) for c in COLUMNS) for r in rows])
            conn.execute("DELETE FROM section_registry_meta")
            conn.executemany("INSERT INTO section_registry_meta (k, v) VALUES (?, ?)",
                             [(k, str(v)) for k, v in meta.items()])
    finally:
        conn.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--write", action="store_true", help="rebuild the section_registry table")
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write no table")
    ap.add_argument("--site", help="one site only (implies no table write)")
    ap.add_argument("--out-db", help="write the table into THIS sqlite file instead of --db "
                                     "(a preview copy; works with --dry-run)")
    ap.add_argument("--out-json")
    ap.add_argument("--out-csv")
    ap.add_argument("--today", help="YYYY-MM-DD override (tests)")
    args = ap.parse_args(argv)
    if not (args.write or args.dry_run):
        ap.error("pass --write or --dry-run")
    if args.write and args.site:
        ap.error("--site is a preview filter; it cannot be combined with --write")

    t0 = time.time()
    sites = collect()
    errors = sites.pop("__import_errors__", {})
    sched = parse_schedule(DAILY_SYNC.read_text()) if DAILY_SYNC.exists() else []
    ro = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=60)
    ro.execute("PRAGMA busy_timeout=60000")
    try:
        rows = build_rows(ro, sites, sched, today=args.today, only_site=args.site)
    finally:
        ro.close()
    today = args.today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n_site = sum(1 for r in rows if r["kind"] == "site")
    n_sec = sum(1 for r in rows if r["kind"] == "section")
    meta = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "today": today, "sites": n_site, "sections": n_sec,
        "sites_sections_unknown": sum(1 for r in rows if r["kind"] == "unknown"),
        "sections_no_docs": sum(1 for r in rows if r["kind"] == "section" and not r["docs"]),
        "sections_stale": sum(1 for r in rows if r["kind"] == "section" and r["staleness"] == "stale"),
        "sites_not_scheduled": sum(1 for r in rows if r["kind"] == "site" and r["schedule"] == "not scheduled"),
        "import_errors": json.dumps(errors, ensure_ascii=False),
        "seconds": f"{time.time() - t0:.1f}",
    }
    for mod, err in errors.items():
        print(f"IMPORT ERROR crawlers.{mod}: {err}", file=sys.stderr)

    if args.out_json:
        Path(args.out_json).write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1))
    if args.out_csv:
        with open(args.out_csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows({c: r.get(c) for c in COLUMNS} for r in rows)
    if args.out_db and not args.site:
        write_table(Path(args.out_db), rows, meta)
    if args.write:
        write_table(Path(args.db), rows, meta)

    if args.site or args.dry_run:
        shown = rows if args.site else [r for r in rows if r["kind"] == "site"
                                        and r["schedule"] == "not scheduled" and r["docs"]][:40]
        if not args.site:
            print("sites configured in a crawler but NOT in the nightly (with docs held):")
        for r in shown:
            print(f"  {r['site_key']:14} {r['kind']:12} {r['schedule']:13} {str(r['docs']):>7} "
                  f"{str(r['with_body']):>7} {r['newest'] or '-':10} {r['staleness']:14} "
                  f"{r['match']:12} {r['name'][:40]}  {r['config_path']}")
    print(f"section registry: {meta['sites']} sites, {meta['sections']} configured sections, "
          f"{meta['sites_sections_unknown']} sites with sections unknown, "
          f"{meta['sections_no_docs']} sections with no docs matched, "
          f"{meta['sections_stale']} stale, {meta['sites_not_scheduled']} sites not scheduled "
          f"({'written' if args.write else 'dry run'}, {meta['seconds']}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
