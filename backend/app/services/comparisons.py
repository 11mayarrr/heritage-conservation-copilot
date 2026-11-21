from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import Comparison, Inspection
from app.models.enums import RegionStatus
from app.services.inspections import InvalidState
from app.services.storage import get_storage
from app.vision.change import compare_regions, side_by_side, visual_change_candidates
from app.vision.imageio import decode_image, encode_jpeg
from app.vision.registration import register, warp_image


def _active(insp: Inspection) -> list[dict]:
    return [
        {"id": r.id, "index": r.index, "damage_type": r.damage_type, "polygon": r.polygon}
        for r in insp.regions
        if r.status != RegionStatus.REJECTED.value
    ]


def create_comparison(db: Session, before: Inspection, after: Inspection) -> Comparison:
    if before.wall_id != after.wall_id:
        raise InvalidState("المقارنة ممكنة فقط بين صورتين لنفس الجدار.")
    if before.id == after.id:
        raise InvalidState("اختر صورتين مختلفتين.")
    if not (before.image_key and after.image_key):
        raise InvalidState("إحدى الحالتين بلا صورة مقبولة.")
    if before.captured_at and after.captured_at and before.captured_at > after.captured_at:
        before, after = after, before

    st = get_storage()
    img_b = decode_image(st.get(before.image_key))
    img_a = decode_image(st.get(after.image_key))
    reg = register(img_b, img_a)
    regions = compare_regions(_active(before), _active(after), reg)
    visual = visual_change_candidates(img_b, img_a, reg)

    comp = Comparison(wall_id=before.wall_id, before_id=before.id, after_id=after.id)
    db.add(comp)
    db.flush()
    aligned_key = None
    if reg.ok and reg.homography is not None:
        aligned = warp_image(img_a, img_b.shape[:2], reg.homography)
        aligned_key = f"comparisons/{comp.id}/after_aligned.jpg"
        st.put(aligned_key, encode_jpeg(aligned))
        st.put(f"comparisons/{comp.id}/side_by_side.jpg", encode_jpeg(side_by_side(img_b, aligned)))
    else:
        st.put(f"comparisons/{comp.id}/side_by_side.jpg", encode_jpeg(side_by_side(img_b, img_a)))

    comp.result = {
        "registration": {
            "ok": reg.ok,
            "matches": reg.matches,
            "inliers": reg.inliers,
            "inlier_ratio": reg.inlier_ratio,
            "message_ar": reg.message_ar,
        },
        "regions": regions,
        "visual_candidates": visual,
        "aligned_key": aligned_key,
        "before": {"id": before.id, "case_number": before.case_number, "captured_at": before.captured_at.isoformat()},
        "after": {"id": after.id, "case_number": after.case_number, "captured_at": after.captured_at.isoformat()},
        "notes_ar": [
            "المقارنة تعتمد على مناطق التلف في الحالتين، وجودتها تتبع جودة المراجعة في كل حالة.",
            "اختلاف الإضاءة لا يُعد تلفًا جديدًا؛ مناطق التغير البصري مرشحة فقط وثقتها منخفضة.",
            "قياس الزيادة نسبي من مساحة الصورة، وليس بالمتر المربع.",
        ],
    }
    gb, ga = before.grid or {}, after.grid or {}
    if (gb.get("cols"), gb.get("rows"), gb.get("version")) != (ga.get("cols"), ga.get("rows"), ga.get("version")):
        comp.result["notes_ar"].append(
            f"الحالتان حُللتا بشبكتين مرجعيتين مختلفتين ({gb.get('cols')}×{gb.get('rows')} و{ga.get('cols')}×{ga.get('rows')}). "
            "مطابقة المناطق تعتمد على الحدود لا على رموز الخلايا، لكن رموز الموقع غير قابلة للمقارنة مباشرة."
        )
    db.commit()
    db.refresh(comp)
    return comp


def comparison_out(c: Comparison) -> dict:
    return {"id": c.id, "wall_id": c.wall_id, "before_id": c.before_id, "after_id": c.after_id,
            "created_at": c.created_at.isoformat(), **c.result}
