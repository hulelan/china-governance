#!/usr/bin/env python3
"""Re-run every mechanically checkable claim in CLAUDE.md and memory/ against reality.

This is the half of "dreaming" the cookbook can only approximate. A cookbook
analyzer verifies a memory claim against a TRANSCRIPT — i.e. against another
model's account of what happened. Here most claims name a file, a symbol, a flag,
a commit or a database object, and those can be checked against the repo, git and
the schema, which is strictly stronger evidence. CLAUDE.md's own memory rule asks
for exactly this: "If one names a file, function, or flag, verify it still exists
before recommending it."

THREE BUCKETS, NEVER TWO. Every claim lands in OK, STALE or UNCHECKED, and the
three are reported separately. That is not fastidiousness: the local documents.db
is a 122 KB stub with 8 tables and 0 rows that predates doc_identity,
tracker_weekly and doc_inbound, so a schema check run against it would report
`doc_identity.instrument_id` as STALE when it exists on the droplet. Reporting a
missing verifier as a failed verification is the "rule validated on the
population where it does NOT fire" shape from CLAUDE.md, and it would make the
report worse than no report. DB claims are UNCHECKED unless --db names a database
that actually carries the corpus schema.

What is NOT attempted: the ~70 six-digit COUNTS ("135,480 documents", "42,942
citations") and the prose date claims. The mapping from such a sentence to the
query that would settle it is not inferable from the sentence, and a guessed
query is how you get a confident wrong answer. They are listed for a human, with
the line number, under "needs a bespoke probe".

    python3 scripts/rnd/dream/verify_memory.py
    python3 scripts/rnd/dream/verify_memory.py --db documents.db
    python3 scripts/rnd/dream/verify_memory.py --out docs/working/memory-staleness.md
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MEMORY = Path.home() / ".claude" / "projects" / "-Users-lelan-Desktop-claude-code-china-governance" / "memory"

OK, STALE, UNCHECKED = "ok", "stale", "unchecked"

_CODE = re.compile(r"`([^`\n]{2,120})`")
_PATHLIKE = re.compile(r"^[\w./\-]+\.(py|sh|md|csv|tsv|yaml|yml|json|jsonl|html|db|sql|txt)$")
_FILE_SYMBOL = re.compile(r"^([\w./\-]+\.(?:py|sh))[:.](\w+)(?:\(\))?$")
_FILE_LINE = re.compile(r"^[\w./\-]+\.(?:py|sh|md):\d+$")
_FLAG = re.compile(r"^--[a-z][a-z0-9\-]{2,}$")
_CONST = re.compile(r"^[A-Z][A-Z0-9_]{4,}$")
_FUNC = re.compile(r"^_?[a-z][a-z0-9_]{3,}\(\)$")
# A commit sha must contain a hex LETTER. 10832248 and 12694197 are corpus
# document ids and were being reported as missing commits.
_SHA = re.compile(r"^(?=[0-9a-f]{7,40}$)[0-9a-f]*[a-f][0-9a-f]*$")
_DB_COL = re.compile(r"^([a-z][a-z0-9_]{3,})\.([a-z][a-z0-9_]{2,})$")
_DB_TABLE_SIG = re.compile(r"^([a-z][a-z0-9_]{3,})\(([a-z][a-z0-9_, ]*)\)$")
_BIGNUM = re.compile(r"\b\d{1,3},\d{3}(?:,\d{3})*\b")

# Tokens that look like one of the shapes above but are not a claim about this
# repo: other people's tools, SQL keywords, and the droplet's own filesystem.
_NOT_OURS = {
    "sqlite_master", "wal_checkpoint", "busy_timeout", "doc_search", "doc_search_seg",
    "PRAGMA", "SELECT", "UPDATE", "INSERT", "GROUP", "ORDER", "WHERE", "COUNT",
    "COALESCE", "LENGTH", "RANDOM", "EXPLAIN", "AUTOMATIC", "COVERING", "LEFT",
    "MATCH", "LIKE", "TRUNCATE", "PASSIVE", "VACUUM",
}


def _repo_grep(needle: str, globs: tuple[str, ...] = ()) -> bool:
    """Fixed-string grep over tracked files. git grep so .gitignored scratch and
    the 4 GB DBs are never scanned."""
    cmd = ["git", "-C", str(REPO), "grep", "-qF", "--", needle]
    if globs:
        cmd += ["--"] + [f"*{g}" for g in globs]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def _git_has(sha: str) -> bool:
    return subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"],
                          capture_output=True).returncode == 0


def load_db_schema(db: Path | None) -> dict[str, set[str]] | None:
    """{table: {columns}}, or None when no database carries the corpus schema.

    The sentinel matters more than the data: returning {} for a stub DB would
    make every table read as missing.
    """
    if db is None or not db.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
        # A corpus DB has the tables the memo claims are there. A pre-2026-10
        # stub has `documents` and `citations` and nothing else, and cannot
        # adjudicate anything.
        if "doc_identity" not in tables:
            con.close()
            return None
        schema = {t: {r[1] for r in con.execute(f'PRAGMA table_info("{t}")')} for t in tables}
        con.close()
        return schema
    except sqlite3.Error:
        return None


_SKIP_DIRS = {".git", ".claude", "node_modules", "__pycache__", ".venv", "raw_html"}


def build_index() -> dict[str, list[str]]:
    """basename -> repo-relative paths. Built once.

    Needed because CLAUDE.md names a file by BASENAME in prose — "see
    `trim_body_tails.py`" — which is correct writing, not a stale claim. The first
    version demanded every basename resolve from the repo root and reported 40 of
    its 56 failures that way: a selection rule that is almost all false positives
    is not selecting. Worktrees under .claude/ are skipped because a stale copy of
    web/static/robots.txt there made the real one look misplaced.
    """
    idx: dict[str, list[str]] = {}
    for p in REPO.rglob("*"):
        if not p.is_file() or _SKIP_DIRS & set(p.relative_to(REPO).parts):
            continue
        idx.setdefault(p.name, []).append(str(p.relative_to(REPO)))
    return idx


def classify(tok: str, schema, idx: dict[str, list[str]]) -> tuple[str, str, str]:
    """-> (verdict, kind, detail). One token, one verdict."""
    if tok in _NOT_OURS or tok.upper() in _NOT_OURS:
        return UNCHECKED, "keyword", "SQL/third-party name"

    # BEFORE _FILE_SYMBOL: `\w+` matches digits, so crawlers/base.py:718 was read
    # as the symbol `718` and reported as a missing file.
    if _FILE_LINE.match(tok):
        return UNCHECKED, "file:line", "a line number cannot be verified by existence"

    if m := _FILE_SYMBOL.match(tok):
        path, sym = m.groups()
        target = REPO / path
        if not target.exists():
            hits = idx.get(Path(path).name, [])
            if not hits:
                return STALE, "file:symbol", f"{path} not in the repo"
            target = REPO / hits[0]
        body = target.read_text(encoding="utf-8", errors="replace")
        return (OK if sym in body else STALE), "file:symbol", f"{sym} in {target.name}"

    if _PATHLIKE.match(tok):
        if tok.startswith(("/", "~")):
            return UNCHECKED, "path", "absolute/droplet path"
        if (REPO / tok).exists():
            return OK, "path", tok
        # memory/ lives outside the repo, in ~/.claude/projects/<slug>/memory.
        if tok.startswith("memory/") and (MEMORY / tok[len("memory/"):]).exists():
            return OK, "path", f"{tok} (in the memory store)"
        if tok.endswith(".db"):
            return UNCHECKED, "path", "gitignored data file"
        hits = idx.get(Path(tok).name, [])
        if "/" not in tok:
            # A bare basename is prose, not a path claim: present anywhere is present.
            if len(hits) == 1:
                return OK, "basename", hits[0]
            if hits:
                return OK, "basename", f"{len(hits)} copies, e.g. {hits[0]}"
            return STALE, "basename", f"no file named {tok} in the repo"
        if hits:
            return STALE, "path", f"not at {tok}; now at {hits[0]}"
        return STALE, "path", f"{tok} not in the repo"

    if _SHA.match(tok):
        return (OK if _git_has(tok) else STALE), "commit", tok

    if _FLAG.match(tok):
        return (OK if _repo_grep(tok) else STALE), "flag", tok

    if _CONST.match(tok):
        return (OK if _repo_grep(tok) else STALE), "constant", tok

    if _FUNC.match(tok):
        name = tok[:-2]
        if _repo_grep(f"def {name}"):
            return OK, "function", f"def {name}"
        # bm25() and fetchall() are SQLite's and Python's. Absent entirely means
        # it was never ours, which is not a stale claim about our code.
        return UNCHECKED, "function", f"{name} is not defined in this repo"

    if m := _DB_TABLE_SIG.match(tok):
        table, cols = m.group(1), [c.strip() for c in m.group(2).split(",") if c.strip()]
        if schema is None:
            return UNCHECKED, "db-table", f"{table}: no corpus DB available"
        if table not in schema:
            return STALE, "db-table", f"table {table} absent"
        missing = [c for c in cols if c not in schema[table]]
        return (STALE if missing else OK), "db-table", f"{table}: missing {missing}" if missing else table

    if m := _DB_COL.match(tok):
        table, col = m.groups()
        if schema is None:
            return UNCHECKED, "db-column", f"{table}.{col}: no corpus DB available"
        if table not in schema:
            return UNCHECKED, "db-column", f"{table} is not a table (may be prose)"
        return (OK if col in schema[table] else STALE), "db-column", f"{table}.{col}"

    return UNCHECKED, "other", "no checker for this shape"


def sources() -> list[Path]:
    files = [REPO / "CLAUDE.md"]
    if MEMORY.is_dir():
        files += sorted(MEMORY.glob("*.md"))
    return [f for f in files if f.exists()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=None,
                    help="corpus DB for schema claims (droplet copy, or omit to leave them UNCHECKED)")
    ap.add_argument("--out", type=Path, default=None, help="write the markdown report here")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    args = ap.parse_args()

    schema = load_db_schema(args.db)
    idx = build_index()
    print(f"schema source: {args.db if schema else 'NONE — db claims will be UNCHECKED'}", flush=True)

    results: list[tuple[str, str, str, str, Path, int]] = []
    seen: dict[str, tuple] = {}
    numbers: list[tuple[Path, int, str]] = []

    for f in sources():
        for lineno, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for tok in _CODE.findall(line):
                tok = tok.strip()
                if " " in tok and not _DB_TABLE_SIG.match(tok):
                    continue
                if tok not in seen:
                    seen[tok] = classify(tok, schema, idx)
                verdict, kind, detail = seen[tok]
                results.append((verdict, kind, tok, detail, f, lineno))
            if f.name == "CLAUDE.md":
                for n in _BIGNUM.findall(line):
                    numbers.append((f, lineno, n))

    by = defaultdict(list)
    for r in results:
        by[r[0]].append(r)
    uniq = {v: len({r[2] for r in rs}) for v, rs in by.items()}

    lines = [f"# Memory staleness report",
             "",
             f"Sources: {', '.join(f.name for f in sources())}",
             f"Schema: {'`' + str(args.db) + '`' if schema else '**none** — DB claims UNCHECKED'}",
             "",
             f"- **{uniq.get(OK, 0)}** distinct claims verified present",
             f"- **{uniq.get(STALE, 0)}** distinct claims FAILED verification",
             f"- **{uniq.get(UNCHECKED, 0)}** distinct claims have no checker",
             f"- **{len({n for _, _, n in numbers})}** distinct large numbers need a bespoke probe",
             ""]

    if by[STALE]:
        lines += ["## Failed verification", ""]
        shown = set()
        for verdict, kind, tok, detail, f, lineno in sorted(by[STALE], key=lambda r: (r[1], r[2])):
            if tok in shown:
                continue
            shown.add(tok)
            lines.append(f"- `{tok}` — *{kind}* — {detail} — {f.name}:{lineno}")
        lines.append("")

    lines += ["## Needs a bespoke probe (not attempted)", "",
              "The sentence does not determine the query, so these are listed, not judged.", ""]
    for f, lineno, n in numbers[:40]:
        lines.append(f"- `{n}` — {f.name}:{lineno}")
    if len(numbers) > 40:
        lines.append(f"- … and {len(numbers) - 40} more")

    report = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
    if not args.quiet:
        print()
        print(report)
    print(f"GATE: {'FAIL' if by[STALE] else 'PASS'}  "
          f"({uniq.get(OK,0)} ok / {uniq.get(STALE,0)} stale / {uniq.get(UNCHECKED,0)} unchecked)")
    sys.exit(1 if by[STALE] else 0)


if __name__ == "__main__":
    main()
