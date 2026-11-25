"""Publish-keyed page cache, shared across uvicorn workers.

Why this exists (measured 2026-11-25): every heavy page (/dashboard 13s, /chain 8s,
/tracker 4s, /collections/oil 5.6s, /lens 9s) was fast only on a SECOND hit. The old
caches were per-process dicts with a 1h TTL, so each of the 2 workers paid the cold
cost separately, again every hour, and again after every nightly restart. But the
data these pages show only changes when the nightly publishes, so a TTL buys
nothing: the right key is "which publish is this".

Design (deliberately the simplest thing that works across processes):

* **Generation** = the mtime of a stamp file (`.publish_stamp` in the repo root,
  touched by daily_sync.sh Phase 3 right before the restart). If the stamp does not
  exist (a dev checkout), the DB file's mtime stands in. Changing the stamp
  invalidates everything at once; `touch .publish_stamp` is the manual lever.
* **Storage** = one pickle file per entry under `<cache_dir>/<generation>/`, written
  to a temp name and `os.replace`d (atomic), so two workers can race on the same
  key without either ever reading a torn file. Older generation directories are
  pruned when a new generation is first seen.
* **Memory layer** = a small per-process LRU in front of the disk, so a hot key is a
  dict lookup, not a file read.
* **Safety net** = an entry older than MAX_AGE is a miss even within one generation,
  so a nightly that never stamps (lock held by a >24h classifier drain) cannot pin a
  page forever.
* **Best effort**: any disk error (unwritable dir, corrupt or unpicklable value) is a
  miss / a skipped write, never a failed request.

Values must be picklable: convert sqlite Rows to dicts before caching.
Keys are any value with a deterministic repr (tuples of str/int/None/bool); they are
hashed with sha1, never with hash(), which is salted per process.
"""
import hashlib
import logging
import os
import pickle
import shutil
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MAX_AGE = 26 * 3600     # seconds; one nightly cadence plus slack
MEM_MAX = 512           # per-process LRU entries

MISS = object()
# Neither the stamp nor the DB file exists (a bare checkout, a test run): there is no
# publish to key on, so nothing is cached rather than caching under a constant key
# that would never invalidate.
NO_GEN = "none"

_cfg = {
    "cache_dir": Path(os.environ.get("WEB_CACHE_DIR") or (ROOT / ".web_cache")),
    "stamp": Path(os.environ.get("PUBLISH_STAMP") or (ROOT / ".publish_stamp")),
    "fallback": None,   # set lazily from web.database.SQLITE_PATH
    "enabled": os.environ.get("WEB_CACHE_DISABLE", "") == "",
}
_mem: "OrderedDict[tuple, tuple]" = OrderedDict()   # (gen, ns, key) -> (ts, value)
_lock = threading.Lock()
_seen_gen = {"gen": None}
_warned: set = set()


def configure(cache_dir=None, stamp=None, fallback=None, enabled=None):
    """Override paths (tests, alternative deployments). Clears the memory layer."""
    if cache_dir is not None:
        _cfg["cache_dir"] = Path(cache_dir)
    if stamp is not None:
        _cfg["stamp"] = Path(stamp)
    if fallback is not None:
        _cfg["fallback"] = Path(fallback)
    if enabled is not None:
        _cfg["enabled"] = bool(enabled)
    clear_memory()


def clear_memory():
    with _lock:
        _mem.clear()
    _seen_gen["gen"] = None


def _fallback_path() -> Path:
    if _cfg["fallback"] is None:
        try:
            from web.database import SQLITE_PATH
            _cfg["fallback"] = Path(SQLITE_PATH)
        except Exception:
            _cfg["fallback"] = ROOT / "documents.db"
    return _cfg["fallback"]


def generation() -> str:
    """Token for the current publish. Changes when the stamp (or, without a stamp,
    the DB file) is modified. One stat() call, ~microseconds."""
    for label, p in (("s", _cfg["stamp"]), ("d", _fallback_path())):
        try:
            return f"{label}{os.stat(p).st_mtime_ns}"
        except OSError:
            continue
    return NO_GEN


def _digest(ns: str, key) -> str:
    return hashlib.sha1(f"{ns}\x00{key!r}".encode("utf-8")).hexdigest()


def _gen_dir(gen: str) -> Path:
    return _cfg["cache_dir"] / gen


def _prune_old(gen: str):
    """Remove other generations' directories (once per process per generation)."""
    if _seen_gen["gen"] == gen:
        return
    _seen_gen["gen"] = gen
    base = _cfg["cache_dir"]
    try:
        for child in base.iterdir():
            if child.is_dir() and child.name != gen and not child.name.startswith("."):
                shutil.rmtree(child, ignore_errors=True)
    except OSError:
        pass


def get(ns: str, key):
    """Return the cached value or MISS."""
    if not _cfg["enabled"]:
        return MISS
    gen = generation()
    if gen == NO_GEN:
        return MISS
    mk = (gen, ns, key if _hashable(key) else repr(key))
    now = time.time()
    with _lock:
        hit = _mem.get(mk)
        if hit is not None:
            if now - hit[0] < MAX_AGE:
                _mem.move_to_end(mk)
                return hit[1]
            _mem.pop(mk, None)
    path = _gen_dir(gen) / (_digest(ns, key) + ".pkl")
    try:
        st = path.stat()
        if now - st.st_mtime >= MAX_AGE:
            return MISS
        with open(path, "rb") as f:
            value = pickle.load(f)
    except (OSError, pickle.PickleError, EOFError, AttributeError, ValueError,
            ImportError, IndexError, TypeError):
        return MISS
    _mem_put(mk, st.st_mtime, value)
    return value


def put(ns: str, key, value):
    """Store value for (ns, key) in the current generation; returns value."""
    if not _cfg["enabled"]:
        return value
    gen = generation()
    if gen == NO_GEN:
        return value
    mk = (gen, ns, key if _hashable(key) else repr(key))
    _mem_put(mk, time.time(), value)
    d = _gen_dir(gen)
    try:
        d.mkdir(parents=True, exist_ok=True)
        _prune_old(gen)
        data = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, d / (_digest(ns, key) + ".pkl"))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        # Best effort: the memory layer still serves this process. Logged once per
        # namespace so an unpicklable value (a sqlite Row) is noticed, not silent.
        if ns not in _warned:
            _warned.add(ns)
            logging.getLogger(__name__).warning(
                "pubcache: disk write skipped for %r: %s: %s", ns, type(exc).__name__, exc)
    return value


async def memo(ns: str, key, compute):
    """get-or-compute: `compute` is a zero-arg async callable."""
    hit = get(ns, key)
    if hit is not MISS:
        return hit
    return put(ns, key, await compute())


def _hashable(key) -> bool:
    try:
        hash(key)
        return True
    except TypeError:
        return False


def _mem_put(mk, ts, value):
    with _lock:
        _mem[mk] = (ts, value)
        _mem.move_to_end(mk)
        while len(_mem) > MEM_MAX:
            _mem.popitem(last=False)
