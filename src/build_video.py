"""Chromium で 1 フレームずつ描き、ffmpeg に直接流し込んで MP4 を作る。

  python3 src/build_video.py            # 本編（16:9）
  python3 src/build_video.py --shorts   # 縦型 60 秒版
ディスクに連番 PNG を残さないので、長尺でも容量を食わない。
"""
import argparse
import json
import os
import subprocess
import sys

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
OUT = os.path.join(ROOT, "out")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Shorts（R6③）：時系列に並べず、結論を先に見せてから「なぜ」を語る。
# 秒数直打ちだと台本を直すたびに壊れるので、シーン内の割合で指定する。
# (シーンID, 開始割合, 終了割合, 最大秒数)
SHORTS_CUTS = [
    ("s9",  0.72, 1.00, 7.0),   # 結論：灰色の中庭が花でいっぱいになる
    ("op",  0.00, 0.30, 4.0),   # 問い：この犬はごみ捨て場に捨てられていた
    ("s2",  0.45, 0.85, 6.0),   # 拾う
    ("s3",  0.46, 0.74, 5.0),   # 目が光る
    ("s4",  0.00, 0.34, 6.0),   # ここほれ、ワン！
    ("s4b", 0.34, 0.62, 5.0),   # ハナの種は芽が出ない
    ("s6",  0.42, 0.80, 6.5),   # こわれる
    ("s8",  0.34, 0.68, 7.0),   # おなかは土と種
    ("s9",  0.24, 0.66, 6.0),   # 芽が出る
    ("end", 0.00, 0.48, 7.5),   # 結び
]


def resolve_cuts(tl):
    """割合指定の SHORTS_CUTS を、実時間の (開始秒, 終了秒) に変換する。"""
    out = []
    for scene, a, b, cap in SHORTS_CUTS:
        s = tl["scenes"][scene]
        dur = s["end"] - s["start"]
        t0 = s["start"] + dur * a
        t1 = min(s["start"] + dur * b, t0 + cap)
        out.append((t0, t1))
    return out


def launch(pw, tl, w, h):
    browser = pw.chromium.launch(executable_path=CHROME,
                                 args=["--force-device-scale-factor=1",
                                       "--disable-lcd-text", "--hide-scrollbars"])
    page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
    page.goto("file://" + os.path.join(ROOT, "src", "movie.html"))
    page.wait_for_function("typeof window.__seek === 'function'")
    page.evaluate("tl => setTimeline(tl)", tl)
    return browser, page


def ffmpeg_proc(w, h, fps, audio, out_path, atrim=None):
    os.makedirs(OUT, exist_ok=True)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", str(fps), "-i", "-"]
    if atrim:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={atrim}"]
    else:
        cmd += ["-i", audio]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", "-shortest", out_path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shorts", action="store_true")
    args = ap.parse_args()

    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    fps = tl["fps"]
    audio = os.path.join(BUILD, "audio.wav")

    if args.shorts:
        w, h, out = 1080, 1920, os.path.join(OUT, "kokohore_shiro_shorts.mp4")
        cuts = resolve_cuts(tl)
        times = []
        for a, b in cuts:
            n = int((b - a) * fps)
            times += [a + i / fps for i in range(n)]
        # 音は本編から同じ区間を切り出して連結する
        seg_files = []
        for i, (a, b) in enumerate(cuts):
            f = os.path.join(BUILD, f"sa{i}.wav")
            subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                            "-i", audio, "-ss", str(a), "-to", str(b), f], check=True)
            seg_files.append(f)
        lst = os.path.join(BUILD, "salist.txt")
        with open(lst, "w") as f:
            for s in seg_files:
                f.write(f"file '{s}'\n")
        audio = os.path.join(BUILD, "shorts_audio.wav")
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                        "-f", "concat", "-safe", "0", "-i", lst, audio], check=True)
    else:
        w, h, out = 1920, 1080, os.path.join(OUT, "kokohore_shiro.mp4")
        times = [i / fps for i in range(int(tl["total"] * fps))]

    print(f"{out}  {w}x{h}  {len(times)} フレーム ({len(times)/fps:.1f}秒)")
    with sync_playwright() as pw:
        # 縦型は 1920x1080 の画をセンター基準で切り出す（CSS で拡大＋クリップ）
        browser, page = launch(pw, tl, w, h)
        if args.shorts:
            # 16:9 の絵を 1.5 倍に拡大して左右を少し切り、上下の余白は
            # ブランド色の背景＋タイトルで埋める（全部を切ると画がもたない）
            page.add_style_tag(content="""
              body { background:#2b2545; }
              #stage { width:1080px; height:1920px;
                       background:linear-gradient(160deg,#3b3566 0%,#2b2545 60%,#1f1b36 100%); }
              #art { position:absolute; left:50%; top:50%; width:1620px; height:911px;
                     transform:translate(-50%,-50%); }
              #scrim { bottom:505px; height:300px; }
              #sub { bottom:360px; font-size:54px; padding:0 50px; }
              #shortsTitle { position:absolute; top:150px; left:0; right:0; text-align:center;
                     font-family:"Rounded Mplus 1c",sans-serif; font-weight:800;
                     font-size:96px; color:#fff; letter-spacing:2px; }
              #shortsSub { position:absolute; top:270px; left:0; right:0; text-align:center;
                     font-family:"Rounded Mplus 1c",sans-serif; font-weight:800;
                     font-size:42px; color:#ffe6a8; }
              #shortsFoot { position:absolute; bottom:150px; left:0; right:0; text-align:center;
                     font-family:"Rounded Mplus 1c",sans-serif; font-weight:800;
                     font-size:44px; color:#c9c4e6; }
            """)
            page.evaluate("""() => {
              const mk=(id,txt)=>{const d=document.createElement('div');d.id=id;
                d.textContent=txt;document.getElementById('stage').appendChild(d);};
              mk('shortsTitle','ここほれ、シロ！');
              mk('shortsSub','〜 はなさかじいさん 2026 〜');
              mk('shortsFoot','本編は チャンネルから');
            }""")
        proc = ffmpeg_proc(w, h, fps, audio, out)
        for i, t in enumerate(times):
            page.evaluate("t => window.__seek(t)", t)
            proc.stdin.write(page.screenshot(type="jpeg", quality=94))
            if i % 480 == 0:
                print(f"  {i}/{len(times)}", flush=True)
        proc.stdin.close()
        proc.wait()
        browser.close()
    print("完了:", out, f"{os.path.getsize(out)/1e6:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
