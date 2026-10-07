"""Research-memo reader — serves ``docs/research/*.md`` as HTML.

The memos are the project's analysis layer (see CLAUDE.md "Research layer"):
markdown files that live in the repo, not the DB. This module

* lists them with a curated, sectioned order (``CURATED``; anything not listed
  lands in a trailing "Other" group),
* extracts each memo's title (first ``# `` heading) and blurb (the leading
  italic ``*...*`` paragraph the memos conventionally open with, else the
  first paragraph),
* renders markdown → HTML with ``python-markdown`` (fenced code + GFM-style
  tables + toc ids — the memos are table-heavy),
* rewrites intra-memo links (``[x](name.md)``, `` `name.md` ``, bare
  ``name.md``) to ``/research/<name>`` so the memos cross-link on the site, and
* caches each rendered memo in-process for an hour, keyed by file mtime, so an
  edited file re-renders on the next request without a restart.

Security: a slug must match ``SLUG_RE`` and resolve to a regular file INSIDE
``RESEARCH_DIR`` (checked after ``resolve()``), so ``..``/absolute paths can
never escape the directory.
"""
import re
import time
from pathlib import Path

import markdown

RESEARCH_DIR = (Path(__file__).resolve().parents[2] / "docs" / "research").resolve()
SLUG_RE = re.compile(r"^[a-z0-9-]+$")
CACHE_TTL = 3600  # seconds
_cache: dict = {}

# (section label, [slugs]) — the volume's reading order. Titles come from the
# files themselves; this only fixes grouping and order.
CURATED: list[tuple[str, list[str]]] = [
    ("Start here: the synthesis", ["findings-synthesis"]),
    ("Part I · The citation network", ["citation-network-structure"]),
    ("Part II · Diffusion and fidelity", [
        "diffusion-atlas", "diffusion-fidelity", "fidelity-provincial",
        "fidelity-jiangsu", "daily-tracker-concept",
    ]),
    ("Part III · Centralization, experimentation, coordination", [
        "recentralization-experimentation", "experimentation-wang-yang",
        "site-selection-gdp", "successor-detector", "bottom-up-channel",
        "joint-issuance",
    ]),
    ("Part IV · Sectors and campaigns", [
        "ai-governance-diffusion", "ai-regulatory-web", "ai-plus-fidelity",
        "industrial-policy-targeting", "attention-campaigns",
    ]),
    ("Foundations", ["consumption-diffusion", "research-agenda", "related-literature"]),
    ("Method & QA", [
        "consistency-review", "corpus-lessons", "access-vantage-brief", "residential-proxy-options",
        "us-china-2026-readout-iran",
    ]),
]
OTHER_LABEL = "Other"

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
_INLINE_MD_RE = re.compile(r"(\*\*|__|`|\*|_)")
# Intra-memo link forms, applied in this order so each rewrite is idempotent:
#   1. [text](name.md#frag) / [text](./name.md)   -> [text](/research/name#frag)
#   2. `name.md`                                   -> [`name.md`](/research/name)
#   3. bare name.md (not already inside a link/path) -> [name.md](/research/name)
_MDLINK_RE = re.compile(r"\]\((?:\./)?([a-z0-9-]+)\.md(#[^)\s]*)?\)")
_TICK_RE = re.compile(r"(?<!\[)`([a-z0-9-]+)\.md`(?!\])")
_BARE_RE = re.compile(r"(?<![\w/`\[(.-])([a-z0-9-]+)\.md(?![\w`)\]-])")


def _slug_exists(slug: str) -> bool:
    return bool(SLUG_RE.match(slug)) and (RESEARCH_DIR / f"{slug}.md").is_file()


def resolve_slug(slug: str) -> Path | None:
    """Map a URL slug to a memo path, or None if it is malformed / missing /
    escapes the research directory."""
    if not slug or not SLUG_RE.match(slug):
        return None
    try:
        path = (RESEARCH_DIR / f"{slug}.md").resolve()
    except OSError:
        return None
    if path.parent != RESEARCH_DIR or path.suffix != ".md" or not path.is_file():
        return None
    return path


def _strip_inline(text: str) -> str:
    """Drop emphasis/code markers and collapse whitespace for plain-text use."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)      # [x](y) -> x
    text = _INLINE_MD_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_front(text: str) -> tuple[str, str]:
    """Return (title, blurb) from raw markdown.

    Blurb = the first italic ``*...*`` paragraph after the H1 (the memos'
    convention), else the first non-heading paragraph. Trimmed to ~320 chars.
    """
    m = _H1_RE.search(text)
    title = _strip_inline(m.group(1)) if m else ""
    body = text[m.end():] if m else text
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    blurb = ""
    for p in paras:
        if p.startswith("#") or p == "---":
            continue
        if p.startswith("*") and not p.startswith("**") and p.rstrip().endswith("*"):
            blurb = p
            break
    if not blurb:
        for p in paras:
            if not p.startswith("#") and p != "---" and not p.startswith("|"):
                blurb = p
                break
    blurb = _strip_inline(blurb)
    if len(blurb) > 320:
        cut = blurb[:320]
        blurb = cut[: cut.rfind(" ")] + " …"
    return title, blurb


def _rewrite_links(text: str) -> str:
    def md_link(m):
        slug, frag = m.group(1), m.group(2) or ""
        return f"](/research/{slug}{frag})" if _slug_exists(slug) else m.group(0)

    def tick(m):
        slug = m.group(1)
        return f"[`{slug}.md`](/research/{slug})" if _slug_exists(slug) else m.group(0)

    def bare(m):
        slug = m.group(1)
        return f"[{slug}.md](/research/{slug})" if _slug_exists(slug) else m.group(0)

    text = _MDLINK_RE.sub(md_link, text)
    # Only rewrite inline code/bare forms OUTSIDE fenced code blocks.
    out, in_fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            line = _TICK_RE.sub(tick, line)
            line = _BARE_RE.sub(bare, line)
        out.append(line)
    return "\n".join(out)


def _render(text: str) -> str:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
        output_format="html5",
    )
    body = md.convert(_rewrite_links(text))
    # Wrap tables so a wide one scrolls inside its own box (base.html .table-scroll)
    # instead of widening the page on a phone.
    return body.replace("<table>", '<div class="table-scroll"><table>') \
               .replace("</table>", "</table></div>")


def _load(path: Path) -> dict:
    """Parse + render one memo, cached by (path, mtime) for CACHE_TTL."""
    st = path.stat()
    key = str(path)
    hit = _cache.get(key)
    if hit and hit["mtime"] == st.st_mtime and time.time() - hit["at"] < CACHE_TTL:
        return hit["memo"]
    text = path.read_text(encoding="utf-8", errors="replace")
    title, blurb = _split_front(text)
    slug = path.stem
    memo = {
        "slug": slug,
        "title": title or slug,
        "blurb": blurb,
        "html": _render(text),
        "mtime": st.st_mtime,
        "updated": time.strftime("%Y-%m-%d", time.localtime(st.st_mtime)),
        "words": len(text.split()),
    }
    _cache[key] = {"mtime": st.st_mtime, "at": time.time(), "memo": memo}
    return memo


def _meta(path: Path) -> dict:
    """Title/blurb only (no render) — cheap enough for the index page; cached
    alongside the full render once that has happened."""
    st = path.stat()
    key = str(path)
    hit = _cache.get(key)
    if hit and hit["mtime"] == st.st_mtime:
        m = hit["memo"]
        return {k: m[k] for k in ("slug", "title", "blurb", "updated", "words")}
    text = path.read_text(encoding="utf-8", errors="replace")
    title, blurb = _split_front(text)
    return {
        "slug": path.stem, "title": title or path.stem, "blurb": blurb,
        "updated": time.strftime("%Y-%m-%d", time.localtime(st.st_mtime)),
        "words": len(text.split()),
    }


def list_sections() -> list[dict]:
    """[{label, memos: [meta...]}, ...] in curated order + trailing Other."""
    available = {p.stem: p for p in RESEARCH_DIR.glob("*.md") if SLUG_RE.match(p.stem)}
    sections, seen = [], set()
    for label, slugs in CURATED:
        memos = [_meta(available[s]) for s in slugs if s in available]
        seen.update(slugs)
        if memos:
            sections.append({"label": label, "memos": memos})
    other = [_meta(available[s]) for s in sorted(available) if s not in seen]
    if other:
        sections.append({"label": OTHER_LABEL, "memos": other})
    return sections


def get_memo(slug: str) -> dict | None:
    """Rendered memo + its section label and sibling list, or None (404)."""
    path = resolve_slug(slug)
    if path is None:
        return None
    memo = dict(_load(path))
    section_label, siblings = OTHER_LABEL, []
    for sec in list_sections():
        if any(m["slug"] == slug for m in sec["memos"]):
            section_label, siblings = sec["label"], sec["memos"]
            break
    memo["section"] = section_label
    memo["siblings"] = siblings
    return memo


def memo_count() -> int:
    return sum(len(s["memos"]) for s in list_sections())


