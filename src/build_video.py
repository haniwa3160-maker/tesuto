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

# Shorts：本編のどこを 60 秒に切り出すか（開始秒, 終了秒）
SHORTS_CUTS = [
    ("s2",  17.8,  24.6),   # ゴミ置き場でシロを見つける
    ("s3",  47.0,  54.5),   # 目が光る／シロと名づける
    ("s4",  54.5,  62.0),   # ここほれワンワン
    ("s4",  70.0,  76.0),   # かんかんと たね
    ("s5", 100.0, 106.0),   # ケンタが借りる
    ("s6", 126.0, 136.8),   # こわれる
    ("s8", 163.0, 176.0),   # おなかは土と たね
    ("s9", 196.0, 204.9),   # 一面の花
    ("end", 240.0, 249.0),  # 結び＋タイトル
]


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
        times = []
        for _, a, b in SHORTS_CUTS:
            n = int((b - a) * fps)
            times += [a + i / fps for i in range(n)]
        # 音は本編から同じ区間を切り出して連結する
        seg_files = []
        for i, (_, a, b) in enumerate(SHORTS_CUTS):
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
            page.add_style_tag(content="""
              #stage { width:1080px; height:1920px; }
              #art { position:absolute; left:50%; top:50%; width:2880px; height:1620px;
                     transform:translate(-50%,-50%); }
              #sub { bottom:300px; font-size:62px; padding:0 60px; }
              #scrim { height:620px; }
            """)
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
