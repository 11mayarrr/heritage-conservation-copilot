# Heritage Conservation Copilot — مساعد ترميم التراث الطيني

وكيل ذكي لدعم قرارات ترميم الجدران الطينية في حي الطريف (الدرعية). **الوكيل يقترح، والمختص يقرر.**

> ⚠️ **نموذج أولي (MVP).** كاشف التلف الحالي يعتمد على قواعد معالجة صور (OpenCV) وليس نموذجًا مدربًا على جدران الطريف.
> لم تُقس دقته، ودرجات الثقة تقديرية غير معايرة. قاعدة المعرفة تجريبية وغير معتمدة. لا يُستخدم لأي تدخل ميداني قبل اعتماد مختص.

## ما يفعله النظام

| الخطوة (حسب خريطة إجراءات التحدي) | التنفيذ في MVP |
|---|---|
| 1. فحص الصورة | الوضوح (Laplacian)، السطوع، الاحتراق الضوئي، الدقة الدنيا. الصورة المرفوضة لا تُحفظ ويُطلب إعادة التصوير |
| 2. إخفاء الوجوه | OpenCV (Haar frontal + profile، أو YuNet إن وُجد ملفه)، **قبل** أي تحليل أو تخزين. الأصل لا يُحفظ. إخفاء يدوي إضافي من الخريطة |
| 3. تحديد التلف | محول قابل للاستبدال: `heuristic` (تشققات + مناطق داكنة "غير مؤكدة") أو `mock` (مناطق وهمية للعرض) أو `model` (نموذج مدرب لاحقًا) |
| 4. تقدير الثقة | لكل منطقة درجة ثقة ومصدرها (`mock` / `heuristic_uncalibrated` / `model_unvalidated` / `expert`)، وعلامة "ثقة منخفضة" و"يحتاج فحصًا ميدانيًا" |
| 5. اقتراح المعالجة | استرجاع من **مكتبة مغلقة** (`knowledge_base/*.json`) فقط، مع المصدر والصفحة ومقتطف حرفي. لا توصية للتلف غير المؤكد |
| 6. المواد والأدوات | مرتبطة بكل منطقة وقابلة للتعديل |
| 7. الخريطة الموحدة | ألوان ثابتة + شبكة مرجعية (مؤقتة 6×4) + تنزيل PNG |
| 8. مراجعة المختص | تعديل الحدود (سحب النقاط)، تغيير النوع والثقة والأولوية، حذف، إضافة يدوية، ملاحظات، ربط المعالجة |
| 9. الاعتماد | اعتماد منطقة أو الحالة كاملة، أو إعادتها للمراجعة. أي تعديل بعد الاعتماد يلغيه تلقائيًا |
| 10. المخرجات | تقرير HTML مستقل قابل للطباعة PDF، وسجل تعديلات كامل (المستخدم، الوقت، القيمة القديمة والجديدة، السبب) |
| المقارنة الزمنية | محاذاة ORB + RANSAC مع تطبيع الإضاءة (CLAHE)، ثم مقارنة **مناطق التلف** (جديدة / زادت / لم تتغير / غير ظاهرة). تغير البكسلات يُعرض كمرشح منخفض الثقة فقط |

خارج النطاق: مراقبة الزوار أو تحليل سلوكهم.

## التشغيل

### محليًا (للتطوير)

```bash
# الخلفية (Python 3.11+)
pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# الواجهة (Node 20+) في نافذة أخرى
cd frontend && npm install && npm run dev
# افتح http://localhost:5173
```

يستخدم SQLite افتراضيًا (`data/hcc.db`) ويحفظ الصور في `data/storage/`.
للعرض بمناطق وهمية تُظهر كل الألوان: `HCC_DETECTOR=mock uvicorn app.main:app`.

### Docker (PostgreSQL)

```bash
docker compose up --build
# الواجهة: http://localhost:8080   — واجهة API: http://localhost:8000/docs
```

### صور للتجربة

```bash
python scripts/make_synthetic_samples.py   # يكتب sample_data/synthetic/
```

هذه صور **اصطناعية** (نسيج مرسوم وتشققات مرسومة) لاختبار سير العمل فقط، وليست جدرانًا حقيقية.
ضع صور الطريف الحقيقية في `sample_data/real/` مع توثيق المصدر والترخيص (انظر `sample_data/README.md`).

## الاختبارات

```bash
python -m pytest -q tests                 # 33 اختبارًا (رؤية، تحديد ذكي، قاعدة معرفة، API، مقاييس، تطابق الألوان)
HCC_TEST_DATABASE_URL=postgresql+psycopg://hcc:hcc@localhost/hcc python -m pytest -q tests   # على PostgreSQL
cd frontend && npm test && npm run build
```

تشمل الاختبارات: رفض الصور الضبابية والمظلمة ومنخفضة الدقة، عدم اختراع معالجة لتلف غير مؤكد، رفض أي مصدر غير مقروء
أو بلا رقم صفحة ومقتطف، رفض معالجة غير موجودة في المكتبة، دورة المراجعة كاملة مع السجل، إلغاء الاعتماد بعد التعديل،
المقارنة الزمنية على صورتين بزاوية وإضاءة مختلفتين، وفشل المحاذاة بشكل صريح عند صور غير مرتبطة.

## هيكل المشروع

```
backend/app/
  api/          نقاط FastAPI (walls, inspections, regions, comparisons, knowledge, audit)
  agents/       workflow.py (LangGraph) + rules.py (قواعد الأولوية والكفاية المؤقتة)
  vision/       quality, detectors/{heuristic,mock,segmentation_model}, segmenters/{sam2_adapter,grabcut}, registration, change, render
  privacy/      anonymizer.py + ملفات Haar
  rag/          knowledge_base.py (استرجاع مغلق مع المصادر)
  reports/      generator.py + templates/report.html
  services/     inspections, comparisons, audit, storage
  database/     SQLAlchemy models + session
  evaluation/   metrics.py (Precision / Recall / F1 / IoU)
frontend/src/   React + TypeScript + Konva (9 أقسام، RTL)
knowledge_base/ sources.json + treatments_*.json
scripts/        make_synthetic_samples.py, export_annotations.py, evaluate.py
tests/
```

## الانتقال إلى نموذج حقيقي

1. اجمع صورًا حقيقية للطريف، وارفعها، وصحح المناطق واعتمدها من مختصين.
2. `python scripts/export_annotations.py export/` يصدّر المضلعات المعتمدة بصيغة COCO لتدريب YOLO-seg أو SegFormer.
3. فعّل النموذج: `HCC_DETECTOR=model HCC_MODEL_WEIGHTS=...` (انظر `vision/detectors/segmentation_model.py`).
4. `python scripts/evaluate.py` يقارن ما اقترحه الوكيل (نسخة محفوظة لحظة التحليل) بما اعتمده المختص، ويحسب Precision وRecall وF1 وIoU لكل نوع.
   لا تُعرض أي أرقام دقة في النظام قبل هذا التقييم.

## أداة التحديد الذكي (SAM 2)

في خريطة التلف، زر **«تحديد ذكي»**: ينقر المختص داخل منطقة التلف (Shift+نقر لنقطة خارجها) فيرسم النظام حدودها،
ثم يحفظها كمنطقة جديدة بنوع يختاره، أو يطبقها على حدود منطقة موجودة. الأداة ترسم الحدود فقط ولا تحدد نوع التلف،
وكل استخدام يُسجل في سجل التعديلات مع اسم الأداة.

- **بدون إعداد:** تعمل ببديل OpenCV GrabCut، وهو تقريبي ويظهر تنبيه بذلك في الواجهة.
- **لتفعيل SAM 2:**
  ```bash
  pip install -r requirements-sam2.txt
  python scripts/download_sam2.py tiny      # يطبع متغيرات البيئة المطلوبة
  HCC_SEGMENTER=sam2 HCC_SAM2_CHECKPOINT=models/sam2.1_hiera_tiny.pt \
    HCC_SAM2_CONFIG=configs/sam2.1/sam2.1_hiera_t.yaml uvicorn app.main:app
  ```
  أو `HCC_SAM2_MODEL_ID=facebook/sam2.1-hiera-tiny` للتنزيل من Hugging Face.

> المحول (`vision/segmenters/sam2_adapter.py`) مكتوب على واجهة `SAM2ImagePredictor` الرسمية، ومختبر في المشروع بنموذج بديل
> يحاكيها، لأن أوزان SAM 2 لم يمكن تنزيلها في بيئة التطوير. أول تشغيل حقيقي له يحتاج تأكيدًا على جهاز يملك الأوزان.

## الافتراضات الحالية

- الواجهة عربية فقط (RTL). التشغيل محلي، ولا يُرسل أي شيء لخدمات سحابية.
- الشبكة المرجعية مؤقتة (6×4، أعمدة A–F وصفوف 1–4) إلى أن تتوفر الشبكة المعتمدة للجدار.
- المساحة نسبة من مساحة الصورة، لا بالمتر المربع، لعدم توفر مرجع قياس.
- قواعد الأولوية مؤقتة وموثقة في التقرير.
- اسم المختص يُدخل في الواجهة؛ لا يوجد تسجيل دخول حقيقي.

## القيود المعروفة

- الكاشف التجريبي لا يصنف تقشر الطلاء ولا فقدان الأجزاء ولا تآكل الحواف آليًا؛ هذه تُضاف يدويًا حتى يتوفر نموذج مدرب.
- قد يخلط بين التشققات والفواصل والزخارف والظلال، والمناطق الداكنة تُعلّم "غير مؤكدة" دائمًا.
- كاشف الوجوه (Haar) يفوت الوجوه الصغيرة أو الجانبية؛ لذلك يوجد إخفاء يدوي وتنبيه في الواجهة.
- قاعدة المعرفة مأخوذة من مرجع أمريكي عام 1978 عن مباني الأدوبي، وليست خاصة بالعمارة النجدية، وكل مدخلاتها "غير معتمدة".
- لا يقاس ميل زاوية التصوير آليًا بعد.

## المصادر المستخدمة

- U.S. National Park Service, *Preservation Brief 5: Preservation of Historic Adobe Buildings* (Tiller & Look, 1978) — المصدر الوحيد الذي بُنيت عليه المعالجات.
- مدرجة لكن **غير مقروءة** ولا يُستشهد بها: Getty Conservation Institute, *Terra Literature Review* (2008)؛ ICOMOS-ISCS, *Illustrated glossary on stone deterioration patterns*.

## لقطات (على صور اصطناعية)

| | |
|---|---|
| ![لوحة التحكم](docs/screenshots/dashboard.jpg) | ![خريطة التلف](docs/screenshots/atlas-editor.jpg) |
| ![المقارنة الزمنية](docs/screenshots/temporal-comparison.jpg) | ![التقرير](docs/screenshots/report.jpg) |
