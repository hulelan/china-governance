"""Extract and persist cross-document citations.

Scans all documents with body text, extracts formal (文号) and named (《》)
references, resolves them against the corpus, and populates the citations table.

Usage:
    python3 scripts/extract_citations.py              # Extract and save
    python3 scripts/extract_citations.py --dry-run    # Show stats without saving
    python3 scripts/extract_citations.py --force      # Drop and rebuild
"""

import argparse
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
from analyze import (
    REF_PATTERN, get_admin_level,
    NAMED_REF_PATTERN, is_policy_document, classify_named_ref_level,
    build_known_abbrevs, canonicalize_formal_ref,
)

DB_PATH = Path(__file__).parents[3] / "documents.db"

# Normalize site-level "department" to "municipal" for 4-level hierarchy
LEVEL_NORMALIZE = {"department": "municipal"}

_NG = 4  # n-gram size for the title substring index

# Resolver-recall upgrade (2026-08): the old exact-substring matcher missed docs
# we DO hold whenever the cited reference and the stored title differed only in
# punctuation / brackets / whitespace / the 中华人民共和国 prefix (a ~14% false-missing
# rate on top-cited refs). Normalizing BOTH sides before matching recovers those.
_TITLE_STRIP = re.compile(
    r'[\s《》〈〉「」『』【】〔〕\[\]()（）“”‘’"\'、，,。．\.·・:：;；／/　]')
_PRC_PREFIX = "中华人民共和国"


def _norm_title(s):
    """Fold punctuation/bracket/whitespace variants + the PRC prefix so that e.g.
    '城市、镇控制性详细规划编制审批办法' and '城市镇...办法', or '《中华人民共和国网络安全法》'
    and '网络安全法', normalize to the same key."""
    s = _TITLE_STRIP.sub('', s or '')
    if s.startswith(_PRC_PREFIX):
        s = s[len(_PRC_PREFIX):]
    return s


_DOCNUM_STRIP = re.compile(r'[\s〔〕\[\]()（）【】　]')


def _norm_docnum(s):
    """Normalize a 文号 for matching: unify bracket styles (〔〕[]（）) + strip spaces,
    so a cited ref matches a stored document_number that used a different bracket."""
    return _DOCNUM_STRIP.sub('', s or '')


# --- Resolver-recall upgrade (2026-08, round 2) -----------------------------
# Diagnosis of the ~49% unresolved edges (see docs/ / the sample study) found that
# the vast majority are genuine COVERAGE GAPS (the cited doc isn't in the corpus:
# other-city municipal docs, historical/central docs we never crawled, foreign
# laws, non-document refs like "中央经济工作会议"). But a fixable minority miss docs
# we DO hold because of two representable variations:
#   (1) 文号 that differ only by full-width digits or stray non-〔〕 punctuation, and
#   (2) a named/LLM ref shaped "《CoreTitle》（文号）" or "…发布的《CoreTitle》" whose stored
#       doc is titled "<agency>印发《CoreTitle》的通知" / "<文号> CoreTitle" — reordered,
#       so neither string substring-contains the other, yet the bare 《》 CORE is a
#       clean substring of the stored title.
# These helpers recover exactly those, conservatively (length-gated to avoid
# matching a short generic core to the wrong doc).

_FULLWIDTH_DIGITS = {ord('０') + i: chr(ord('0') + i) for i in range(10)}


def _agg_docnum(s):
    """Aggressive 文号 key: map full-width digits to ASCII and keep only CJK, ASCII
    digits and 号 — folds every remaining punctuation/space/bracket variant."""
    s = (s or "").translate(_FULLWIDTH_DIGITS)
    return re.sub(r'[^一-鿿0-9号]', '', s)


_CORE_DOCNUM = re.compile(
    r'([一-鿿]{1,10})'
    r'[〔〈《（‘〚\[(]'
    r'((?:19|20)\d{2})'
    r'[〕〉》）’〛\])]'
    r'\s*(\d+)\s*号'
)


def _core_docnum(s):
    """Extract the canonical issuer+〔year〕+num号 core from a noisy ref (last match),
    dropping any prepended agency/sentence fragment the canonicalizer missed."""
    ms = list(_CORE_DOCNUM.finditer(s or ""))
    if not ms:
        return None
    m = ms[-1]
    return f"{m.group(1)}{m.group(2)}{m.group(3)}号"


# --- Resolver-recall upgrade (2026-08, round 3) -----------------------------
# Two more representable formal-ref misses, both proven on the live unresolved set:
#   (1) ZERO-PADDING. A heavily-cited ref like 财库〔2022〕4号 (demand 130) is held in
#       the corpus as 财库〔2022〕004号. Every existing docnum key keeps the sequence
#       number verbatim, so 4号 != 004号 and the ref never resolves. _core_zs_key
#       strips the number's leading zeros so the two collide.
#   (2) EMPTY document_number (75% of docs). A formal 文号 citation can't reach a held
#       doc via the docnum indices when that doc stored no document_number — but the
#       文号 usually lives in the TITLE. We index title-embedded 文号 (zero-strip core)
#       so such refs resolve. To keep precision we prefer the "own-number position"
#       (right after a 发文字号/文号 label, or trailing in （…） at the end) over a mere
#       mid-title mention of some OTHER doc's number.
# Both are added as FINAL tiers of resolve_formal that fire ONLY after the whole
# existing chain misses (existing indices untouched), so the currently-resolved
# edge set stays a strict subset — no regression by construction.

def _core_zs_key(s):
    """Zero-padding-insensitive 文号 key: like _core_docnum but strips leading zeros
    from the sequence number, so 财库〔2022〕4号 and 财库〔2022〕004号 (same document,
    padded differently) map to one key. Returns None when no 文号 core is present."""
    ms = list(_CORE_DOCNUM.finditer(s or ""))
    if not ms:
        return None
    m = ms[-1]
    num = m.group(3).lstrip("0") or "0"
    return f"{m.group(1)}{m.group(2)}{num}号"


# 发文字号/文号/字号 label immediately preceding a title-embedded 文号 → it is the
# document's OWN number (not a reference to a different doc).
_OWN_NUM_MARK = re.compile(r'(?:发文字号|文\s*号|字\s*号)[：:\s]{0,3}$')


def _title_docnums(title):
    """Yield (zs_key, is_own_number) for each 文号 core found in a title. is_own_number
    is True when the 文号 sits in an own-number position — right after a 发文字号/文号
    label, or trailing at the very end inside （…） — which distinguishes a doc's own
    number from an in-title mention of some OTHER doc's number (e.g. '…（X号批次）')."""
    for m in _CORE_DOCNUM.finditer(title or ""):
        k = _core_zs_key(m.group(0))
        if not k:
            continue
        pre = title[max(0, m.start() - 8):m.start()]
        tail = title[m.end():]
        is_own = bool(_OWN_NUM_MARK.search(pre)) or all(
            ch in ')）]】〕 ' for ch in tail)
        yield k, is_own


# 《...》 inner title (>=8 chars) and an END-anchored trailing qualifier group.
# The trailing set is deliberately limited to qualifiers that do NOT change a
# document's identity (试行/暂行/征求意见稿/…); we intentionally do NOT strip a bare
# trailing (YYYY)/(YYYY年版) because that would cross-link different editions, nor a
# MID-title parenthetical (text after it) because that changes what the doc is.
_INNER_TITLE = re.compile(r'《([^《》]{8,})》')
_TRAIL_QUAL = re.compile(
    r'[（(【\[〔](?:试行|暂行|修订|修正|草案|送审稿|征求意见稿|征求意见|讨论稿)[)）】\]〕]$')
_CORE_MIN_LEN = 10  # normalized length floor for a title core to be trustworthy


def _title_cores(raw_ref):
    """Alternate title strings to try when the whole ref doesn't resolve: the text
    inside 《》, and the ref with an end-anchored qualifier group removed."""
    out = []
    for m in _INNER_TITLE.finditer(raw_ref):
        out.append(m.group(1))
    s = raw_ref.strip()
    s2 = _TRAIL_QUAL.sub('', s)
    if s2 != s and s2:
        out.append(s2)
    return out


class TitleMatcher:
    """Indexed fuzzy title resolver — replaces an O(docs x titles) per-ref scan.

    resolve(name, min_len) returns a doc id for some stored title t with
    len(t) >= min_len and (t in name OR name in t), else None — the same
    RESOLVED/UNRESOLVED partition as the old brute-force loop (parity-tested),
    but O(len(name)^2) via substring generation + an n-gram inverted index
    instead of scanning every title. Drops the full rebuild from ~2h to minutes.
    Tie-break differs (prefers the longest 't in name' match — strictly better).
    """

    def __init__(self, title_to_doc):
        # Index on NORMALIZED titles (punctuation/prefix folded). setdefault keeps the
        # first id when two titles normalize identically (near-duplicate docs).
        self.exact = {}  # norm-title -> id
        for t, v in title_to_doc.items():
            nt = _norm_title(t)
            if nt:
                self.exact.setdefault(nt, v[0])
        self.titles = list(self.exact.keys())
        self.index = {}  # gram -> set of title indices
        for idx, t in enumerate(self.titles):
            for g in self._grams(t):
                self.index.setdefault(g, set()).add(idx)

    @staticmethod
    def _grams(s):
        if len(s) < _NG:
            return {s}
        return {s[i:i + _NG] for i in range(len(s) - _NG + 1)}

    def _containing(self, name):
        """Titles that contain `name` (n-gram intersection, then verify)."""
        posting = None
        for g in self._grams(name):
            s = self.index.get(g)
            if not s:
                return ()
            posting = set(s) if posting is None else (posting & s)
            if not posting:
                return ()
        return (self.titles[i] for i in posting if name in self.titles[i])

    def resolve(self, name, min_len):
        name = _norm_title(name)  # match on the normalized form (both sides folded)
        L = len(name)
        # (a) a stored title is a substring of the cited name (longest-first; L==exact)
        if L >= min_len:
            for length in range(L, min_len - 1, -1):
                for i in range(L - length + 1):
                    did = self.exact.get(name[i:i + length])
                    if did is not None:
                        return did
        # (b) the cited name is a substring of a longer stored title (floor is on title)
        for t in self._containing(name):
            if len(t) >= min_len:
                return self.exact[t]
        return None

    def resolve_ref(self, raw_ref, min_len=8):
        """resolve() on the whole ref, then (only on a miss) on its title cores —
        the bare 《》 inner title / an end-anchored-qualifier-stripped form — so a
        "《Core》（文号）" ref still links to a stored "<agency>印发《Core》的通知"
        (reordered; the core is a clean substring of the stored title)."""
        did = self.resolve(raw_ref, min_len)
        if did is not None:
            return did
        base = _norm_title(raw_ref)
        for core in _title_cores(raw_ref):
            nc = _norm_title(core)
            if len(nc) >= _CORE_MIN_LEN and nc != base:
                did = self.resolve(core, max(min_len, _CORE_MIN_LEN))
                if did is not None:
                    return did
        return None


def get_source_level(doc_number: str, site_admin_level: str) -> str:
    """Determine admin level for a source document."""
    if doc_number:
        level = get_admin_level(doc_number)
        if level != "unknown":
            return level
    # Fall back to site's admin level
    return LEVEL_NORMALIZE.get(site_admin_level, site_admin_level) or "unknown"


def extract_all(conn: sqlite3.Connection, dry_run: bool = False):
    """Extract citations from all documents with body text."""
    t0 = time.time()

    # --- Build lookup tables ---

    # document_number -> doc_id (for formal ref resolution)
    docnum_to_id = {}
    docnum_agg = {}   # aggressive key (full-width digits + all punctuation folded)
    docnum_core = {}  # canonical issuer+year+num号 core key
    docnum_core_zs = {}  # zero-padding-insensitive core key (round-3)
    for row in conn.execute(
        "SELECT id, document_number FROM documents WHERE document_number <> ''"
    ).fetchall():
        did, dn = row[0], row[1 + 0]
        docnum_to_id[dn] = did  # raw docnum -> id
        nd = _norm_docnum(dn)   # + bracket-normalized key (don't clobber a raw match)
        if nd and nd != dn:
            docnum_to_id.setdefault(nd, did)
        ad = _agg_docnum(dn)
        if ad:
            docnum_agg.setdefault(ad, did)
        cd = _core_docnum(dn)
        if cd:
            docnum_core.setdefault(_agg_docnum(cd), did)
        zk = _core_zs_key(dn)
        if zk:
            docnum_core_zs.setdefault(zk, did)

    # title-embedded 文号 index (round-3): key -> id, own-number positions winning
    # over mere in-title mentions. Populated after title_to_doc is built, below.
    title_docnum_zs = {}

    def resolve_formal(ref):
        """docnum resolution: raw -> bracket-norm -> aggressive -> canonical core, then
        (round-3 FINAL tiers, only on a miss) zero-strip core over document_number, then
        the zero-strip core embedded in a stored TITLE. The round-3 tiers fire strictly
        after the existing chain, so already-resolved refs are unchanged."""
        did = (docnum_to_id.get(ref)
               or docnum_to_id.get(_norm_docnum(ref))
               or docnum_agg.get(_agg_docnum(ref))
               or docnum_core.get(_agg_docnum(_core_docnum(ref) or "")))
        if did:
            return did
        zk = _core_zs_key(ref)
        if zk:
            return docnum_core_zs.get(zk) or title_docnum_zs.get(zk)
        return None

    # title -> (id, site_key) for named ref resolution (only titles >= 8 chars (was 10 — excluded 9-char provincial 条例))
    title_to_doc = {}
    _title_dn_strong = {}  # own-number-position 文号 in a title
    _title_dn_weak = {}    # mid-title mention of a 文号 (fallback only)
    for row in conn.execute(
        "SELECT id, title, site_key FROM documents WHERE LENGTH(title) >= 8"
    ).fetchall():
        title_to_doc[row[1]] = (row[0], row[2])
        for zk, is_own in _title_docnums(row[1]):
            (_title_dn_strong if is_own else _title_dn_weak).setdefault(zk, row[0])
    # own-number positions win over mere in-title mentions of another doc's number
    title_docnum_zs.update(_title_dn_weak)
    title_docnum_zs.update(_title_dn_strong)

    # site_key -> admin_level
    site_levels = {}
    for row in conn.execute("SELECT site_key, admin_level FROM sites").fetchall():
        site_levels[row[0]] = row[1] or "unknown"

    matcher = TitleMatcher(title_to_doc)  # indexed fuzzy title resolver (fast)
    print(f"Lookup tables: {len(docnum_to_id)} doc numbers, {len(title_to_doc)} titles, {len(site_levels)} sites")

    # --- Fetch all documents with body text OR references_json ---
    docs = conn.execute(
        """SELECT id, site_key, title, document_number, body_text_cn, references_json
           FROM documents
           WHERE (body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 20)
              OR (references_json IS NOT NULL AND references_json != '' AND references_json != '[]')"""
    ).fetchall()
    print(f"Documents with body text or references: {len(docs)}")

    # --- Pre-scan: build the issuer-abbreviation vocabulary for 文号 normalization ---
    # (held doc numbers are authoritative; short standalone ref prefixes fill gaps)
    raw_formal = []
    for _d in docs:
        raw_formal.extend(REF_PATTERN.findall(_d[4] or ""))
    known_abbrevs = build_known_abbrevs(docnum_to_id.keys(), raw_formal)
    print(f"Known issuer abbreviations: {len(known_abbrevs)} (from {len(docnum_to_id)} held numbers + short refs)")

    # --- Extract citations ---
    citations = []  # list of (source_id, target_ref, target_id, citation_type, source_level, target_level)
    stats = Counter()
    missing_formal_refs = set()  # distinct unresolved 文号 (for dedup-impact metric)

    for doc_id, site_key, title, doc_number, body, refs_json in docs:
        source_level = get_source_level(doc_number, site_levels.get(site_key, ""))
        body = body or ""

        # Formal 文号 citations (normalized: strip lead-ins + prepended agency names)
        formal_refs = REF_PATTERN.findall(body)
        seen_formal = set()
        for ref in formal_refs:
            ref = canonicalize_formal_ref(ref, known_abbrevs)
            if ref == doc_number:  # skip self-reference
                continue
            if ref in seen_formal:
                continue
            seen_formal.add(ref)

            target_id = resolve_formal(ref)
            target_level = get_admin_level(ref)
            citations.append((doc_id, ref, target_id, "formal", source_level, target_level))
            stats["formal"] += 1
            if target_id:
                stats["formal_resolved"] += 1
            else:
                missing_formal_refs.add(ref)

        # Named 《》 citations
        named_refs = NAMED_REF_PATTERN.findall(body)
        seen_named = set()
        for name in named_refs:
            if not is_policy_document(name):
                continue
            if name in title or title in name:  # skip self-reference
                continue
            if name in seen_named:
                continue
            seen_named.add(name)

            # Try to resolve to corpus (indexed fuzzy title match + title cores)
            target_id = matcher.resolve_ref(name, 8)

            target_level = classify_named_ref_level(name)
            citations.append((doc_id, name, target_id, "named", source_level, target_level))
            stats["named"] += 1
            if target_id:
                stats["named_resolved"] += 1

        # LLM-extracted references (from references_json column)
        if refs_json and refs_json not in ('', '[]'):
            try:
                import json as _json
                llm_refs = _json.loads(refs_json)
            except (ValueError, TypeError):
                llm_refs = []
            for ref_name in llm_refs:
                if not isinstance(ref_name, str) or len(ref_name) < 4:
                    continue
                # Self-reference check: skip only if ref is essentially the same as the title.
                # Don't skip when the ref is PART of the title (common for explainers:
                # "一图读懂《X》" references X, which is a substring of the title but NOT self)
                if ref_name == title or title == ref_name:
                    continue
                # Skip if already found by regex
                if ref_name in seen_formal or ref_name in seen_named:
                    continue

                # Try to resolve to corpus by title match (indexed + cores), then doc number
                target_id = matcher.resolve_ref(ref_name, 8)
                if not target_id:
                    target_id = resolve_formal(ref_name)

                target_level = classify_named_ref_level(ref_name)
                citations.append((doc_id, ref_name, target_id, "llm", source_level, target_level))
                stats["llm"] += 1
                if target_id:
                    stats["llm_resolved"] += 1

    elapsed = time.time() - t0

    # --- Report ---
    print(f"\nExtracted {len(citations)} citations in {elapsed:.1f}s:")
    print(f"  Formal (文号): {stats['formal']} ({stats['formal_resolved']} resolved, "
          f"{len(missing_formal_refs)} distinct missing after normalization)")
    print(f"  Named  (《》): {stats['named']} ({stats['named_resolved']} resolved)")
    print(f"  LLM  (refs):   {stats['llm']} ({stats['llm_resolved']} resolved)")
    total_resolved = stats['formal_resolved'] + stats['named_resolved'] + stats['llm_resolved']
    print(f"  Total resolved: {total_resolved}/{len(citations)}")

    # Level breakdown
    level_counts = Counter()
    cross_level = 0
    for _, _, _, _, src_lvl, tgt_lvl in citations:
        level_counts[f"{src_lvl} → {tgt_lvl}"] += 1
        if src_lvl != tgt_lvl and src_lvl != "unknown" and tgt_lvl != "unknown":
            cross_level += 1

    print(f"\n  Cross-level citations: {cross_level}")
    print(f"\n  Citation flow:")
    for flow, count in sorted(level_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"    {flow}: {count}")

    if dry_run:
        print("\n[DRY RUN — nothing saved]")
        return

    # --- Save (with retry for busy DB) ---
    for save_attempt in range(5):
        try:
            conn.execute("DELETE FROM citations")
            break
        except sqlite3.OperationalError:
            wait = (save_attempt + 1) * 10
            print(f"  DB locked, retrying in {wait}s (attempt {save_attempt + 1}/5)...")
            time.sleep(wait)
    else:
        print("ERROR: Could not acquire write lock after 5 attempts")
        return
    conn.executemany(
        """INSERT OR REPLACE INTO citations
           (source_id, target_ref, target_id, citation_type, source_level, target_level)
           VALUES (?, ?, ?, ?, ?, ?)""",
        citations,
    )
    conn.commit()
    final_count = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    print(f"\nSaved {final_count} citations to database")


def main():
    parser = argparse.ArgumentParser(description="Extract and persist cross-document citations")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without saving")
    parser.add_argument("--force", action="store_true", help="Drop and recreate citations table first")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = None  # use tuples for speed

    if args.force:
        conn.execute("DROP TABLE IF EXISTS citations")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_ref TEXT NOT NULL,
                target_id INTEGER,
                citation_type TEXT NOT NULL,
                source_level TEXT NOT NULL,
                target_level TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES documents(id),
                FOREIGN KEY (target_id) REFERENCES documents(id),
                UNIQUE(source_id, target_ref, citation_type)
            );
            CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
            CREATE INDEX IF NOT EXISTS idx_citations_target_id ON citations(target_id);
            CREATE INDEX IF NOT EXISTS idx_citations_target_ref ON citations(target_ref);
            CREATE INDEX IF NOT EXISTS idx_citations_levels ON citations(source_level, target_level);
        """)
        print("Rebuilt citations table")

    extract_all(conn, dry_run=args.dry_run)
    conn.close()


if __name__ == "__main__":
    main()
