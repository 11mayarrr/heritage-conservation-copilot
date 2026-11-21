"""يُبقي سيناريو العرض مطابقًا للواجهة: كل زر مذكور موجود فعلًا، والمدة لا تتجاوز 3 دقائق."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "DEMO_SCRIPT.md"
PAGES = ROOT / "frontend" / "src"

UI_LABELS = [
    "رفع وتحليل الصور",
    "تسجيل جدار جديد",
    "تسجيل الجدار",
    "فتح خريطة التلف للمراجعة",
    "الانتقال إلى المراجعة والاعتماد",
    "تحديد وتعديل",
    "تعديل",
    "اعتماد النتيجة",
    "سبب القرار (يُحفظ في السجل)",
    "فتح التقرير",
    "المقارنة الزمنية",
    "قبل / بعد",
    "مفتاح الألوان",
]


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def _frontend_source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in PAGES.rglob("*.tsx"))


def test_every_ui_label_in_the_script_exists_in_the_frontend():
    doc, src = _doc(), _frontend_source()
    for label in UI_LABELS:
        assert f"«{label}»" in doc, f"غير مذكور في السيناريو: {label}"
        assert label in src, f"غير موجود في الواجهة: {label}"


def test_scenes_add_up_to_at_most_three_minutes():
    seconds = [int(m.group(1)) for m in re.finditer(r"^\| \d \|.*\| (\d+) \|$", _doc(), re.M)]
    assert len(seconds) == 7
    assert sum(seconds) <= 180


def test_script_discloses_synthetic_data_and_forbids_accuracy_claims():
    doc = _doc()
    assert "اصطناعية" in doc
    assert "لا نذكر نسبة دقة" in doc
    assert "لا نقول إن المكتبة «معتمدة»" in doc


def test_unmerged_features_are_marked_as_not_in_mvp():
    doc = _doc()
    for pr in ("#4", "#5", "#6", "#7", "#8"):
        assert f"PR {pr}" in doc
    assert "غير موجودة في `mvp` اليوم" in doc
