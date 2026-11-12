"""Speaker type of a document, shared by the global-discourse scans.

The definitions now live in web/services/discourse_vocab.py (one source of truth,
also used by scripts/build_discourse_weekly.py and /discourse); this module
re-exports them so the memo's scripts keep working unchanged."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from web.services.discourse_vocab import (  # noqa: E402,F401
    BIZ, COMM, PARTY, RES, STATE, C, PH, speaker, strip_chrome)
