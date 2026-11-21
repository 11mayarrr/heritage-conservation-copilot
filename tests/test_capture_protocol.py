"""يُبقي بروتوكول التصوير متطابقًا مع ما يفحصه النظام فعلًا، ويمنع تعارض الأمثلة مع صيغة التسمية."""
import re
from pathlib import Path

from app.config import get_settings

DOC = Path(__file__).resolve().parents[1] / "docs" / "CAPTURE_PROTOCOL.md"
NAME_RE = re.compile(r"^[A-Za-z0-9-]+_\d{8}_\d{2}\.jpg$")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_protocol_quotes_the_real_quality_thresholds():
    s = get_settings()
    text = _text()
    assert f"{s.min_width}×{s.min_height}" in text
    assert str(int(s.dark_threshold)) in text
    assert str(int(s.bright_threshold)) in text


def test_protocol_is_marked_as_draft_and_needs_permission():
    text = _text()
    assert "مسودة" in text
    assert "إذن" in text
    assert "لم يراجعها مختص" in text


def test_protocol_has_required_sections():
    text = _text()
    for heading in ("قواعد الالتقاط", "تسمية الملفات", "الخصوصية", "قائمة التحقق"):
        assert heading in text


def test_example_file_names_follow_the_naming_pattern():
    names = re.findall(r"`([^`\s]+\.jpg)`", _text())
    assert len(names) >= 2
    for name in names:
        assert NAME_RE.match(name), name
