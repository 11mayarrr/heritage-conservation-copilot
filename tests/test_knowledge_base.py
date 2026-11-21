import json

import pytest

from app.config import get_settings
from app.models.enums import DamageType
from app.rag.knowledge_base import KnowledgeBase, KnowledgeBaseError


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(get_settings().knowledge_base_dir)


def test_every_entry_has_a_real_source_with_locator_and_quote(kb):
    assert kb.entries
    read_sources = {s["url"] for s in kb.sources_index if s.get("status") == "read"}
    for e in kb.entries:
        assert e.sources
        for s in e.sources:
            assert s.title and s.publisher and s.locator and s.quote
            assert s.url in read_sources, f"{e.id} cites a source not marked as read"


def test_retrieval_is_closed_and_type_filtered(kb):
    res = kb.retrieve("crack", "تشقق إنشائي")
    assert res["sufficient"]
    ids = {e.id for e in kb.entries}
    for r in res["results"]:
        assert r["id"] in ids
        assert "crack" in r["damage_types"]
        assert r["approval"] == "demo_unapproved"
        assert r["suitability"] != "high"  # nothing is officially approved yet
    assert "اعتماد" in res["warning_ar"]


def test_uncertain_damage_gets_no_treatment(kb):
    res = kb.retrieve(DamageType.UNCERTAIN.value)
    assert not res["sufficient"] and res["results"] == []
    assert "غير كافية" in res["message_ar"]


def test_every_damage_type_except_uncertain_has_coverage(kb):
    for t in DamageType:
        if t is DamageType.UNCERTAIN:
            continue
        assert kb.retrieve(t.value)["sufficient"], t


def test_missing_source_is_rejected(tmp_path):
    (tmp_path / "bad.json").write_text(json.dumps({"treatments": [{
        "id": "x", "damage_types": ["crack"], "title_ar": "t", "method_ar": "m",
        "materials": ["a"], "tools": ["b"], "sources": [{"title": "", "publisher": "", "year": "", "locator": ""}]}]}))
    with pytest.raises(KnowledgeBaseError):
        KnowledgeBase(tmp_path)


def test_empty_library_reports_insufficient(tmp_path):
    kb = KnowledgeBase(tmp_path)
    res = kb.retrieve("crack")
    assert not res["sufficient"] and "غير كافية" in res["message_ar"]


def test_glossary_endpoint_covers_every_damage_type(client):
    from app.models.enums import DamageType

    g = client.get("/api/knowledge/glossary").json()
    assert g["status"] == "draft_unapproved"  # never presented as an approved glossary
    assert {t["id"] for t in g["terms"]} == {t.value for t in DamageType}
