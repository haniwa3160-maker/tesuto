"""movie.html の 1 コマを使って YouTube サムネイル（1280x720）を作る。"""
import json
import os

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
OUT = os.path.join(ROOT, "out")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

OVERLAY = """
(() => {
  document.getElementById('sub').style.display='none';
  document.getElementById('scrim').style.display='none';
  const s=document.getElementById('stage');
  const css=`position:absolute;left:0;right:0;text-align:center;font-weight:800;color:#fff;
    font-family:"Rounded Mplus 1c",sans-serif;
    text-shadow:0 0 22px rgba(21,18,40,.9),8px 8px 0 #2b2545,-8px 8px 0 #2b2545,
    8px -8px 0 #2b2545,-8px -8px 0 #2b2545,0 10px 0 #2b2545,0 -10px 0 #2b2545,
    10px 0 0 #2b2545,-10px 0 0 #2b2545;`;
  const a=document.createElement('div');
  a.style.cssText=css+'top:40px;font-size:156px;letter-spacing:4px;';
  a.textContent='ここほれ、シロ！'; s.appendChild(a);
  const b=document.createElement('div');
  b.style.cssText=css+'top:236px;font-size:62px;color:#ffe6a8;';
  b.textContent='〜 はなさかじいさん 2026 〜'; s.appendChild(b);
  const c=document.createElement('div');
  c.style.cssText='position:absolute;left:50%;transform:translateX(-50%);bottom:52px;'+
    'background:#ff7a6b;color:#fff;font-weight:800;font-size:64px;padding:18px 56px;'+
    'white-space:nowrap;border-radius:999px;border:9px solid #2b2545;'+
    'font-family:"Rounded Mplus 1c",sans-serif;';
  c.textContent='この犬、なにを ほって いた と 思う？'; s.appendChild(c);
})()
"""


def main():
    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    # 動画の 1 コマ目と絵を揃える（R6③）：シロが掘っているカット
    op = tl["scenes"]["op"]
    t = op["start"] + (op["end"] - op["start"]) * 0.22
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, args=["--hide-scrollbars"])
        page = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.goto("file://" + os.path.join(ROOT, "src", "movie.html"))
        page.wait_for_function("typeof window.__seek === 'function'")
        page.evaluate("tl => setTimeline(tl)", tl)
        page.evaluate("t => window.__seek(t)", t)
        page.evaluate(OVERLAY)
        path = os.path.join(OUT, "thumbnail.png")
        page.screenshot(path=path)
        b.close()
    # YouTube 推奨の 1280x720 に落とす
    from PIL import Image
    im = Image.open(path).resize((1280, 720), Image.LANCZOS)
    im.save(path)
    print("書き出し:", path, f"{os.path.getsize(path)/1e3:.0f} KB")


if __name__ == "__main__":
    main()
