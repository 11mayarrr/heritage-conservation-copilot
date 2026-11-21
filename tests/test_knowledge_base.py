import json

import pytest

from app.config import get_settings
from app.models.enums import DamageType
from app.rag.knowledge_base import KnowledgeBase, KnowledgeBaseError


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(get_settings().knowledge_base_dir)


def test_every_entry_has_a_real_source_with_locator_and_support(kb):
    assert kb.entries
    index = {s["url"]: s for s in kb.sources_index}
    for e in kb.entries:
        assert e.sources
        for s in e.sources:
            assert s.title and s.publisher and s.locator
            record = index.get(s.url)
            assert record and record.get("status") == "read", f"{e.id} cites a source not marked as read"
            if record.get("quote_policy") == "summary_only":
                # copyrighted source: Arabic paraphrase + locator, never copied text
                assert s.summary_ar and not s.quote, f"{e.id}: summary_only source needs summary_ar and no quote"
            else:
                assert s.quote, f"{e.id}: public-domain source needs a verbatim quote"


def test_atturaif_entries_are_site_specific_and_unapproved(kb):
    site = [e for e in kb.entries if e.id.startswith("atturaif-")]
    assert len(site) >= 7
    for e in site:
        assert e.approval == "demo_unapproved"
        assert all("unesco" in s.url for s in e.sources)
        assert e.cautions_ar, f"{e.id}: needs cautions"
        # the review panel splits materials/tools on commas, so list items must not contain any
        for item in [*e.materials, *e.tools]:
            assert "،" not in item and "," not in item, f"{e.id}: comma inside '{item}'"
    # every damage type except 'uncertain' has a site-specific option
    covered = {dt for e in site for dt in e.damage_types}
    assert covered >= {t.value for t in DamageType if t is not DamageType.UNCERTAIN}


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
