"""Excel and GeoJSON exports of an *approved* inspection (challenge step 10).

These are pure functions: they take the dicts produced by `inspection_out`, the
audit rows and a treatment lookup, so they need no database and are easy to test.
Nothing is exported unless a restoration specialist approved the inspection.

GeoJSON coordinates are NOT geographic. The project has no real-world location
or official grid for the walls yet, so regions are written in a local plane of
the wall image and the file says so explicitly (see COORD_WARNING_*).
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.models.enums import CONF_SOURCE_AR, PRIORITY_AR, InspectionStatus, RegionStatus

NOT_APPROVED_AR = "لا يُصدَّر إلا بعد أن يعتمد مختص الترميم الحالة."

COORD_SYSTEM = "wall_image_plane"
COORD_WARNING_AR = (
    "تنبيه: هذه ليست إحداثيات جغرافية حقيقية. الإحداثيات محلية على صورة الجدار: "
    "x = المسافة من يسار الصورة، y = المسافة من أسفل الصورة، والوحدة هي عرض الصورة "
    "(1 = كامل العرض). لا تُستخدم لتحديد موقع الجدار على الأرض، ولا تُقاس منها أبعاد "
    "بالأمتار قبل ربطها بشبكة رسمية."
)
COORD_WARNING_EN = (
    "WARNING: these are NOT real-world geographic coordinates. They are local to the wall "
    "image: x = distance from the left edge, y = distance up from the bottom edge, in units "
    "of the image width (1 = full width). Do not use them to locate the wall on the ground, "
    "and do not measure metres from them before they are tied to an official grid."
)

ACTION_LABEL_AR = {
    "create": "إنشاء",
    "update": "تعديل",
    "delete": "حذف",
    "approve": "اعتماد",
    "return": "إعادة للمراجعة",
    "status": "تغيير الحالة",
    "reanalyze": "إعادة تحليل",
    "approval_revoked": "إلغاء الاعتماد",
    "manual_blur": "إخفاء يدوي",
}
FIELD_LABEL_AR = {
    "damage_type": "نوع التلف",
    "polygon": "حدود المنطقة",
    "confidence": "درجة الثقة",
    "note": "ملاحظة",
    "description": "الوصف",
    "priority": "الأولوية",
    "needs_field_inspection": "فحص ميداني",
    "treatment_id": "المعالجة",
    "materials": "المواد",
    "tools": "الأدوات",
    "status": "الحالة",
    "expert_notes": "ملاحظات المختص",
}
ENTITY_LABEL_AR = {
    "inspection": "الحالة",
    "region": "المنطقة",
    "wall": "الجدار",
    "comparison": "المقارنة",
}


class NotApproved(ValueError):
    """Raised when an export is requested for an inspection that is not approved."""


def ensure_exportable(data: dict) -> None:
    """Only inspections approved by a specialist can be exported, and every
    active region must carry that approval (edits after approval reopen it)."""
    if data.get("status") != InspectionStatus.APPROVED.value:
        raise NotApproved(NOT_APPROVED_AR)
    if any(r["status"] != RegionStatus.APPROVED.value for r in data.get("regions", [])):
        raise NotApproved(NOT_APPROVED_AR)


# ------------------------------------------------------------------ helpers
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _fmt_utc(iso: str | None) -> str:
    """System timestamps are stored in UTC (SQLite drops the zone); label them."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return str(iso)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M") + " UTC"


def _fmt_date(iso: str | None) -> str:
    """Capture time is user-supplied and may have no time zone, so only the date."""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d")
    except ValueError:
        return str(iso)


def _value_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _source_line(s: dict) -> str:
    head = f"{s.get('title', '')} — {s.get('publisher', '')}"
    if s.get("year"):
        head += f"، {s['year']}"
    if s.get("locator"):
        head += f" — {s['locator']}"
    return head


def _region_view(r: dict, treatment: dict | None) -> dict:
    """Values shared by the Excel row and the GeoJSON properties."""
    sources = treatment["sources"] if treatment else []
    return {
        "label": f"R{r['index']}",
        "treatment_title": treatment["title_ar"] if treatment else "",
        "treatment_approval": treatment["approval"] if treatment else "",
        "treatment_approval_label": treatment.get("approval_label_ar", "") if treatment else "",
        "sources": sources,
        "source_lines": [_source_line(s) for s in sources],
    }


# ------------------------------------------------------------------ GeoJSON
def _signed_area(pts: list[list[float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        total += x1 * y2 - x2 * y1
    return total / 2


def _ring(poly: list, aspect: float) -> list[list[float]]:
    """Normalized image polygon (y down) -> closed, counter-clockwise ring in the
    local wall plane (y up, units of image width), as RFC 7946 expects."""
    pts = [[round(float(x), 6), round((1.0 - float(y)) * aspect, 6)] for x, y in poly]
    if _signed_area(pts) < 0:
        pts.reverse()
    if pts[0] != pts[-1]:
        pts.append(list(pts[0]))
    return pts


def build_geojson(data: dict, treatments: dict[str, dict]) -> dict:
    ensure_exportable(data)
    w, h = data.get("width") or 0, data.get("height") or 0
    aspect = h / w if w > 0 and h > 0 else 1.0
    features = []
    for r in sorted(data["regions"], key=lambda x: x["index"]):
        t = treatments.get(r["treatment_id"]) if r.get("treatment_id") else None
        v = _region_view(r, t)
        poly = r.get("polygon") or []
        features.append(
            {
                "type": "Feature",
                "id": r["id"],
                "geometry": {"type": "Polygon", "coordinates": [_ring(poly, aspect)]} if len(poly) >= 3 else None,
                "properties": {
                    "region": v["label"],
                    "damage_type": r["damage_type"],
                    "damage_label_ar": r["damage_label_ar"],
                    "priority": r["priority"],
                    "priority_ar": PRIORITY_AR.get(r["priority"], r["priority"]),
                    "confidence": r["confidence"],
                    "confidence_source": r["confidence_source"],
                    "confidence_source_ar": CONF_SOURCE_AR.get(r["confidence_source"], r["confidence_source"]),
                    "area_fraction": r["area_fraction"],
                    "grid_cells": r["grid_cells"],
                    "status": r["status"],
                    "status_label_ar": r["status_label_ar"],
                    "source": r["source"],
                    "needs_field_inspection": r["needs_field_inspection"],
                    "description": r["description"],
                    "note": r["note"],
                    "treatment_id": r["treatment_id"],
                    "treatment_title_ar": v["treatment_title"],
                    "treatment_approval": v["treatment_approval"],
                    "treatment_approval_label_ar": v["treatment_approval_label"],
                    "materials": r["materials"],
                    "tools": r["tools"],
                    "treatment_sources": v["sources"],
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "name": data["case_number"],
        "hcc": {
            "case_number": data["case_number"],
            "wall_code": data["wall"]["code"],
            "building_name": data["wall"]["building_name"],
            "captured_date": _fmt_date(data.get("captured_at")),
            "approved_by": data.get("approved_by"),
            "approved_at_utc": _fmt_utc(data.get("approved_at")),
            "image_width_px": w,
            "image_height_px": h,
            "coordinate_system": COORD_SYSTEM,
            "coordinate_warning_ar": COORD_WARNING_AR,
            "coordinate_warning_en": COORD_WARNING_EN,
        },
        "features": features,
    }


def geojson_text(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


# -------------------------------------------------------------------- Excel
_HEAD_FILL = PatternFill("solid", fgColor="E8DCC8")
_HEAD_FONT = Font(bold=True)
_WRAP = Alignment(wrap_text=True, vertical="top", horizontal="right")


def _put(ws, row: int, col: int, value):
    """Write a cell. Text is always stored as text: openpyxl would turn a string
    that starts with '=' into a formula, and expert notes are free text."""
    if isinstance(value, str):
        value = _ILLEGAL_XML.sub("", value)
    cell = ws.cell(row=row, column=col)
    cell.value = value
    if isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"
    cell.alignment = _WRAP
    return cell


def _table(wb: Workbook, title: str, headers: list[str], rows: list[list], widths: list[int]):
    ws = wb.create_sheet(title)
    ws.sheet_view.rightToLeft = True
    for c, head in enumerate(headers, start=1):
        cell = _put(ws, 1, c, head)
        cell.font, cell.fill = _HEAD_FONT, _HEAD_FILL
        ws.column_dimensions[get_column_letter(c)].width = widths[c - 1]
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            _put(ws, r, c, value)
    ws.freeze_panes = "A2"
    return ws


def _case_notes(data: dict, treatments: dict[str, dict]) -> list[str]:
    notes = [
        f"صُدّر هذا الملف من حالة اعتمدها المختص «{data.get('approved_by') or '—'}». "
        "كل تعديل مسجّل في ورقة «سجل التعديلات»."
    ]
    det = (data.get("analysis") or {}).get("detector") or {}
    if det and det.get("validated") is False:
        notes.append(
            f"الكاشف المستخدم ({det.get('name', '—')}) لم يُقيَّم على صور حقيقية معتمدة، "
            "لذا نسب الثقة الصادرة عن الوكيل تقديرية وغير معايرة."
        )
    unapproved = 0
    for r in data["regions"]:
        t = treatments.get(r["treatment_id"]) if r.get("treatment_id") else None
        if t and t["approval"] != "approved":
            unapproved += 1
    if unapproved:
        notes.append(
            f"المعالجات المقترحة لـ {unapproved} منطقة مأخوذة من مكتبة تجريبية غير معتمدة؛ "
            "يراجعها المختص قبل أي تنفيذ."
        )
    return notes


def build_xlsx(data: dict, audit_rows: list[dict], treatments: dict[str, dict]) -> bytes:
    ensure_exportable(data)
    wb = Workbook()
    wb.remove(wb.active)

    summary = data["summary"]
    case_rows = [
        ["رقم الحالة", data["case_number"]],
        ["رقم الجدار", data["wall"]["code"]],
        ["المبنى", data["wall"]["building_name"]],
        ["تاريخ التصوير", _fmt_date(data.get("captured_at"))],
        ["حالة الاعتماد", "معتمدة"],
        ["اعتمدها", data.get("approved_by") or ""],
        ["تاريخ الاعتماد", _fmt_utc(data.get("approved_at"))],
        ["عدد المناطق", summary["total"]],
        ["مناطق تحتاج فحصًا ميدانيًا", summary["field_inspection"]],
        ["ملاحظات المختص", data.get("expert_notes") or ""],
    ]
    for note in _case_notes(data, treatments):
        case_rows.append(["تنبيه", note])
    _table(wb, "الحالة", ["البند", "القيمة"], case_rows, [28, 90])

    headers = [
        "المنطقة", "نوع التلف", "الأولوية", "الثقة", "مصدر الثقة", "المساحة من الصورة",
        "خلايا الشبكة", "الوصف", "المعالجة المقترحة", "اعتماد المعالجة", "المواد", "الأدوات",
        "المرجع", "فحص ميداني", "حالة المنطقة", "المُنشئ", "ملاحظة المختص",
    ]
    widths = [10, 24, 12, 9, 22, 14, 16, 40, 34, 22, 36, 36, 50, 12, 16, 12, 36]
    rows = []
    for r in sorted(data["regions"], key=lambda x: x["index"]):
        t = treatments.get(r["treatment_id"]) if r.get("treatment_id") else None
        v = _region_view(r, t)
        rows.append(
            [
                v["label"],
                r["damage_label_ar"],
                PRIORITY_AR.get(r["priority"], r["priority"]),
                r["confidence"],
                CONF_SOURCE_AR.get(r["confidence_source"], r["confidence_source"]),
                r["area_fraction"],
                "، ".join(str(c) for c in r["grid_cells"]),
                r["description"],
                v["treatment_title"],
                v["treatment_approval_label"],
                "\n".join(r["materials"]),
                "\n".join(r["tools"]),
                "\n".join(v["source_lines"]),
                "نعم" if r["needs_field_inspection"] else "لا",
                r["status_label_ar"],
                "المختص" if r["source"] == "expert" else "الوكيل",
                r["note"],
            ]
        )
    ws = _table(wb, "المناطق", headers, rows, widths)
    for row in ws.iter_rows(min_row=2):
        row[3].number_format = "0%"
        row[5].number_format = "0.00%"
    ws.auto_filter.ref = ws.dimensions

    audit_table = [
        [
            _fmt_utc(e.get("at")),
            e.get("user", ""),
            ENTITY_LABEL_AR.get(e.get("entity", ""), e.get("entity", "")),
            ACTION_LABEL_AR.get(e.get("action", ""), e.get("action", "")),
            FIELD_LABEL_AR.get(e.get("field") or "", e.get("field") or ""),
            _value_text(e.get("old_value")),
            _value_text(e.get("new_value")),
            e.get("reason", ""),
        ]
        for e in audit_rows
    ]
    _table(
        wb,
        "سجل التعديلات",
        ["الوقت (UTC)", "المستخدم", "العنصر", "الإجراء", "الحقل", "القيمة القديمة", "القيمة الجديدة", "السبب"],
        audit_table,
        [20, 18, 12, 16, 16, 34, 34, 30],
    )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
