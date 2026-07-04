"""China Law Translate crawler.

Pulls posts from chinalawtranslate.com via the WordPress REST API and stores
them as standalone documents under site_key="chinalawtranslate".

Known quirk: CloudFlare returns 502 on per_page=100 requests that include the
`content` field. Use per_page=20 and browser-shaped headers (this crawler
already does). Don't bump per_page back up to save round-trips — it 502s.

Each post's structure:
  - title.rendered           = Chinese title of the underlying law
  - slug                     = English-friendly handle (e.g. "facial-recognition-draft")
  - content.rendered         = HTML body that begins with a <pre> metadata block:
        【颁布时间】 date
        【标题】     title
        【发文号】   doc number
        【颁布单位】 issuing organ(s)
        【法规来源】 source URL  ← KEY for matching to native corpus docs
    Followed by the actual body — sometimes Chinese, sometimes English, often
    Chinese only (CLT posts the source first; English translation may come
    later as an edit).

Strategy:
  1. Store every CLT post as a doc (site_key=chinalawtranslate).
  2. Use slug-derived English title + Chinese title from title.rendered.
  3. Capture the source URL into `relation` so a follow-up matcher can link
     CLT posts to native docs in our corpus by URL.
  4. Compute language ratio so the matcher can later distinguish posts with
     real English translations from Chinese-only posts.

Usage:
    python3 -m crawlers.chinalawtranslate                     # full crawl
    python3 -m crawlers.chinalawtranslate --limit 5           # 5 per category
    python3 -m crawlers.chinalawtranslate --dry-run
    python3 -m crawlers.chinalawtranslate --category internet
"""

from __future__ import annotations

import argparse
import html
import re
import time
import urllib.parse

from .base import (
    fetch_json,
    init_db,
    log,
    store_document,
    store_site,
)

SITE_KEY = "chinalawtranslate"
BASE_URL = "https://www.chinalawtranslate.com"
API = f"{BASE_URL}/wp-json/wp/v2/posts"
ID_OFFSET = 900_000_000  # avoid collision with native doc IDs (max ~12.7M)
PER_PAGE = 20  # CloudFlare 502s on per_page=100 with full content

# CloudFlare needs browser-shaped headers — urllib defaults get blocked.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# WP category IDs to harvest. Discovered via /wp-json/wp/v2/categories.
CATEGORIES: dict[str, int] = {
    "internet": 1357,            # Internet/cyber regulations
    "spc": 59,                   # Supreme People's Court
    "admin": 10,                 # Administrative/regulatory
    "criminal": 3,               # Criminal Law
    "legislative-drafts": 1001,  # Drafts for comment
    "npc": 248,                  # NPC laws
    "spp2": 246,                 # Supreme People's Procuratorate
    "civil": 4,                  # Civil law
    "policydoc": 44,             # Policy papers
    "mps": 247,                  # Ministry of Public Security
    "scs": 1952,                 # Social Credit
    "gwy": 250,                  # State Council
    "party": 340,                # Party regulations
    "environment": 822,          # Environment
    "moj": 707,                  # Ministry of Justice
    "ip": 6,                     # IP Law
    "laboremploy": 153,          # Labor
    "moh": 249,                  # Ministry of Health
    "supervision": 2167,         # Supervision
    "religion": 1951,
    "disability": 607,
    "lawnews": 5,                # Legal news (often translated explainers)
}

CATEGORY_TO_TYPE: dict[str, str] = {
    "internet": "regulation",
    "legislative-drafts": "draft_for_comment",
    "policydoc": "policy_issuance",
    "scs": "regulation",
    "criminal": "law",
    "civil": "law",
    "npc": "law",
    "ip": "law",
    "laboremploy": "law",
    "religion": "regulation",
    "supervision": "regulation",
    "environment": "regulation",
    "moj": "regulation",
    "mps": "regulation",
    "moh": "regulation",
    "spc": "judicial_interpretation",
    "spp2": "judicial_interpretation",
    "admin": "administrative_measures",
    "gwy": "policy_issuance",
    "party": "party_regulation",
    "lawnews": "explainer",
}

DOC_NUM_RE = re.compile(
    r"([一-鿿]{1,8}〔\d{4}〕第?\d+号|"
    r"[一-鿿]{1,8}\[\d{4}\]\d+号|"
    r"中华人民共和国主席令第\d+号|"
    r"第\s*\d+\s*号)"
)

META_KEYS = [
    "颁布时间", "标题", "发文号", "颁布单位", "法规来源",
    "失效时间", "意见时期", "来源", "时效",
]


def strip_html(html_text: str) -> str:
    """Strip HTML tags and decode entities, preserving paragraph structure."""
    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.I)
    text = re.sub(r"</(?:p|div|li|h[1-6]|tr|pre)>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def slug_to_title(slug: str) -> str:
    """Turn 'facial-recognition-draft' into 'Facial Recognition Draft'.

    Returns "" for unusable slugs (URL-encoded Chinese, mostly digits, etc.) so
    the caller falls back to the Chinese title.
    """
    # URL-encoded Chinese? Skip and let caller fall back
    decoded = urllib.parse.unquote(slug)
    if any("一" <= c <= "鿿" for c in decoded):
        return ""
    parts = slug.replace("-", " ").replace("_", " ").split()
    # Filter out trailing duplicate counters like "post-2" → just "post"
    if parts and parts[-1].isdigit() and len(parts) > 1:
        parts = parts[:-1]
    # Skip if slug is mostly digits (numeric IDs)
    letter_count = sum(1 for w in parts for c in w if c.isalpha())
    digit_count = sum(1 for w in parts for c in w if c.isdigit())
    if letter_count < 3 or letter_count <= digit_count:
        return ""
    # Skip "concatenated" slugs (single long word with no hyphens) — these
    # produce ugly titles like "Partycoronavirusresponse"
    if len(parts) == 1 and len(parts[0]) > 14:
        return ""
    small = {"of", "and", "the", "in", "on", "for", "to", "vs", "a", "an"}
    out = []
    for i, w in enumerate(parts):
        if i > 0 and w.lower() in small:
            out.append(w.lower())
        else:
            out.append(w[0].upper() + w[1:].lower() if w else w)
    return " ".join(out)


def parse_metadata_block(content_html: str) -> dict[str, str]:
    """Extract 【key】value pairs from the post body.

    CLT uses two layouts:
      - Newer (~2024+): a single <pre> block with all metadata
      - Older: inline <p><b>【KEY】<a href="URL">URL</a></b></p> paragraphs

    We just search the first 4KB of content for each key, regardless of layout.
    """
    head = content_html[:4000]
    meta: dict[str, str] = {}
    for key in META_KEYS:
        # Capture text after 【KEY】 up to the next 【 or close of paragraph
        m = re.search(
            rf"【\s*{key}\s*】(.*?)(?=【|</p>|</pre>|\n\n|<br|\Z)",
            head,
            re.DOTALL,
        )
        if not m:
            continue
        raw = m.group(1)
        # If the value has an <a href=...>, prefer that URL
        link_m = re.search(r'href=["\']([^"\']+)["\']', raw)
        if link_m and key in {"法规来源", "来源"}:
            meta[key] = link_m.group(1).strip()
            continue
        # Otherwise strip tags and clean up
        v = re.sub(r"<[^>]+>", "", raw)
        v = html.unescape(v).strip().strip(":：").strip()
        if v:
            meta[key] = v
    return meta


def strip_metadata_and_links(content_html: str) -> str:
    """Remove metadata (【KEY】 paragraphs or <pre> block) and CLT's related-link cards."""
    # Drop a <pre> block at the start
    out = re.sub(r"<pre[^>]*>.*?</pre>", "", content_html, count=1, flags=re.DOTALL)
    # Drop the inline metadata paragraphs (<p>...【KEY】...</p>)
    keys_alt = "|".join(re.escape(k) for k in META_KEYS)
    out = re.sub(
        rf"<p[^>]*>[^<]*?(?:<[^>]+>[^<]*?)*【\s*(?:{keys_alt})\s*】.*?</p>",
        "",
        out,
        flags=re.DOTALL,
    )
    # CLT's "vlp-link-container" wraps related-article cards — match the whole div
    out = re.sub(
        r'<div\s+class="vlp-link-container[^"]*".*?vlp-layout-zone-main.*?</div></div></div>(?:</a>)?(?:</div>)?',
        "",
        out,
        flags=re.DOTALL,
    )
    # Trailing rating widgets / footers
    out = re.sub(r"Click to rate this post!.*", "", out, flags=re.DOTALL)
    return out


def language_ratio(text: str) -> float:
    """Fraction of letters that are Chinese (vs ASCII letters). 0=all English, 1=all Chinese."""
    chinese = sum(1 for c in text if "一" <= c <= "鿿")
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    total = chinese + ascii_letters
    return chinese / total if total else 0.0


def fetch_category_posts(cat_id: int, slug: str) -> list[dict]:
    """Fetch all posts in a WP category via paginated REST API."""
    posts: list[dict] = []
    page = 1
    while True:
        url = (
            f"{API}?categories={cat_id}&per_page={PER_PAGE}&page={page}"
            "&_fields=id,slug,link,title,content,excerpt,date,modified,categories,tags"
        )
        try:
            batch = fetch_json(url, timeout=60, headers=HEADERS)
        except Exception as e:
            if (
                "HTTP Error 400" in str(e)
                or "rest_post_invalid_page_number" in str(e)
            ):
                break
            log.warning(f"  [{slug}] page {page} failed: {e}")
            break
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < PER_PAGE:
            break
        page += 1
        time.sleep(0.5)
    return posts


def build_doc(post: dict, slug_cat: str) -> dict | None:
    """Convert a WP post to our doc dict. Returns None for stubs."""
    wp_id = post["id"]
    permalink = post["link"]

    cn_title = html.unescape(strip_html(post["title"]["rendered"]))
    en_title_from_slug = slug_to_title(post["slug"])
    # Display title: prefer English-derived; fall back to Chinese
    title = en_title_from_slug or cn_title or f"CLT post {wp_id}"

    content_html = post["content"]["rendered"]
    meta = parse_metadata_block(content_html)
    body_html = strip_metadata_and_links(content_html)
    body_text = strip_html(body_html)

    if len(body_text) < 80:
        return None  # stub or broken

    excerpt_text = strip_html(post.get("excerpt", {}).get("rendered", ""))
    summary = excerpt_text[:600] if excerpt_text else body_text[:400]

    date_str = post["date"][:10]  # YYYY-MM-DD from WP
    # Prefer the metadata 颁布时间 if present (the actual law-issued date)
    if meta.get("颁布时间"):
        m = re.search(r"(\d{4})[-./年]\s*(\d{1,2})[-./月]\s*(\d{1,2})", meta["颁布时间"])
        if m:
            date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    date_int = int(date_str.replace("-", ""))

    doc_num = meta.get("发文号", "") or extract_doc_number(body_text)
    publisher = meta.get("颁布单位", "") or "China Law Translate"
    cn_source_url = meta.get("法规来源") or meta.get("来源", "")
    cn_title_meta = meta.get("标题", "") or cn_title

    lang_ratio = language_ratio(body_text)

    return {
        "id": ID_OFFSET + wp_id,
        "title": title,
        "url": permalink,
        "post_url": permalink,
        "abstract": summary,
        "body_text_cn": body_text,
        "publisher": publisher,
        "date_written": date_int,
        "date_published": date_str,
        "display_publish_time": date_int,
        "document_number": doc_num,
        "identifier": cn_title_meta,
        "classify_genre_name": slug_cat,
        # Encode source URL + lang ratio in `relation` so the matcher can find them.
        # Format: "cn_source=<URL>;lang_ratio=<0.0-1.0>"
        "relation": f"cn_source={cn_source_url};lang_ratio={lang_ratio:.2f}",
        "raw_html_path": "",
        # carried only for the post-insert UPDATE; not stored by store_document
        "_title_en": en_title_from_slug,
        "_summary_en": summary if lang_ratio < 0.6 else "",
        "_doc_type": CATEGORY_TO_TYPE.get(slug_cat, ""),
    }


def extract_doc_number(text: str) -> str:
    m = DOC_NUM_RE.search(text)
    return m.group(1) if m else ""


def crawl(
    limit_per_cat: int | None = None,
    only_category: str | None = None,
    dry_run: bool = False,
) -> int:
    conn = init_db()
    if not dry_run:
        store_site(
            conn,
            SITE_KEY,
            {
                "name": "China Law Translate",
                "base_url": BASE_URL,
                "admin_level": "research",
            },
        )

    cats = (
        {only_category: CATEGORIES[only_category]}
        if only_category
        else CATEGORIES
    )

    seen: set[int] = set()
    inserted = 0
    cn_only = 0
    real_translations = 0

    for slug, cat_id in cats.items():
        log.info(f"Fetching category {slug} (id={cat_id})…")
        try:
            posts = fetch_category_posts(cat_id, slug)
        except Exception as e:
            log.error(f"  Failed: {e}")
            continue
        if limit_per_cat:
            posts = posts[:limit_per_cat]
        log.info(f"  → {len(posts)} posts")

        for p in posts:
            if p["id"] in seen:
                continue
            seen.add(p["id"])

            doc = build_doc(p, slug)
            if not doc:
                continue

            if "lang_ratio=" in doc["relation"]:
                lr = float(doc["relation"].split("lang_ratio=")[1])
                if lr >= 0.6:
                    cn_only += 1
                else:
                    real_translations += 1

            if dry_run:
                tag = "EN" if doc["_summary_en"] else "CN"
                cn_url = doc["relation"].split(";")[0].replace("cn_source=", "")
                log.info(
                    f"  [DRY {tag}] {doc['title'][:60]} | "
                    f"{doc['document_number'] or '-'} | "
                    f"src={cn_url[:60] or '-'}"
                )
                continue

            # Strip our private fields before passing to store_document
            store_doc = {k: v for k, v in doc.items() if not k.startswith("_")}
            store_document(conn, SITE_KEY, store_doc)
            conn.execute(
                """UPDATE documents
                   SET title_en = ?, summary_en = ?, doc_type = ?
                   WHERE id = ?""",
                (
                    doc["_title_en"],
                    doc["_summary_en"],
                    doc["_doc_type"],
                    doc["id"],
                ),
            )
            inserted += 1

        if not dry_run:
            conn.commit()
        time.sleep(0.4)

    if not dry_run:
        conn.commit()
    log.info(
        f"Done. {inserted} docs stored from {len(seen)} unique posts. "
        f"Real translations: {real_translations}, CN-only: {cn_only}."
    )
    return inserted


def main() -> None:
    p = argparse.ArgumentParser(description="China Law Translate crawler")
    p.add_argument("--limit", type=int, help="Limit posts per category (for testing)")
    p.add_argument(
        "--category", choices=sorted(CATEGORIES.keys()),
        help="Crawl only this category",
    )
    p.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = p.parse_args()
    crawl(
        limit_per_cat=args.limit,
        only_category=args.category,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
