"""doc_identity.province stores the SITE fallback, with provenance (2026-11-12).

Before: `province` held only per-document evidence and was NULL otherwise; the two
in-house consumers (build_diffusion_events.load, pairs.load_docs) applied
`iprov or province_of(site)` themselves, but a reader of the RAW column
(global_discourse/concept_scan.py) saw 40,612 of 70,017 post-2025-07 sub-national docs
as province-less — 40,531 of them on a site whose province was known.

Now: province_source = 'doc' (per-document evidence) | 'site' (site fallback) | NULL.
Guard: a site whose OWN per-document provinces mostly disagree with its label gets no
fallback (contradicted_sites) — found on `suzhou_ah`, named 宿州 (Anhui) but crawling
www.suzhou.gov.cn, 苏州 (Jiangsu): 82 of 82 per-document answers said js.

Run: python3 -m pytest tests/test_province_site_fallback.py -v
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "classification"))

import build_doc_identity as bdi  # noqa: E402
import build_diffusion_events as bde  # noqa: E402


# --- the pure resolver ------------------------------------------------------
def test_per_document_evidence_wins():
    assert bdi.resolve_province("gd", "sx") == ("gd", "doc")


def test_site_fallback_when_no_evidence():
    assert bdi.resolve_province(None, "sx") == ("sx", "site")


def test_null_when_neither():
    assert bdi.resolve_province(None, None) == (None, None)


# --- the contradiction guard ------------------------------------------------
def test_suzhou_shape_is_contradicted():
    per_doc = [("suzhou_ah", "js")] * 82 + [("suzhou_ah", None)] * 1135
    got = bdi.contradicted_sites(per_doc, {"suzhou_ah": "ah"}.get)
    assert got == {"suzhou_ah": (0, 82, "js")}


def test_mostly_agreeing_site_is_not_contradicted():
    # a provincial portal that also posts some other provinces' texts: 6 of 10 agree
    per_doc = [("fujian", "fj")] * 6 + [("fujian", "zj")] * 4
    assert bdi.contradicted_sites(per_doc, {"fujian": "fj"}.get) == {}


def test_contradiction_needs_ten_per_document_rows():
    per_doc = [("tiny", "js")] * 9
    assert bdi.contradicted_sites(per_doc, {"tiny": "ah"}.get) == {}


def test_site_without_a_province_is_never_contradicted():
    per_doc = [("npc", "gd")] * 50
    assert bdi.contradicted_sites(per_doc, {}.get) == {}


# --- the site labels ---------------------------------------------------------
def test_suzhou_ah_is_jiangsu_by_override():
    # sites.name still says 宿州市 (Anhui) — store_site never updates a name
    assert bde.province_of("suzhou_ah", "Suzhou, Anhui (宿州市)") == "js"
    assert bde.province_of("ahsz", "宿州市") == "ah"          # the real 宿州 site
    assert bde.province_of("jcgov", "晋城市") == "sx"


# --- end to end over build() on an in-memory corpus -------------------------
def _fixture():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE sites (site_key TEXT PRIMARY KEY, name TEXT, admin_level TEXT);
        CREATE TABLE documents (id INTEGER PRIMARY KEY, site_key TEXT, title TEXT,
            document_number TEXT, publisher TEXT, date_published TEXT, crawl_timestamp TEXT,
            algo_doc_type TEXT, classify_main_name TEXT);
        CREATE TABLE doc_issuers (doc_id INTEGER PRIMARY KEY, lead_issuer TEXT);
    """)
    c.executemany("INSERT INTO sites VALUES (?,?,?)", [
        ("jcgov", "晋城市", "municipal"),
        ("suzhou_ah", "Suzhou, Anhui (宿州市)", "municipal"),   # override -> js
        ("mislabeled", "Suzhou, Anhui (宿州市)", "municipal"),  # no override: contradicted
        ("gov", "State Council", "central"),
    ])
    rows = [
        (1, "jcgov", "晋城公积金！最新提醒！"),
        (2, "suzhou_ah", "苏州科技城动态公交直达医院门诊"),
        (3, "gov", "国务院关于印发某某规划的通知"),
        (4, "mislabeled", "苏州科技城动态公交直达医院门诊"),
    ]
    rows += [(100 + i, "mislabeled", f"苏州市人民政府办公室关于做好第{i}批项目申报工作的通知")
             for i in range(12)]
    c.executemany(
        "INSERT INTO documents VALUES (?,?,?,'','','2026-09-01','2026-09-02','other','')", rows)
    return c


def test_build_writes_site_fallback_with_provenance():
    docs, meta = bdi.build(_fixture())
    got = {i: (docs[i]["level"], docs[i]["province"], docs[i]["province_source"])
           for i in (1, 2, 3, 4, 100)}
    assert got == {
        1: ("municipal", "sx", "site"),     # no evidence -> the site's province
        2: ("municipal", "js", "site"),     # suzhou_ah -> js through the override
        3: ("central", None, None),         # central docs never carry a province
        4: ("municipal", None, None),       # contradicted site: fallback WITHHELD
        100: ("municipal", "js", "doc"),    # per-document evidence
    }
    assert meta["prov_contradicted"] == {"mislabeled": (0, 12, "js")}


def test_ddl_and_insert_agree_on_column_count():
    c = sqlite3.connect(":memory:")
    c.executescript(bdi.DDL)
    cols = [r[1] for r in c.execute("PRAGMA table_info(doc_identity)")]
    assert cols[-1] == "province_source" and len(cols) == 12
    docs, _ = bdi.build(_fixture())
    n, _ = bdi.write(c, docs)
    assert n == 16
    assert c.execute("SELECT province, province_source FROM doc_identity WHERE doc_id=1").fetchone() \
        == ("sx", "site")
