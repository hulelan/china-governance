#!/usr/bin/env python3
"""Flatten Claude Code session JSONL into plain-text transcripts a model can read.

This is the piece the Managed Agents "dreaming" cookbook gets for free from
`client.beta.sessions.retrieve` and we have to supply ourselves: our sessions are
Claude Code sessions stored as local JSONL under ~/.claude/projects/<slug>/, not
API sessions, so nothing on the API side can export them.

Three things make this more than a jq one-liner.

1. COMPRESSION IS THE WHOLE JOB. The current china-governance session is 163 MB;
   the cookbook's 11 example transcripts were 283 KB total (~26 KB each). Tool
   RESULTS are essentially all of the bulk — a `cat` of a statute body, a 40-row
   SQL dump, a 277 KB fetched page — and almost none of the lesson. So results
   are capped head+tail (`--result-chars`) while prose and tool INPUTS, which are
   where the reasoning and the commands live, are kept nearly whole.

2. A SHAPE PATTERN CANNOT FIND A SECRET THAT IS NOT WEARING ITS LABEL. Measured
   on the first run of this script: 113 `sk-` keys were redacted by pattern and
   the Railway postgres password still leaked, because the session that leaked it
   was AUDITING it — `git log -S "<the password>"`, a bare high-entropy string
   with no `postgresql://` prefix and no `password=` in front of it. So the
   patterns below are the fallback, and the primary defence is a DENYLIST of the
   literal values read at runtime out of the files on this machine that hold them
   (`--secrets-from`, defaulting to the project .env and the Claude settings
   files). This is CLAUDE.md's "when a heuristic and an identifier disagree, the
   identifier wins": the shape is the heuristic, the value on disk is the
   identifier. It matters because a dream WRITES memory files that later sessions
   load eagerly, so a key copied into memory is a key in every future context.

   Redaction runs on the RAW text, before clipping. A 32-char password that
   straddles a `… [N chars omitted] …` boundary matches neither half, so clipping
   first would defeat the denylist on exactly the longest secrets.

3. SUBAGENT TURNS ARE THE INTERESTING PART AND THEY LIVE IN TWO PLACES. This
   project has 2 top-level session files and 245 separate subagents/*.jsonl, plus
   `isSidechain: true` turns inline in the parent. CLAUDE.md records the exact
   failure that makes them worth distilling — an anchor string copied "from a
   subagent report, not from the file" — so a transcript set that silently drops
   them would omit the population the lessons come from.

Output is one .txt per session, plus a manifest.json the dream step reads.

    python3 scripts/rnd/dream/export_transcripts.py --list
    python3 scripts/rnd/dream/export_transcripts.py --out /tmp/dream/transcripts
    python3 scripts/rnd/dream/export_transcripts.py --audit /tmp/dream/transcripts
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
DEFAULT_PROJECT = "-Users-lelan-Desktop-claude-code-china-governance"
REPO = Path(__file__).resolve().parents[3]

# Files on this machine that hold real credentials. Their VALUES become literal
# denylist entries; nothing is ever printed.
SECRET_SOURCES = [
    REPO / ".env",
    REPO / ".claude" / "settings.local.json",
    REPO / ".claude" / "settings.json",
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".claude.json",
]

# Fallback shape patterns, for a secret that was pasted into a prompt once and
# never stored in a file the parser below can read. Each keeps the NAME and drops
# the SECRET, so a distilled memory can still say "the Spaces key lives in the
# droplet .env".
_SHAPES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-<REDACTED>"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)(\s*[=:]\s*)[\"\']?[A-Za-z0-9_\-/+.]{12,}[\"\']?"),
     r"\1\2<REDACTED>"),
    (re.compile(r"(?i)\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^:\s]+:[^@\s]+@"), r"\1://<REDACTED>@"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-.]{16,}"), "Bearer <REDACTED>"),
    (re.compile(r"\$apr1\$[A-Za-z0-9./$]+"), "$apr1$<REDACTED>"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "ghp_<REDACTED>"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "<REDACTED PRIVATE KEY>"),
]

# PARSE, DO NOT GUESS. The first version of this harvested any >=12-char
# high-entropy token out of the credential files and it failed in BOTH
# directions at once, which is why the rule is now structural:
#   * it MISSED the live Railway postgres password, because that password is all
#     letters and the filter required a digit — the "rule validated where it does
#     not fire" shape CLAUDE.md names twice already;
#   * and an entropy floor cannot replace the digit test, because at >=3.5 it
#     keeps 1,069 entries of which the longest are hyphenated feature-flag names
#     out of ~/.claude.json (high per-character entropy precisely because they
#     are long and diverse).
# A credential in a config file always sits in one of three structures, so read
# the structure instead: NAME=VALUE, "NAME": "VALUE", and scheme://user:PW@host.
_SECRET_NAME = re.compile(
    r"(?i)(^|_)(key|token|secret|password|passwd|credential|cred|dsn|auth|api)s?($|_)"
    r"|(api_?key|database_url|access_key|private_key)")
_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
# Matches both a plain NAME="v" and the backslash-escaped form that appears when
# a shell command is stored inside a JSON permission string.
_INLINE_ASSIGN = re.compile(r"([A-Za-z_][A-Za-z0-9_]{2,})\s*=\s*\\?[\"\']([^\"\'\\]{6,})\\?[\"\']")
_URL_CRED = re.compile(r"[a-z][a-z0-9+.\-]*://[^:/\s\"\']+:([^@\s\"\']{4,})@")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _plausible(v: str) -> bool:
    """A credential VALUE, not an identifier or a path.

    UUIDs are excluded by name: 18 of the first run's 144 denylist entries were
    session UUIDs out of ~/.claude.json, and one of them appeared in 241 of 246
    transcripts — because the session id is in every transcript header. A value
    present in nearly every transcript is an identifier, not a secret.
    """
    v = v.strip().strip("\"'")
    if len(v) < 8 or len(v) > 4096:
        return False
    if _UUID.match(v) or v.startswith(("/", "./", "~", "http://", "https://")):
        return False
    return not re.search(r"\s", v)


def _harvest(text: str) -> set[str]:
    found: set[str] = set()
    for m in _URL_CRED.finditer(text):
        found.add(m.group(1))
    for name, val in _INLINE_ASSIGN.findall(text):
        if _SECRET_NAME.search(name):
            found.add(val)
    for line in text.splitlines():
        m = _ENV_LINE.match(line)
        if m and _SECRET_NAME.search(m.group(1)):
            found.add(m.group(2))
    # A JSON config nests credentials under a telling key name.
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        obj = None

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and _SECRET_NAME.search(str(k)):
                    found.add(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return {v.strip().strip("\"'") for v in found if _plausible(v)}


def load_known_secrets(paths: list[Path]) -> list[str]:
    """Literal credential values read out of the files that hold them."""
    found: set[str] = set()
    for p in paths:
        try:
            found |= _harvest(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    # Longest first, so a URL that contains a shorter token is masked whole.
    return sorted(found, key=len, reverse=True)


def make_redactor(known: list[str]):
    def redact(s: str) -> str:
        for secret in known:
            if secret in s:
                s = s.replace(secret, "<REDACTED>")
        for pat, repl in _SHAPES:
            s = pat.sub(repl, s)
        return s
    return redact


def clip(s: str, limit: int) -> str:
    """Head+tail clip. Both ends matter: a command's shape is at the head, its
    exit status and error are at the tail, and a middle-only truncation loses the
    half that says whether the thing worked."""
    if limit <= 0 or len(s) <= limit:
        return s
    head = limit * 2 // 3
    tail = limit - head
    return f"{s[:head]}\n… [{len(s) - limit:,} chars omitted] …\n{s[-tail:]}"


def _blocks(content) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def render_turn(d: dict, redact, result_chars: int, input_chars: int, keep_thinking: bool) -> str | None:
    msg = d.get("message")
    if not isinstance(msg, dict):
        return None
    role = msg.get("role")
    if role not in ("user", "assistant") or d.get("isMeta"):
        return None

    tag = {"user": "USER", "assistant": "CLAUDE"}[role]
    if d.get("isSidechain"):
        tag = f"SUBAGENT/{tag}"
    if d.get("isCompactSummary"):
        tag = "COMPACT-SUMMARY"

    out: list[str] = []
    for b in _blocks(msg.get("content")):
        t = b.get("type")
        # redact() always runs on the RAW string, then clip(). Reversing these
        # lets a long secret straddle the omission marker and survive.
        if t == "text":
            txt = redact((b.get("text") or "").strip())
            if txt:
                out.append(txt)
        elif t == "thinking" and keep_thinking:
            txt = redact((b.get("thinking") or "").strip())
            if txt:
                out.append(f"[thinking] {clip(txt, result_chars)}")
        elif t == "tool_use":
            args = redact(json.dumps(b.get("input") or {}, ensure_ascii=False, sort_keys=True))
            out.append(f"[tool: {b.get('name')}] {clip(args, input_chars)}")
        elif t == "tool_result":
            c = b.get("content")
            if isinstance(c, list):
                c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
            body = clip(redact(str(c or "").strip()), result_chars)
            if body:
                out.append(f"[result{' ERROR' if b.get('is_error') else ''}] {body}")
    if not out:
        return None
    return f"=== {tag} ===\n" + "\n".join(out)


def export_one(src: Path, dst: Path, redact, args) -> dict:
    turns = kept = bad = 0
    with dst.open("w", encoding="utf-8") as fh:
        fh.write(f"# transcript: {src.name}\n# source: {src}\n\n")
        for line in src.open(encoding="utf-8", errors="replace"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            turns += 1
            block = render_turn(d, redact, args.result_chars, args.input_chars, args.thinking)
            if block:
                kept += 1
                fh.write(block + "\n\n")
    return {"file": dst.name, "source": str(src), "turns": turns,
            "rendered": kept, "unparseable": bad, "bytes": dst.stat().st_size}


def discover(project: str, include_subagents: bool) -> list[Path]:
    root = PROJECTS / project
    # sorted() so a rerun emits the same names, which is what lets an
    # incremental dream skip what it already read.
    files = sorted(root.glob("*.jsonl"))
    if include_subagents:
        files += sorted(root.glob("*/subagents/**/*.jsonl"))
    return files


def audit(out: Path, known: list[str]) -> int:
    """Grep finished exports for every known secret. Exits non-zero on a hit, and
    names the file but never the value."""
    hits = 0
    for f in sorted(out.glob("*.txt")):
        text = f.read_text(encoding="utf-8", errors="replace")
        for i, secret in enumerate(known):
            if secret in text:
                print(f"LEAK  {f.name}  (denylist entry #{i}, {len(secret)} chars)")
                hits += 1
    print(f"\naudit: {len(list(out.glob('*.txt')))} files x {len(known)} known secrets -> "
          f"{hits} leak(s)")
    return 1 if hits else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=DEFAULT_PROJECT,
                    help="dir under ~/.claude/projects (substring match allowed)")
    ap.add_argument("--out", default="/tmp/dream/transcripts")
    ap.add_argument("--result-chars", type=int, default=1200,
                    help="cap per tool_result (head+tail). The compression knob.")
    ap.add_argument("--input-chars", type=int, default=2000, help="cap per tool_use input")
    ap.add_argument("--thinking", action="store_true", help="keep thinking blocks (large)")
    ap.add_argument("--no-subagents", dest="subagents", action="store_false", default=True)
    ap.add_argument("--min-bytes", type=int, default=2000,
                    help="drop exports under this size (stub sessions carry no lesson)")
    ap.add_argument("--secrets-from", action="append", default=None,
                    help="extra file whose literal values are added to the denylist")
    ap.add_argument("--list", action="store_true", help="show what would be exported, write nothing")
    ap.add_argument("--audit", metavar="DIR", help="re-grep an existing export dir for known secrets")
    args = ap.parse_args()

    sources = list(SECRET_SOURCES) + [Path(p) for p in (args.secrets_from or [])]
    known = load_known_secrets(sources)
    print(f"denylist: {len(known)} literal values from "
          f"{sum(1 for p in sources if p.exists())}/{len(sources)} credential files", flush=True)

    if args.audit:
        sys.exit(audit(Path(args.audit), known))

    if not (PROJECTS / args.project).is_dir():
        hits = [p.name for p in PROJECTS.iterdir() if p.is_dir() and args.project in p.name]
        if len(hits) != 1:
            sys.exit(f"--project {args.project!r} matched {len(hits)} dirs: {hits}")
        args.project = hits[0]

    files = discover(args.project, args.subagents)
    if args.list:
        for f in files:
            print(f"{f.stat().st_size:>12,}  {f.relative_to(PROJECTS / args.project)}")
        print(f"\n{len(files)} files, {sum(f.stat().st_size for f in files):,} bytes")
        return

    redact = make_redactor(known)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest, dropped = [], 0
    for src in files:
        # Name collisions are real: every session dir has subagents/<uuid>.jsonl.
        rel = src.relative_to(PROJECTS / args.project)
        name = str(rel).replace("/", "__").replace(".jsonl", ".txt")
        rec = export_one(src, out / name, redact, args)
        if rec["bytes"] < args.min_bytes:
            (out / name).unlink()
            dropped += 1
            continue
        manifest.append(rec)
        print(f"{rec['bytes']:>10,}  {rec['rendered']:>5}/{rec['turns']:<6} turns  {name}", flush=True)

    total = sum(r["bytes"] for r in manifest)
    raw = sum(f.stat().st_size for f in files)
    (out / "manifest.json").write_text(json.dumps(
        {"project": args.project, "transcripts": manifest,
         "result_chars": args.result_chars, "input_chars": args.input_chars,
         "thinking": args.thinking, "denylist_size": len(known)}, indent=1), encoding="utf-8")
    print(f"\n{len(manifest)} transcripts ({dropped} dropped under --min-bytes)")
    print(f"{raw:,} bytes in -> {total:,} bytes out  ({raw / max(total, 1):.0f}x compression)")
    sys.exit(audit(out, known))


if __name__ == "__main__":
    main()
