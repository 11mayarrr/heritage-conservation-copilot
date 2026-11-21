"""H3 recorder: its button names must still exist in the UI, and it must fail cleanly. No browser is started."""
from pathlib import Path

import pytest

import record_demo as rd

FRONT = Path(__file__).resolve().parents[1] / "frontend" / "src"
UI_TEXT = "\n".join(p.read_text(encoding="utf-8") for p in FRONT.rglob("*.ts*"))


@pytest.mark.parametrize("key,label", sorted(rd.LABELS.items()))
def test_every_label_the_recorder_clicks_exists_in_the_ui(key, label):
    assert label in UI_TEXT, f"{key}: «{label}» no longer in frontend/src, update scripts/record_demo.py"


def test_seven_scenes_match_the_demo_script():
    assert len(rd.CAPTIONS) == 7
    doc = (Path(__file__).resolve().parents[1] / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8") \
        if (Path(__file__).resolve().parents[1] / "docs" / "DEMO_SCRIPT.md").exists() else None
    if doc:  # the script lives in another PR until it is merged
        assert doc.count("### المشهد") == 7


def test_the_first_caption_says_the_images_are_synthetic():
    assert "اصطناعية" in rd.CAPTIONS[0]


def test_stops_with_a_clear_message_when_the_backend_is_down():
    with pytest.raises(SystemExit) as e:
        rd.check_backend("http://127.0.0.1:1")
    assert "README" in str(e.value)


def test_playwright_is_imported_only_when_recording():
    src = Path(rd.__file__).read_text(encoding="utf-8")
    assert src.index("import sync_playwright") > src.index("def main")
