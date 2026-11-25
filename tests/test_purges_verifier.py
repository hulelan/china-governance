"""The purge dataset's quote verifier, on a fixture.

The rule under test: a "corpus" evidence item counts only if its quote is an EXACT
substring of that document's title or body_text_cn. Anything else (missing document,
paraphrase, whitespace drift, a quote with no doc id) is a failure, and a person whose
only removal evidence fails is not corpus-verified.
"""
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rnd" / "purges" / "build_purges.py"
spec = importlib.util.spec_from_file_location("build_purges", SCRIPT)
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

DOCS = {
    "1": {"site": "xinhua", "url": "http://x/1", "date": "2026-01-02 08:00:00", "title": "甲某严重违纪违法被开除党籍",
          "body": "经中共中央批准，决定给予甲某开除党籍处分。\n　　此前已免去其职务。"},
    "2": {"site": "gov", "url": "http://x/2", "date": "2026-02-03", "title": "任免名单", "body": None},
    str(bp.CC20_FULL): {"site": "ce", "url": "", "date": "2022-10-22", "title": "委员名单",
                        "body": "名单\n甲某 乙某（女） 丙某"},
    str(bp.CC20_ALT): {"site": "ce", "url": "", "date": "2022-10-22", "title": "候补委员名单", "body": "丁某（回族） 戊某"},
}


def person(name, ev, tier="副国级", rtype="a", flags=None, action="expelled"):
    return {"name_cn": name, "tier": tier, "removal_type": rtype, "flags": flags or [],
            "events": [{"date": "2026-01-02", "action": action, "establishes_removal": True, "evidence": ev}]}


def dataset(persons, cc=None):
    return {"meta": {"as_of": "2026-11-25"}, "persons": persons, "cc_expulsions": cc or []}


def corpus(doc_id, quote):
    return {"label": "corpus", "doc_id": doc_id, "quote": quote}


def test_exact_body_and_title_quotes_pass_and_are_stamped():
    d = dataset([person("甲某", [corpus(1, "决定给予甲某开除党籍处分"), corpus(1, "甲某严重违纪违法被开除党籍")])])
    assert bp.verify(d, DOCS) == []
    body_ev, title_ev = d["persons"][0]["events"][0]["evidence"]
    assert body_ev["verified"] and body_ev["where"] == "body"
    assert title_ev["where"] == "title"
    assert body_ev["site"] == "xinhua" and body_ev["doc_date"] == "2026-01-02"


def test_paraphrase_whitespace_drift_and_missing_doc_fail():
    d = dataset([person("甲某", [
        corpus(1, "决定给予甲某开除党籍的处分"),            # one inserted character
        corpus(1, "处分。 此前已免去其职务"),                # collapsed whitespace: must NOT match
        corpus(999, "任何文字"),                             # no such document
        corpus(2, "任免"),                                   # NULL body, but the title holds it
        {"label": "corpus", "quote": "无文号"},              # no doc id
    ])])
    fails = bp.verify(d, DOCS)
    assert [f[0] for f in fails] == [1, 1, 999, None]
    ev = d["persons"][0]["events"][0]["evidence"]
    assert [e["verified"] for e in ev] == [False, False, False, True, False]


def test_web_and_recalled_evidence_never_verifies_a_person():
    d = dataset([
        person("甲某", [corpus(1, "决定给予甲某开除党籍处分")]),
        person("乙某", [{"label": "web, not in corpus", "url": "http://w", "fetched": True, "note": ""}]),
        person("丙某", [{"label": "not in corpus", "note": "recalled"}], rtype="b"),
        person("丁某", [corpus(1, "并非原文")], tier="CMC member"),
        person("戊某", [corpus(1, "此前已免去其职务")], flags=["removed_before_18th_congress"]),
    ])
    bp.verify(d, DOCS)
    s = bp.summarise(d)
    h = s["headline"]
    assert h["total_all_types"] == 3                      # 丁某 is CMC tier, 戊某 is flagged out
    assert h["by_type"] == {"a": 2, "b": 1, "c": 0, "d": 0}
    assert h["corpus_verified_all_types"] == 1            # only 甲某
    assert h["plus_flagged_before_congress"] == ["戊某"]
    assert h["cmc_member_tier"] == 1 and h["cmc_member_tier_corpus_verified"] == 0
    assert s["cells"]["副国级|a"]["of_which_not_corpus_verified"] == ["乙某"]


def test_membership_is_resolved_from_the_name_lists():
    cc = [{"plenum": "20-9", "date": "2026-01-01", "congress": 20, "expelled": ["乙某", "丁某", "己某"],
           "other": [{"name": "戊某", "action": "x"}], "evidence": [corpus(1, "开除党籍")]}]
    d = dataset([], cc)
    bp.verify(d, DOCS)
    assert bp.resolve_membership(d, DOCS) == []
    assert d["cc_expulsions"][0]["membership"] == {"乙某": "full", "丁某": "alternate", "己某": "not found"}
    assert d["cc_expulsions"][0]["other"][0]["membership"] == "alternate"
    row = bp.summarise(d)["cc_expulsions_by_plenum"][0]
    assert (row["full_members"], row["alternate_members"], row["evidence"]) == (1, 1, "corpus")


def test_cli_exits_nonzero_on_a_bad_quote_and_does_not_rewrite(tmp_path):
    import json
    db = tmp_path / "documents.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, site_key TEXT, url TEXT, date_published TEXT, "
              "title TEXT, body_text_cn TEXT)")
    for k, v in DOCS.items():
        c.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)", (int(k), v["site"], v["url"], v["date"], v["title"], v["body"]))
    c.commit(); c.close()
    good = dataset([person("甲某", [corpus(1, "决定给予甲某开除党籍处分")])])
    bad = dataset([person("甲某", [corpus(1, "决定给予甲某留党察看处分")])])
    for name, payload, want in (("good.json", good, 0), ("bad.json", bad, 1)):
        f = tmp_path / name
        f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        before = f.read_text(encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT), "--data", str(f), "--db", str(db)], capture_output=True, text=True)
        assert r.returncode == want, r.stdout + r.stderr
        if want:
            assert "FAIL doc 1" in r.stdout and f.read_text(encoding="utf-8") == before
        else:
            assert json.loads(f.read_text(encoding="utf-8"))["persons"][0]["corpus_verified"] is True
