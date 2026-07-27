"""movie.html を Chromium で 1 フレームずつ撮影して PNG 連番にする。

  python3 src/render_frames.py             # 全フレーム
  python3 src/render_frames.py --check     # 代表カットだけ contact sheet 用に撮る
"""
import argparse
import json
import os
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
W, H = 1920, 1080


def open_page(pw, tl):
    browser = pw.chromium.launch(executable_path=CHROME,
                                 args=["--force-device-scale-factor=1",
                                       "--disable-lcd-text",
                                       "--hide-scrollbars"])
    page = browser.new_page(viewport={"width": W, "height": H},
                            device_scale_factor=1)
    page.goto("file://" + os.path.join(ROOT, "src", "movie.html"))
    page.wait_for_function("typeof window.__seek === 'function'")
    page.evaluate("tl => setTimeline(tl)", tl)
    page.evaluate("() => document.fonts.ready")
    return browser, page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    args = ap.parse_args()

    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    fps = tl["fps"]
    total = tl["total"]

    with sync_playwright() as pw:
        browser, page = open_page(pw, tl)

        if args.check:
            outdir = os.path.join(BUILD, "check")
            shutil.rmtree(outdir, ignore_errors=True)
            os.makedirs(outdir, exist_ok=True)
            shots = []
            for k in tl["order"]:
                s = tl["scenes"][k]
                for frac in (0.12, 0.38, 0.62, 0.88):
                    shots.append((k, s["start"] + (s["end"] - s["start"]) * frac))
            for i, (k, t) in enumerate(shots):
                page.evaluate("t => window.__seek(t)", t)
                page.screenshot(path=os.path.join(outdir, f"{i:03d}_{k}_{t:07.2f}.png"))
            print(f"{len(shots)} 枚を {outdir} に出力")
            browser.close()
            return

        outdir = os.path.join(BUILD, "frames")
        shutil.rmtree(outdir, ignore_errors=True)
        os.makedirs(outdir, exist_ok=True)
        n = int(total * fps)
        for i in range(n):
            t = i / fps
            page.evaluate("t => window.__seek(t)", t)
            page.screenshot(path=os.path.join(outdir, f"f{i:06d}.png"))
            if i % 240 == 0:
                print(f"  {i}/{n}  ({t:6.1f}s)", flush=True)
        print(f"{n} フレームを {outdir} に出力")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
