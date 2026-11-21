"""يمنع أن يتحول ترخيص «لم نتحقق منه» في docs/DATASETS.md إلى ادعاء صامت."""
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "DATASETS.md"


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def _rows() -> list[str]:
    # جدول القسم 1 فقط (قبل جدول المرشح الجديد)
    section_one = _text().split("## 2.")[0]
    return [l for l in section_one.splitlines() if l.startswith("| **")]


def test_every_dataset_from_the_plan_is_listed():
    text = _text()
    for name in ("SYCrack", "CrackSeg9k", "OmniCrack30k", "Surface Damage for Heritage Site Protection"):
        assert name in text, name


def test_unverified_licenses_are_stated_as_unverified():
    rows = {r.split("|")[1]: r for r in _rows()}
    for key in ("CrackSeg9k", "OmniCrack30k"):
        row = next(v for k, v in rows.items() if key in k)
        assert "لم نتحقق" in row, key


def test_no_dataset_is_claimed_as_downloaded():
    text = _text()
    assert "لم يُنزَّل أي شيء بعد" in text
    for row in _rows():
        cells = [c.strip() for c in row.split("|")]
        # عمود «تاريخ التنزيل» هو الخامس في جدول الداتا سيت
        if len(cells) > 6 and "صورنا الاصطناعية" not in cells[1]:
            assert cells[5] in ("لم يُنزَّل", "غير متاح"), cells[1]


def test_synthetic_data_is_not_for_accuracy():
    assert "لا تُستخدم لقياس الدقة" in _text()
