"""Record the 3-minute demo (docs/DEMO_SCRIPT.md) from the running web UI: a video plus one screenshot per scene (task H3).

It drives a real browser through the seven scenes of the demo script using the button names the UI shows,
then saves hcc-demo.webm (and hcc-demo.mp4 when ffmpeg exists) and a PNG per scene.

Everything shown is SYNTHETIC: the walls are drawn by code (scripts/make_synthetic_samples.py). The video must
be presented as such. Each run registers new demo walls (DEMO-<time>, CMP-<time>) so reruns never collide.

Before running: backend and frontend are up (README section 5). Then:
  pip install playwright
  python scripts/record_demo.py --url http://localhost:5173
Uses the Edge or Chrome already installed (no browser download). A scene that fails is logged with a screenshot
and the run continues, so one UI change does not lose the whole video.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample_data" / "synthetic"
VIEWPORT = {"width": 1280, "height": 800}

# Button and page names exactly as the UI shows them. tests/test_record_demo.py checks each one exists in frontend/src.
LABELS = {
    "nav_dashboard": "لوحة التحكم",
    "nav_upload": "رفع وتحليل الصور",
    "new_wall": "تسجيل جدار جديد",
    "wall_code_placeholder": "مثال: TRF-A12-N",
    "register_wall": "تسجيل الجدار",
    "analyze": "تحليل الصورة",
    "open_atlas": "فتح خريطة التلف للمراجعة",
    "go_review": "الانتقال إلى المراجعة والاعتماد",
    "approve_region": "اعتماد",
    "reason": "سبب القرار",
    "approve_case": "اعتماد النتيجة",
    "nav_reports": "التقارير",
    "open_report": "فتح التقرير",
    "nav_compare": "المقارنة الزمنية",
}
CAPTIONS = [
    "1 — الفكرة: الوكيل يقترح والمختص يقرر (صور اصطناعية)",
    "2 — الرفع: إخفاء الوجوه وفحص الجودة",
    "3 — خريطة التلف بألوان ثابتة",
    "4 — مراجعة المختص وتصحيحه",
    "5 — اعتماد المختص وسبب القرار",
    "6 — التقرير الجاهز للطباعة",
    "7 — المقارنة الزمنية: قبل / بعد",
]


class Recorder:
    def __init__(self, page, ctx, out: Path, slow: float):
        self.page, self.ctx, self.out, self.slow = page, ctx, out, slow
        self.results: list[tuple[str, bool, str]] = []

    def pause(self, seconds: float) -> None:
        self.page.wait_for_timeout(int(seconds * 1000 * self.slow))

    def caption(self, text: str) -> None:
        self.page.evaluate(
            """(t) => { let d = document.getElementById('hcc-cap');
              if (!d) { d = document.createElement('div'); d.id = 'hcc-cap';
                d.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#1b2a41;color:#fff;'
                  + 'font:600 20px sans-serif;padding:10px 18px;text-align:center;direction:rtl;opacity:.93';
                document.body.appendChild(d); } d.textContent = t; }""",
            text,
        )

    def scene(self, n: int, fn) -> None:
        name = CAPTIONS[n - 1]
        try:
            fn()
            self.caption(name)
            self.pause(2.5)
            self.page.screenshot(path=str(self.out / f"scene_{n}.png"))
            self.results.append((name, True, ""))
        except Exception as e:  # noqa: BLE001 - keep recording; the report says which scene failed
            try:
                self.page.screenshot(path=str(self.out / f"scene_{n}_FAILED.png"))
            except Exception:  # noqa: BLE001
                pass
            self.results.append((name, False, str(e).splitlines()[0][:160]))


def register_wall(page, code: str) -> None:
    page.get_by_text(LABELS["new_wall"]).click()
    page.get_by_placeholder(LABELS["wall_code_placeholder"]).fill(code)
    page.get_by_role("button", name=LABELS["register_wall"], exact=True).click()
    page.wait_for_timeout(800)


def upload(page, image: Path, timeout_ms: int = 90_000) -> None:
    page.locator("input[type=file]").set_input_files(str(image))
    page.get_by_role("button", name=LABELS["analyze"]).click()
    page.get_by_text(LABELS["open_atlas"]).first.wait_for(timeout=timeout_ms)


def prepare_comparison_wall(browser, url: str, code: str, images: list[Path], timeout: float = 30) -> None:
    """Two inspections of one wall, made in a separate browser context that is NOT recorded."""
    ctx = browser.new_context(viewport=VIEWPORT)
    ctx.set_default_timeout(timeout * 1000)
    page = ctx.new_page()
    page.goto(f"{url}/upload")
    page.get_by_text(LABELS["new_wall"]).wait_for()
    register_wall(page, code)
    for img in images:
        upload(page, img)
        page.get_by_role("link", name=LABELS["nav_upload"]).click()
        page.get_by_text(LABELS["new_wall"]).wait_for()
        page.locator("select").first.select_option(value=page.locator("select").first.locator("option", has_text=code).get_attribute("value"))
    ctx.close()


def make_scenes(rec: Recorder, url: str, live_code: str, cmp_code: str):
    page, ctx = rec.page, rec.ctx

    def s1():
        page.goto(url)
        page.get_by_role("link", name=LABELS["nav_dashboard"]).first.click()
        rec.pause(3)

    def s2():
        page.get_by_role("link", name=LABELS["nav_upload"]).first.click()
        rec.pause(1.5)
        register_wall(page, live_code)
        upload(page, SAMPLES / "synthetic_wall_T1.jpg")
        rec.pause(2)

    def s3():
        page.get_by_text(LABELS["open_atlas"]).first.click()
        page.wait_for_load_state("networkidle")
        rec.pause(3)

    def s4():
        page.get_by_text(LABELS["go_review"]).first.click()
        page.wait_for_load_state("networkidle")
        rec.pause(2)
        btn = page.get_by_role("button", name=LABELS["approve_region"], exact=True)
        if btn.count():
            btn.first.click()
            rec.pause(1.5)

    def s5():
        page.get_by_label(LABELS["reason"]).fill("المناطق راجعتها بيدي والحدود مناسبة")
        rec.pause(1.5)
        page.get_by_role("button", name=LABELS["approve_case"]).click()
        page.get_by_text("اعتمدها").first.wait_for(timeout=15_000)

    def s6():
        page.get_by_role("link", name=LABELS["nav_reports"]).first.click()
        rec.pause(1.5)
        with ctx.expect_page() as info:
            page.get_by_role("link", name=LABELS["open_report"]).first.click()
        rp = info.value
        rp.wait_for_load_state()
        rp.wait_for_timeout(int(1500 * rec.slow))
        for _ in range(4):
            rp.mouse.wheel(0, 500)
            rp.wait_for_timeout(int(700 * rec.slow))
        rp.close()

    def s7():
        page.get_by_role("link", name=LABELS["nav_compare"]).first.click()
        rec.pause(1.5)
        wall = page.locator("select").nth(0)
        wall.select_option(value=wall.locator("option", has_text=cmp_code).get_attribute("value"))
        page.locator("select").nth(1).select_option(index=1)
        page.locator("select").nth(2).select_option(index=1)  # قائمة «بعد» تستثني لقطة «قبل»
        page.locator("button.primary").first.click()
        page.get_by_text("قبل / بعد").first.wait_for(timeout=60_000)
        rec.pause(3)

    return [s1, s2, s3, s4, s5, s6, s7]


def launch(p, choice: str, headed: bool):
    if choice not in ("auto", "msedge", "chrome", "chromium"):
        return p.chromium.launch(executable_path=choice, headless=not headed)
    order = ["msedge", "chrome", "chromium"] if choice == "auto" else [choice]
    last = None
    for ch in order:
        try:
            return p.chromium.launch(channel=None if ch == "chromium" else ch, headless=not headed)
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"لم أجد Edge ولا Chrome ولا Chromium. جرّب: python -m playwright install chromium\n{last}")


def to_mp4(webm: Path) -> Path | None:
    if not shutil.which("ffmpeg"):
        return None
    mp4 = webm.with_suffix(".mp4")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)])
    return mp4 if r.returncode == 0 and mp4.exists() else None


def check_backend(url: str) -> None:
    try:
        urllib.request.urlopen(f"{url}/api/health", timeout=8).read()
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"لا أصل إلى {url}/api/health. شغّل الخلفية والواجهة أولًا (README القسم 5) أو غيّر --url.\n{e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:5173")
    ap.add_argument("--out", type=Path, default=ROOT / "demo_recording")
    ap.add_argument("--slow", type=float, default=1.0, help="مضاعف للهدوء بين الخطوات (2 = أبطأ مرتين)")
    ap.add_argument("--browser", default="auto", help="auto | msedge | chrome | chromium | مسار ملف تنفيذي")
    ap.add_argument("--timeout", type=float, default=30, help="ثواني الانتظار لكل خطوة قبل اعتبارها فاشلة")
    ap.add_argument("--headed", action="store_true", help="يُظهر نافذة المتصفح أثناء التسجيل")
    args = ap.parse_args(argv)
    url = args.url.rstrip("/")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("ثبّت المكتبة أولًا: pip install playwright")
    check_backend(url)
    if not (SAMPLES / "synthetic_wall_T1.jpg").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_synthetic_samples.py")], check=True)
    args.out.mkdir(parents=True, exist_ok=True)
    tmp = args.out / "_video"
    shutil.rmtree(tmp, ignore_errors=True)
    stamp = time.strftime("%H%M%S")
    live_code, cmp_code = f"DEMO-{stamp}", f"CMP-{stamp}"

    with sync_playwright() as p:
        browser = launch(p, args.browser, args.headed)
        try:
            prepare_comparison_wall(browser, url, cmp_code, [SAMPLES / "synthetic_wall_T1.jpg", SAMPLES / "synthetic_wall_T2.jpg"], args.timeout)
        except Exception as e:  # noqa: BLE001 - scene 7 will then fail and say so
            print(f"تنبيه: تعذّر تجهيز جدار المقارنة ({str(e).splitlines()[0][:120]}). سيفشل المشهد 7.")
        ctx = browser.new_context(viewport=VIEWPORT, record_video_dir=str(tmp), record_video_size=VIEWPORT, locale="ar-SA")
        ctx.set_default_timeout(args.timeout * 1000)
        page = ctx.new_page()
        rec = Recorder(page, ctx, args.out, args.slow)
        for i, fn in enumerate(make_scenes(rec, url, live_code, cmp_code), start=1):
            rec.scene(i, fn)
        video = page.video
        ctx.close()
        browser.close()
        src = Path(video.path())
    webm = args.out / "hcc-demo.webm"
    shutil.move(str(src), webm)
    shutil.rmtree(tmp, ignore_errors=True)
    mp4 = to_mp4(webm)

    print(f"\nالفيديو: {webm}" + (f"\nنسخة mp4: {mp4}" if mp4 else "\n(لا ffmpeg: الفيديو webm يُفتح في Edge وChrome، ولا يُفتح في QuickTime)"))
    for name, ok, why in rec.results:
        print(("✓ " if ok else "✗ ") + name + ("" if ok else f"  ← {why}"))
    print("كل ما في الفيديو صور اصطناعية مرسومة بالكود، وتُقدَّم هكذا.")
    return 0 if all(ok for _, ok, _ in rec.results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
