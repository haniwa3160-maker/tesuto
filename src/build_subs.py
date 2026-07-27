"""timeline.json から YouTube 用の字幕ファイル（SRT）を書き出す。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
OUT = os.path.join(ROOT, "out")


def ts(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60)
    s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        ms = 0; s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    lines, n = [], 0
    for e in tl["events"]:
        if e["kind"] != "line" or not e["sub"]:
            continue
        n += 1
        lines.append(f"{n}\n{ts(e['start'])} --> {ts(e['end'] + 0.45)}\n{e['sub']}\n")
    path = os.path.join(OUT, "kokohore_shiro.ja.srt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"{n} 件の字幕を書き出し: {path}")


if __name__ == "__main__":
    main()
