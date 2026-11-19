import type { DetectorInfo } from "../api/types";

export function PrivacyNotice() {
  return (
    <div className="banner info" role="note">
      <b>تنبيه الخصوصية:</b> تُخفى الوجوه آليًا قبل التحليل والتخزين، ولا تُحفظ الصورة الأصلية. لا يُستخدم النظام لتتبع
      الأشخاص أو تحليل سلوك الزوار. قد يفوت الكاشف وجوهًا صغيرة أو جانبية، فراجع الصورة وأضف إخفاءً يدويًا عند الحاجة.
    </div>
  );
}

export function DetectorNotice({ detector }: { detector?: DetectorInfo | null }) {
  if (!detector) return null;
  const mock = detector.kind === "mock";
  return (
    <div className={`banner ${mock ? "danger" : "warn"}`} role="note">
      <b>{mock ? "بيانات وهمية للعرض فقط." : "نتائج أولية غير مُقيّمة."}</b> {detector.disclaimer}{" "}
      <small>({detector.name} v{detector.version})</small>
    </div>
  );
}

export function PreliminaryNotice() {
  return (
    <div className="banner warn" role="note">
      التوصيات أولية تجريبية ومسترجعة فقط من قاعدة المعرفة المرفقة، ولا تُنفذ قبل اعتماد مختص الترميم. الوكيل يقترح، والمختص يقرر.
    </div>
  );
}
