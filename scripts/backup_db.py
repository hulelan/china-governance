#!/usr/bin/env python3
"""Off-droplet backup of the SQLite corpus to DigitalOcean Spaces (S3-compatible).

Why this exists
---------------
The droplet's ``documents.db`` is the SOURCE OF TRUTH (see CLAUDE.md → Architecture).
It exists in exactly one place; ``backups/manifest_*.csv`` are recovery *hints*
(id/url/site_key lists), NOT a copy of the data. This script makes a real,
off-droplet, restorable copy so a droplet loss isn't catastrophic.

What it does (per DB)
---------------------
1. ``VACUUM INTO`` a temp file  — a transactionally CONSISTENT snapshot. A raw
   ``cp`` of a live WAL-mode DB can tear (uncommitted pages live in the -wal
   sidecar); VACUUM INTO writes a clean, defragmented single file.
2. gzip it (Chinese text compresses ~2-2.5x → ~3.8GB DB becomes ~1.5-2GB).
3. Upload to Spaces under ``daily/<db>-YYYYMMDD.db.gz`` (multipart, automatic).
4. On Mondays, server-side-copy that object to ``weekly/`` too.
5. Prune: keep the newest 7 ``daily/`` and newest 4 ``weekly/`` per DB.

Config (all via env — the droplet's .env already sources these)
---------------------------------------------------------------
  SPACES_KEY, SPACES_SECRET   (required; live in .env, chmod 600, gitignored)
  SPACES_REGION               (default: nyc3)
  SPACES_BUCKET               (default: china-governance-backups)

Usage
-----
  python3 scripts/backup_db.py            # back up documents.db + officials.db
  python3 scripts/backup_db.py --dry-run  # VACUUM + gzip + size report, NO upload
  python3 scripts/backup_db.py --db documents.db   # one DB only

Restore (manual)
----------------
  s3cmd/aws/boto3 get  daily/documents-YYYYMMDD.db.gz  ->  gunzip  ->  it's a
  plain SQLite file. Point SQLITE_PATH at it (or replace documents.db + restart).
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Databases worth protecting. officials.db is INCLUDED because it is the hardest
# to reproduce — it's built from a manual Excel seed that isn't in git (see
# CLAUDE.md → officials.db). Missing files are skipped with a warning, not fatal.
DEFAULT_DBS = ["documents.db", "officials.db"]

DAILY_KEEP = 7
WEEKLY_KEEP = 4


def log(msg: str) -> None:
    print(f"[backup_db] {msg}", flush=True)


def make_client():
    """S3 client pointed at the DO Spaces regional endpoint."""
    import boto3  # imported lazily so --help works without the dep

    key = os.environ.get("SPACES_KEY")
    secret = os.environ.get("SPACES_SECRET")
    region = os.environ.get("SPACES_REGION", "nyc3")
    if not key or not secret:
        sys.exit("ERROR: SPACES_KEY / SPACES_SECRET not set (expected in .env).")

    endpoint = f"https://{region}.digitaloceanspaces.com"
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
    )


def snapshot_and_compress(db_path: Path, workdir: Path, date_str: str) -> Path:
    """VACUUM INTO a consistent snapshot, then gzip it. Returns the .gz path."""
    stem = db_path.stem  # "documents" / "officials"
    snap = workdir / f"{stem}-{date_str}.db"
    gz = workdir / f"{stem}-{date_str}.db.gz"

    log(f"{db_path.name}: VACUUM INTO {snap.name} …")
    # Open the live DB read-only; VACUUM INTO produces a clean copy without
    # blocking readers/writers (it takes a brief read lock only).
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=60)
    try:
        con.execute("VACUUM INTO ?", (str(snap),))
    finally:
        con.close()

    raw = snap.stat().st_size
    log(f"{db_path.name}: gzip {snap.name} ({raw/1e9:.2f} GB) …")
    with open(snap, "rb") as f_in, gzip.open(gz, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out, length=8 * 1024 * 1024)
    snap.unlink()  # drop the uncompressed snapshot; keep only the .gz

    comp = gz.stat().st_size
    log(f"{db_path.name}: compressed → {comp/1e9:.2f} GB ({comp/raw*100:.0f}% of raw)")
    return gz


def prune(client, bucket: str, prefix: str, keep: int) -> None:
    """Keep only the newest `keep` objects under `prefix` (names are date-sortable)."""
    resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objs = sorted((o["Key"] for o in resp.get("Contents", [])))
    stale = objs[:-keep] if keep else objs
    for key in stale:
        client.delete_object(Bucket=bucket, Key=key)
        log(f"pruned {key}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Back up SQLite DBs to DO Spaces.")
    ap.add_argument("--db", action="append", help="DB filename(s); repeatable. Default: documents.db + officials.db")
    ap.add_argument("--dry-run", action="store_true", help="VACUUM + gzip locally, skip upload/prune")
    ap.add_argument("--date", help="Override YYYYMMDD (testing); default = today UTC")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    date_str = args.date or now.strftime("%Y%m%d")
    is_monday = now.weekday() == 0
    dbs = args.db or DEFAULT_DBS

    bucket = os.environ.get("SPACES_BUCKET", "china-governance-backups")
    client = None if args.dry_run else make_client()

    rc = 0
    for name in dbs:
        db_path = REPO_ROOT / name
        if not db_path.exists():
            log(f"SKIP {name}: not found at {db_path}")
            continue

        with tempfile.TemporaryDirectory(prefix="dbbackup_") as tmp:
            workdir = Path(tmp)
            try:
                gz = snapshot_and_compress(db_path, workdir, date_str)
            except Exception as e:  # snapshot failure shouldn't abort the other DB
                log(f"ERROR snapshotting {name}: {e}")
                rc = 1
                continue

            if args.dry_run:
                log(f"DRY-RUN: would upload {gz.name} to s3://{bucket}/daily/")
                continue

            daily_key = f"daily/{gz.name}"
            log(f"uploading → s3://{bucket}/{daily_key} …")
            client.upload_file(str(gz), bucket, daily_key)

            if is_monday:
                weekly_key = f"weekly/{gz.name}"
                log(f"Monday: copy → s3://{bucket}/{weekly_key}")
                client.copy_object(Bucket=bucket, Key=weekly_key,
                                   CopySource={"Bucket": bucket, "Key": daily_key})

            stem = db_path.stem
            prune(client, bucket, f"daily/{stem}-", DAILY_KEEP)
            prune(client, bucket, f"weekly/{stem}-", WEEKLY_KEEP)
            log(f"{name}: done.")

    return rc


if __name__ == "__main__":
    sys.exit(main())
