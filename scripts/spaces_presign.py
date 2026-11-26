#!/usr/bin/env python3
"""Print short-lived download URLs for the newest backups in DO Spaces.

Runs ON THE DROPLET (where the Spaces key lives). Its only consumer is
scripts/usb_backup.sh on the Mac, which calls it over ssh and downloads with
curl, so the Spaces secret never has to leave the droplet.

Output: one line per database, tab-separated:  <filename>\t<size_bytes>\t<url>

    set -a; source .env; set +a; python3 scripts/spaces_presign.py
    python3 scripts/spaces_presign.py --expires 21600 --prefix weekly/
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup_db import make_client  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prefix", default="daily/", help="daily/ (default) or weekly/")
    ap.add_argument("--expires", type=int, default=6 * 3600,
                    help="URL lifetime in seconds (default 6h: a 6 GB download on home wifi)")
    ap.add_argument("--db", action="append", default=None,
                    help="stem to include (documents, officials); repeatable; default both")
    args = ap.parse_args()

    bucket = os.environ.get("SPACES_BUCKET", "china-governance-backups")
    client = make_client()
    objs = client.list_objects_v2(Bucket=bucket, Prefix=args.prefix).get("Contents", [])
    stems = args.db or ["documents", "officials"]
    missing = []
    for stem in stems:
        mine = sorted((o for o in objs if Path(o["Key"]).name.startswith(f"{stem}-")),
                      key=lambda o: o["Key"])
        if not mine:
            missing.append(stem)
            continue
        newest = mine[-1]
        url = client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": newest["Key"]},
            ExpiresIn=args.expires)
        print(f"{Path(newest['Key']).name}\t{newest['Size']}\t{url}")
    if missing:
        sys.exit(f"ERROR: no backup under {args.prefix} for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
