"""scripts/rnd/purges/upgrade_web_evidence.py: a web item becomes `corpus` only
with an exact-substring quote from the document its url now resolves to."""
import copy
import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts" / "rnd" / "purges" / "upgrade_web_evidence.py"
_spec = importlib.util.spec_from_file_location("upgrade_web_evidence", _p)
uw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uw)

URL = "https://www.court.gov.cn/fabu/xiangqing/94792.html"
DATA = {"persons": [{"name_cn": "孙政才", "events": [
    {"date": "2018-05-08", "action": "sentenced", "detail_en": "life",
     "evidence": [{"label": uw.WEB, "url": URL, "fetched": True, "note": "SPC release"}]}]}]}
DOCS = {URL: {"id": 7, "site": "spc", "date": "2018-05-08",
              "title": "孙政才受贿案一审公开宣判", "body": "对被告人孙政才以受贿罪判处无期徒刑。"}}
PATH = ["persons", 0, "events", 0, "evidence", 0]


def test_list_finds_the_web_item():
    assert [p for p, _ in uw.walk_web(DATA)] == [tuple(PATH)]


def test_apply_relabels_and_keeps_provenance():
    d = copy.deepcopy(DATA)
    fails = uw.apply(d, [{"path": PATH, "url": URL, "doc_id": 7,
                          "quote": "以受贿罪判处无期徒刑"}], DOCS)
    assert fails == []
    ev = uw.at(d, PATH)
    assert ev["label"] == "corpus" and ev["doc_id"] == 7 and ev["quote"] == "以受贿罪判处无期徒刑"
    assert ev["upgraded_from"] == {"label": uw.WEB, "url": URL, "fetched": True, "note": "SPC release"}
    assert list(uw.walk_web(d)) == []          # the provenance copy is not a live web item


def test_a_paraphrased_quote_is_refused():
    d = copy.deepcopy(DATA)
    fails = uw.apply(d, [{"path": PATH, "url": URL, "doc_id": 7,
                          "quote": "孙政才被判无期徒刑"}], DOCS)
    assert fails and "substring" in fails[0][1]


def test_establishes_removal_is_set_only_when_asked_and_on_a_removal_event():
    d = copy.deepcopy(DATA)
    assert uw.apply(d, [{"path": PATH, "url": URL, "doc_id": 7, "quote": "无期徒刑"}], DOCS) == []
    assert "establishes_removal" not in d["persons"][0]["events"][0]
    d = copy.deepcopy(DATA)
    assert uw.apply(d, [{"path": PATH, "url": URL, "doc_id": 7, "quote": "无期徒刑",
                         "establishes_removal": True}], DOCS) == []
    assert d["persons"][0]["events"][0]["establishes_removal"] is True
    d = copy.deepcopy(DATA)
    d["persons"][0]["events"][0]["action"] = "named_in_party_media"
    fails = uw.apply(d, [{"path": PATH, "url": URL, "doc_id": 7, "quote": "无期徒刑",
                          "establishes_removal": True}], DOCS)
    assert fails and "non-removal" in fails[0][1]


def test_a_wrong_doc_id_is_refused():
    d = copy.deepcopy(DATA)
    fails = uw.apply(d, [{"path": PATH, "url": URL, "doc_id": 8, "quote": "无期徒刑"}], DOCS)
    assert fails and "does not resolve" in fails[0][1]
