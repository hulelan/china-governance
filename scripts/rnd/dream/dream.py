#!/usr/bin/env python3
"""Dream: distil Claude Code session transcripts into the long-term memory store.

A local adaptation of the Managed Agents "dreaming" cookbook. The cookbook runs
on the Claude API — predefined agents, a memory_store, a no-network cloud
environment — and its input step (`client.beta.sessions.retrieve`) can only
export API sessions. Ours are Claude Code sessions on disk, so the engine here is
headless `claude -p` and the input comes from export_transcripts.py.

ONE DELIBERATE DEPARTURE FROM THE COOKBOOK: ANALYZERS DO NOT WRITE TO MEMORY.

The cookbook has every analyzer edit the shared memory directory concurrently and
spends part of its prompt managing the race ("re-read files before editing, make
targeted edits rather than rewrites"). This project already knows where that
leads — CLAUDE.md's SQLite rule is "writer count is not the limit, transaction
HOLD TIME is; do not start a second writer". So here each analyzer writes only
its own proposals/<name>.md, and a single organizer is the one writer to the
store. The race is removed rather than managed, and a bad analyzer damages one
proposal file instead of the store.

The analyzer never sees the repository either: it runs with cwd in the work
directory, no Bash and no network, and is handed a COPY of MEMORY.md rather than
the store. That keeps the 34,000-token CLAUDE.md out of 246 separate agent
contexts, and it means a transcript cannot talk an analyzer into editing code.

Incremental by default: state.json records (source, size, mtime) per analyzed
transcript, so a nightly run only reads what changed.

    python3 scripts/rnd/dream/dream.py --dry-run
    python3 scripts/rnd/dream/dream.py --limit 8            # a bounded first pass
    python3 scripts/rnd/dream/dream.py --analyze-only
    python3 scripts/rnd/dream/dream.py --organize-only
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MEMORY = (Path.home() / ".claude" / "projects"
          / "-Users-lelan-Desktop-claude-code-china-governance" / "memory")

ANALYZER_TOOLS = "Read,Write,Glob,Grep"
ORGANIZER_TOOLS = "Read,Write,Edit,Glob,Grep"
# Named explicitly rather than relying on the allowlist: a transcript is hostile
# input, and Bash or WebFetch in an analyzer would make a prompt injection
# actionable instead of inert.
DENY = "Bash,WebFetch,WebSearch,Agent,Task,NotebookEdit"


def run_claude(prompt: str, cwd: Path, tools: str, model: str,
               add_dirs: tuple[Path, ...] = (), timeout: int = 900) -> dict:
    cmd = ["claude", "-p", prompt,
           "--allowed-tools", tools,
           "--disallowed-tools", DENY,
           "--permission-mode", "acceptEdits",
           "--output-format", "json",
           "--model", model]
    for d in add_dirs:
        cmd += ["--add-dir", str(d)]
    try:
        # No `timeout` binary on macOS (CLAUDE.md records this), so the timeout
        # is subprocess's, not the shell's.
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"is_error": True, "subtype": "timeout", "result": f"timed out after {timeout}s"}
    if p.returncode != 0:
        return {"is_error": True, "subtype": f"exit{p.returncode}",
                "result": (p.stderr or p.stdout or "")[-400:]}
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"is_error": True, "subtype": "unparseable", "result": p.stdout[-400:]}


def load_state(f: Path) -> dict:
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"analyzed": {}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, default=Path("/tmp/dream"),
                    help="work dir holding transcripts/, proposals/ and state.json")
    ap.add_argument("--memory", type=Path, default=MEMORY)
    ap.add_argument("--limit", type=int, default=0, help="analyze at most N transcripts (0 = all)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--model-analyzer", default="claude-haiku-5-5")
    ap.add_argument("--model-organizer", default="claude-sonnet-5-5")
    ap.add_argument("--max-transcript-bytes", type=int, default=400_000,
                    help="skip (loudly) anything larger; re-export it with a tighter --result-chars")
    ap.add_argument("--staleness", type=Path, default=None,
                    help="report from verify_memory.py --out; the organizer applies it")
    ap.add_argument("--force", action="store_true", help="re-analyze transcripts already in state.json")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--organize-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, spend nothing")
    args = ap.parse_args()

    work = args.work
    tdir, pdir = work / "transcripts", work / "proposals"
    if not tdir.is_dir():
        sys.exit(f"no transcripts at {tdir} — run export_transcripts.py --out {tdir} first")
    pdir.mkdir(parents=True, exist_ok=True)
    state_f = work / "state.json"
    state = load_state(state_f)

    analyzer_prompt = (HERE / "prompts" / "analyzer.md").read_text(encoding="utf-8")
    organizer_prompt = (HERE / "prompts" / "organizer.md").read_text(encoding="utf-8")

    def stage(src: Path | None, name: str) -> None:
        """Copy an input into the work dir, unless it already IS that file —
        verify_memory.py --out commonly writes straight into the work dir."""
        dst = work / name
        if src and src.exists() and not (dst.exists() and src.samefile(dst)):
            shutil.copy2(src, dst)

    # The analyzer is handed a read-only COPY of the whole store, never the store
    # itself. The first version staged only MEMORY.md, and the analyzers caught
    # it: every verification line came back "(inferred) — the memory body was not
    # visible here, so the match rests on its title only". Verification against a
    # one-line index can only ever be inferred, which defeats the point. A copy
    # keeps the single-writer property while making MEASURED verification possible.
    snap = work / "memory_snapshot"
    if args.memory.is_dir():
        shutil.rmtree(snap, ignore_errors=True)
        shutil.copytree(args.memory, snap)
    stage(args.staleness, "staleness.md")

    todo, skipped_big, skipped_done = [], [], 0
    for t in sorted(tdir.glob("*.txt")):
        st = t.stat()
        key = t.name
        if st.st_size > args.max_transcript_bytes:
            skipped_big.append((t.name, st.st_size))
            continue
        prev = state["analyzed"].get(key)
        if prev and not args.force and prev.get("size") == st.st_size:
            skipped_done += 1
            continue
        todo.append(t)
    if args.limit:
        todo = todo[:args.limit]

    print(f"transcripts: {len(todo)} to analyze, {skipped_done} already done, "
          f"{len(skipped_big)} over --max-transcript-bytes")
    for n, b in skipped_big:
        print(f"  SKIPPED {b:>12,}  {n}")
    if skipped_big:
        print("  -> re-export these with a tighter --result-chars to include them")

    if args.dry_run:
        print(f"\nwould run {len(todo)} x {args.model_analyzer} analyzers "
              f"(concurrency {args.concurrency}), then 1 x {args.model_organizer} organizer")
        print(f"work dir: {work}\nmemory:   {args.memory}")
        return

    cost = 0.0
    failures: list[tuple[str, str]] = []

    if not args.organize_only:
        def analyze(t: Path) -> tuple[Path, dict]:
            out = f"proposals/{t.stem}.md"
            prompt = (f"{analyzer_prompt}\n\n---\n\n"
                      f"Transcript to analyze: `transcripts/{t.name}`\n"
                      f"Current memory store (read-only copy): `memory_snapshot/` "
                      f"— read MEMORY.md there for the index, then the individual "
                      f"files you need to verify a claim against its BODY\n"
                      f"Write your proposal to: `{out}`\n")
            return t, run_claude(prompt, work, ANALYZER_TOOLS, args.model_analyzer)

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(analyze, t): t for t in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                t, res = fut.result()
                cost += res.get("total_cost_usd") or 0.0
                if res.get("is_error"):
                    failures.append((t.name, f"{res.get('subtype')}: {str(res.get('result'))[:120]}"))
                    mark = "FAIL"
                else:
                    state["analyzed"][t.name] = {"size": t.stat().st_size, "at": time.time()}
                    mark = "ok  "
                print(f"[{i:>3}/{len(todo)}] {mark} ${cost:7.4f}  {t.name[:64]}", flush=True)
                state_f.write_text(json.dumps(state, indent=1), encoding="utf-8")
        print(f"\nanalyze: {len(todo) - len(failures)} ok, {len(failures)} failed, "
              f"{time.time() - t0:.0f}s, ${cost:.4f}")
        for n, why in failures:
            print(f"  FAIL {n}: {why}")

    if not args.analyze_only:
        props = sorted(pdir.glob("*.md"))
        if not props:
            sys.exit("no proposals to organize")
        prompt = (f"{organizer_prompt}\n\n---\n\n"
                  f"Proposals (read-only): `proposals/` — {len(props)} files\n"
                  f"Memory directory (read-write): `{args.memory}`\n"
                  + (f"Staleness report: `staleness.md`\n" if (work / 'staleness.md').exists()
                     else "Staleness report: none supplied this run.\n"))
        print(f"\norganize: 1 x {args.model_organizer} over {len(props)} proposals", flush=True)
        res = run_claude(prompt, work, ORGANIZER_TOOLS, args.model_organizer,
                         add_dirs=(args.memory,), timeout=3600)
        cost += res.get("total_cost_usd") or 0.0
        if res.get("is_error"):
            print(f"ORGANIZER FAILED: {res.get('subtype')}: {str(res.get('result'))[:400]}")
            failures.append(("organizer", str(res.get("subtype"))))
        else:
            print(f"organizer said: {str(res.get('result'))[:800]}")

    print(f"\ntotal ${cost:.4f}")
    print(f"GATE: {'FAIL' if failures else 'PASS'} ({len(failures)} failure(s))")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
