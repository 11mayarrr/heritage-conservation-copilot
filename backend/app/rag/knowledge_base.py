"""Conservation-aware retrieval over a CLOSED library of treatment entries.

Design choices (from the challenge brief, step 5: "يختار لكل تلف معالجة محددة
من المكتبة المعتمدة فقط"):
  * The system can only return entries that exist in knowledge_base/*.json.
    It never generates a treatment, a material, or a reference.
  * Each entry carries its source (title, publisher, year, page/section, url)
    and an approval status. Entries in the MVP are `demo_unapproved` until a
    conservation authority approves them.
  * If nothing matches, the result says so explicitly.

Retrieval is lexical (damage-type filter + TF-IDF-style keyword overlap), which
keeps it transparent and dependency-free. An embedding index can be swapped in
behind `retrieve()` later; the output contract stays the same.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings
from app.models.enums import INSUFFICIENT_INFO_AR, PRELIMINARY_WARNING_AR, DamageType

APPROVAL_LABELS_AR = {
    "approved": "معتمدة من جهة مختصة",
    "demo_unapproved": "تجريبية غير معتمدة",
}

_TOKEN = re.compile(r"[\w؀-ۿ]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "") if len(t) > 2]


@dataclass
class Source:
    title: str
    publisher: str
    year: str
    locator: str  # page or section inside the source
    url: str = ""
    quote: str = ""  # short verbatim excerpt supporting the entry (public-domain sources)
    # Arabic paraphrase of what the source says at `locator`. Used instead of a
    # verbatim quote for sources whose copyright status does not allow copying
    # text (see `quote_policy` in sources.json).
    summary_ar: str = ""


@dataclass
class Treatment:
    id: str
    damage_types: list[str]
    title_ar: str
    method_ar: str
    usage_ar: str
    materials: list[str]
    tools: list[str]
    cautions_ar: list[str]
    sources: list[Source]
    approval: str = "demo_unapproved"
    keywords: list[str] = field(default_factory=list)

    def text(self) -> str:
        return " ".join(
            [self.title_ar, self.method_ar, self.usage_ar, *self.materials, *self.keywords]
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "damage_types": self.damage_types,
            "title_ar": self.title_ar,
            "method_ar": self.method_ar,
            "usage_ar": self.usage_ar,
            "materials": self.materials,
            "tools": self.tools,
            "cautions_ar": self.cautions_ar,
            "sources": [s.__dict__ for s in self.sources],
            "approval": self.approval,
            "approval_label_ar": APPROVAL_LABELS_AR.get(self.approval, self.approval),
        }


class KnowledgeBaseError(ValueError):
    pass


def _parse(entry: dict, path: Path) -> Treatment:
    required = ["id", "damage_types", "title_ar", "method_ar", "materials", "tools", "sources"]
    missing = [k for k in required if not entry.get(k)]
    if missing:
        raise KnowledgeBaseError(f"{path.name}: entry {entry.get('id')} missing {missing}")
    for dt in entry["damage_types"]:
        DamageType(dt)  # raises on unknown type
    sources = [Source(**s) for s in entry["sources"]]
    for s in sources:
        if not (s.title and s.publisher and s.locator):
            raise KnowledgeBaseError(f"{entry['id']}: every source needs title, publisher, locator")
    return Treatment(
        id=entry["id"],
        damage_types=entry["damage_types"],
        title_ar=entry["title_ar"],
        method_ar=entry["method_ar"],
        usage_ar=entry.get("usage_ar", ""),
        materials=entry["materials"],
        tools=entry["tools"],
        cautions_ar=entry.get("cautions_ar", []),
        sources=sources,
        approval=entry.get("approval", "demo_unapproved"),
        keywords=entry.get("keywords", []),
    )


class KnowledgeBase:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.entries: list[Treatment] = []
        self.sources_index: list[dict] = []
        self.reload()

    def reload(self) -> None:
        self.entries = []
        for path in sorted(self.directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if path.name == "sources.json":
                self.sources_index = data
                continue
            for entry in data.get("treatments", []):
                self.entries.append(_parse(entry, path))
        docs = [Counter(_tokens(e.text())) for e in self.entries]
        n = max(1, len(docs))
        df: Counter = Counter()
        for d in docs:
            df.update(d.keys())
        self._idf = {t: math.log(1 + n / c) for t, c in df.items()}
        self._docs = docs

    def get(self, treatment_id: str) -> Treatment | None:
        return next((e for e in self.entries if e.id == treatment_id), None)

    def retrieve(self, damage_type: str, context: str = "", k: int = 3) -> dict:
        """Return up to k treatments for a damage type, ranked, with a
        suitability label, or an explicit 'insufficient information' result."""
        if damage_type == DamageType.UNCERTAIN.value:
            return {
                "damage_type": damage_type,
                "results": [],
                "sufficient": False,
                "message_ar": INSUFFICIENT_INFO_AR
                + " لا تُقترح معالجة لتلف غير مؤكد قبل الفحص الميداني.",
                "warning_ar": PRELIMINARY_WARNING_AR,
            }
        q = Counter(_tokens(context))
        scored = []
        for e, doc in zip(self.entries, self._docs):
            if damage_type not in e.damage_types:
                continue
            kw = sum(self._idf.get(t, 0) * min(c, doc[t]) for t, c in q.items() if t in doc)
            primary = 1.0 if e.damage_types[0] == damage_type else 0.6
            scored.append((primary + 0.1 * kw, e))
        scored.sort(key=lambda x: -x[0])
        results = []
        for score, e in scored[:k]:
            d = e.to_dict()
            d["score"] = round(score, 3)
            if e.approval == "approved" and score >= 1.0:
                d["suitability"] = "high"
                d["suitability_ar"] = "ملاءمة عالية (من المكتبة المعتمدة)"
            elif score >= 1.0:
                d["suitability"] = "medium"
                d["suitability_ar"] = "ملاءمة مبدئية: مطابقة لنوع التلف، والمصدر غير معتمد رسميًا"
            else:
                d["suitability"] = "low"
                d["suitability_ar"] = "ملاءمة منخفضة: تعالج هذا التلف بشكل ثانوي"
            results.append(d)
        return {
            "damage_type": damage_type,
            "results": results,
            "sufficient": bool(results),
            "message_ar": "" if results else INSUFFICIENT_INFO_AR
            + " لا توجد معالجة لهذا النوع في قاعدة المعرفة الحالية.",
            "warning_ar": PRELIMINARY_WARNING_AR,
        }


_kb: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase(get_settings().knowledge_base_dir)
    return _kb


def set_kb(kb: KnowledgeBase) -> None:
    global _kb
    _kb = kb
