"""Regression check for the diffusion matcher's `source_implementing` flag (2026-10).

docs/research/diffusion-fidelity.md ("implementing-instrument subset"): a resolved
citation admits ANY citing document as a diffusion event — Politburo-meeting reposts,
党组会议 readouts, 解读, Xi's WAIC speech reposts — which are references, not
implementations. `is_implementing()` flags each event 0/1 from the SOURCE doc's
`doc_identity.genre` (promulgation / implementing → 1; explainer / readout / news /
other → 0; title_reissue → 1 by construction); the tracker counts implementing-only
by default. The genre itself is derived by scripts/build_doc_identity.py
(derive_genre), whose rules are unit-tested there (--self-test).

Two layers:
  1. Pure unit checks on `is_implementing` + the genre set build_doc_identity uses
     for its implementing rule (synthetic — no DB needed).
  2. Live checks against documents.db / diffusion_events for the AI+ anchor
     (900039770, resolved to its doc_identity instrument pool): a known readout
     source → 0, 黑龙江 AI+ 实施方案 → 1. Skipped when the DB (or the flagged table)
     is absent, so they run on the droplet, not on a dev Mac with a stale snapshot.

Run: python3 -m pytest tests/test_diffusion_implementing.py -v
  or: python3 tests/test_diffusion_implementing.py   (assert-based, no pytest needed)
"""
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))

from build_diffusion_events import IMPLEMENTING_IDENTITY_GENRES, is_implementing  # noqa: E402
from build_doc_identity import IMPLEMENTING_GENRES, derive_genre  # noqa: E402

AI_PLUS_ANCHOR = 900039770
HLJ_AIPLUS_PLAN = 12714192       # 黑龙江省人民政府关于印发《…“人工智能+”行动的实施方案》的通知 (action_plan)
HLJ_AIPLUS_EXPLAINER = 12715715  # 【文字解读】《…“人工智能+”行动的实施方案》政策解读 (explainer)
FJ_XI_WAIC_REPOST = 900084252    # 习近平出席2026世界人工智能大会…发表主旨讲话 (fj_xxzx, other)
SZ_ZHENGXIE_READOUT = 12758859   # 市政协党组召开会议 助推深圳经济… (sz_invest, other)


def _doc(igenre):
    return {"igenre": igenre}


def test_genre_set_matches_memo_subset():
    memo = {"action_plan", "work_plan", "policy_issuance", "opinion", "notice",
            "regulation", "decision", "strategy", "subsidy"}
    assert memo <= IMPLEMENTING_GENRES
    for g in ("explainer", "announcement", "report", "publicity", "commentary",
              "reply", "circular", "administrative", "other", ""):
        assert g not in IMPLEMENTING_GENRES, g
    assert IMPLEMENTING_IDENTITY_GENRES == {"promulgation", "implementing"}


def test_identity_genres_flag():
    assert is_implementing(_doc("implementing"), "citation") == 1
    assert is_implementing(_doc("promulgation"), "citation") == 1
    for g in ("explainer", "readout", "news", "other", ""):
        assert is_implementing(_doc(g), "citation") == 0, g
        assert is_implementing(_doc(g), "topic_genre") == 0, g


def test_title_reissue_is_implementing_by_construction():
    assert is_implementing(_doc("other"), "title_reissue") == 1
    assert is_implementing(_doc("news"), "title_reissue") == 1


def test_end_to_end_via_derive_genre():
    """The same cases the old title/algo-based flag was tested on, now through
    build_doc_identity.derive_genre → is_implementing."""
    def flag(title, algo, level, mtype="citation"):
        return is_implementing(_doc(derive_genre(title, algo, level)), mtype)
    # instruments
    assert flag("黑龙江省人民政府关于印发《黑龙江省深入实施“人工智能+”行动的实施方案》的通知",
                "action_plan", "provincial") == 1
    assert flag("关于印发《湖南省级人工智能终端产品认定管理办法（试行）》的通知",
                "policy_issuance", "provincial") == 1
    assert flag("市政府办公室关于印发XX市数字经济发展三年行动计划的通知", "other", "municipal") == 1
    # readouts / explainers / news → mentions
    assert flag("市政协党组召开会议 助推深圳经济持续向好加快高质量发展", "other", "municipal") == 0
    assert flag("习近平出席2026世界人工智能大会暨人工智能全球治理高级别会议开幕式并发表主旨讲话",
                "other", "provincial") == 0
    assert flag("中共中央政治局召开会议 分析研究当前经济形势和经济工作", "other", "municipal") == 0
    assert flag("盛阅春会见联想集团执行副总裁刘军", "other", "district") == 0
    assert flag("【文字解读】《黑龙江省深入实施“人工智能+”行动的实施方案》政策解读",
                "explainer", "provincial") == 0
    assert flag("《XX行动方案》政策解读", "action_plan", "provincial") == 0
    assert flag("广东“AI+文旅”的N种可能：23个应用场景典型案例和孵化项目正式发布",
                "other", "municipal") == 0


# --- live checks (droplet) ----------------------------------------------------
def _live_conn():
    db = Path(os.environ.get("SQLITE_PATH") or (ROOT / "documents.db"))
    if not db.exists() or db.stat().st_size == 0:
        return None
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(diffusion_events)")}
        has_identity = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='doc_identity'").fetchone()
    except sqlite3.Error:
        cols, has_identity = set(), None
    if "source_implementing" not in cols or not has_identity:
        conn.close()
        return None
    return conn


def test_live_ai_plus_anchor_flags():
    conn = _live_conn()
    if conn is None:
        try:
            import pytest
            pytest.skip("no flagged diffusion_events + doc_identity in a local documents.db")
        except ImportError:
            print("  (live check skipped: no flagged diffusion_events locally)")
            return
    flags = dict(conn.execute(
        """SELECT source_id, source_implementing FROM diffusion_events
           WHERE anchor_id IN (SELECT doc_id FROM doc_identity WHERE instrument_id =
                               (SELECT instrument_id FROM doc_identity WHERE doc_id = ?))""",
        (AI_PLUS_ANCHOR,)))
    conn.close()
    assert flags, "AI+ anchor has no events"
    # the implementing instrument
    assert flags.get(HLJ_AIPLUS_PLAN, 1) == 1
    # readouts / explainers that merely mention the anchor
    for sid in (HLJ_AIPLUS_EXPLAINER, FJ_XI_WAIC_REPOST, SZ_ZHENGXIE_READOUT):
        if sid in flags:  # event may legitimately vanish if the resolver changes
            assert flags[sid] == 0, sid
    n_impl = sum(flags.values())
    # before the flag: 103 events all counted; implementing should be a minority
    assert n_impl < len(flags), (n_impl, len(flags))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all checks passed")
