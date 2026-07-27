"""ナレーション（pyopenjtalk）・BGM・効果音を合成して out/audio.wav と build/timeline.json を作る。

映像側は timeline.json を唯一の時間軸として読むので、音を先に作る。
"""
import json
import os
import sys

import numpy as np
import pyopenjtalk
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from story import BEATS, VOICES, SCENE_ORDER  # noqa: E402

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
os.makedirs(BUILD, exist_ok=True)


# ---------------------------------------------------------------- ナレーション
def synth_line(beat):
    v = VOICES[beat["speaker"]]
    x, sr = pyopenjtalk.tts(beat["tts"], speed=v["speed"], half_tone=v["tone"])
    x = np.asarray(x, dtype=np.float64)
    if sr != SR:  # 念のためのリサンプル
        n = int(len(x) * SR / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    peak = np.max(np.abs(x)) or 1.0
    x = x / peak * 0.85
    # 前後の無音を削る（pyopenjtalk は末尾に長い無音を残しがち）
    env = np.abs(x)
    win = int(0.01 * SR)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    idx = np.where(env > 0.012)[0]
    if len(idx):
        x = x[max(0, idx[0] - int(0.04 * SR)): idx[-1] + int(0.10 * SR)]
    # 軽いフェード
    f = int(0.012 * SR)
    x[:f] *= np.linspace(0, 1, f)
    x[-f:] *= np.linspace(1, 0, f)
    return x


# ---------------------------------------------------------------- 楽器
def adsr(n, a, d, s, r):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    a, d, r = min(a, n), min(d, n), min(r, n)
    sus = max(0, n - a - d - r)
    return np.concatenate([
        np.linspace(0, 1, a),
        np.linspace(1, s, d),
        np.full(sus, s),
        np.linspace(s, 0, r),
    ])[:n]


def note_box(f, dur, vel):
    """オルゴール/マリンバ系。倍音が速く減衰する。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for k, (mult, amp, dec) in enumerate([(1, 1.0, 3.0), (2.0, 0.32, 5.5),
                                          (3.01, 0.16, 8.0), (4.7, 0.07, 12.0)]):
        y += amp * np.sin(2 * np.pi * f * mult * t) * np.exp(-dec * t)
    y *= adsr(n, 0.004, 0.05, 0.55, min(dur * 0.6, 0.5))
    return y * vel


def note_pad(f, dur, vel):
    """やわらかいパッド。和音の土台。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for det in (-0.006, 0.0, 0.007):
        y += np.sin(2 * np.pi * f * (1 + det) * t)
    y += 0.25 * np.sin(2 * np.pi * f * 2 * t)
    y /= 3.5
    # 一次ローパス
    a = 0.10
    out = np.zeros(n)
    acc = 0.0
    for i in range(0, n, 1):
        acc += a * (y[i] - acc)
        out[i] = acc
    out *= adsr(n, 0.45, 0.3, 0.75, dur * 0.5)
    return out * vel


def note_pluck(f, dur, vel):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2 * t)
         + 0.2 * np.sin(2 * np.pi * f * 3 * t))
    y *= np.exp(-6.0 * t)
    y *= adsr(n, 0.003, 0.02, 0.4, dur * 0.5)
    return y / 1.6 * vel


def note_bass(f, dur, vel):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(2 * np.pi * f * 2 * t)
    y *= adsr(n, 0.02, 0.15, 0.6, dur * 0.4)
    return y / 1.3 * vel


INSTR = {"box": note_box, "pad": note_pad, "pluck": note_pluck, "bass": note_bass}


def hz(name):
    """'C4' 'F#3' -> Hz"""
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    p = base[name[0]]
    i = 1
    while i < len(name) and name[i] in "#b":
        p += 1 if name[i] == "#" else -1
        i += 1
    octv = int(name[i:])
    return 440.0 * 2 ** ((p - 9) / 12 + (octv - 4))


# ---------------------------------------------------------------- 効果音
def se_boot():
    """ピピッ（起動）"""
    out = np.zeros(int(0.75 * SR))
    for i, (st, f) in enumerate([(0.0, 880), (0.16, 1174), (0.32, 1567)]):
        n = int(0.11 * SR)
        t = np.arange(n) / SR
        y = 0.5 * np.sign(np.sin(2 * np.pi * f * t)) * np.exp(-16 * t)
        y += 0.5 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-22 * t)
        s = int(st * SR)
        out[s:s + n] += y * 0.55
    return out


def se_dig():
    """ざっ、ざっ（掘る）"""
    out = np.zeros(int(1.5 * SR))
    rng = np.random.default_rng(7)
    for k in range(5):
        n = int(0.14 * SR)
        t = np.arange(n) / SR
        y = rng.normal(0, 1, n) * np.exp(-18 * t)
        # ざらつきを落とすため軽く平滑化
        y = np.convolve(y, np.ones(9) / 9, mode="same")
        s = int((0.05 + k * 0.27) * SR)
        out[s:s + n] += y * 0.45
    return out


def se_crash():
    """ガシャン（落下）"""
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(11)
    y = rng.normal(0, 1, n) * np.exp(-9 * t) * 0.5
    for f, d in [(180, 4.0), (523, 3.0), (784, 3.6), (1245, 4.5), (1860, 6.0)]:
        y += 0.20 * np.sin(2 * np.pi * f * t) * np.exp(-d * t)
    y *= adsr(n, 0.001, 0.02, 0.5, 1.0)
    return y * 0.85


def se_bloom():
    """花がひらく（きらきら上昇）"""
    n = int(3.0 * SR)
    out = np.zeros(n)
    scale = ["C5", "D5", "E5", "G5", "A5", "C6", "D6", "E6", "G6", "A6", "C7"]
    for i, nm in enumerate(scale):
        st = int(i * 0.13 * SR)
        y = note_box(hz(nm), 1.6, 0.42)
        out[st:st + len(y)] += y[:max(0, n - st)]
    return out


def se_sparkle():
    n = int(1.2 * SR)
    out = np.zeros(n)
    for i, nm in enumerate(["G5", "C6", "E6"]):
        st = int(i * 0.09 * SR)
        y = note_box(hz(nm), 0.9, 0.32)
        out[st:st + len(y)] += y[:max(0, n - st)]
    return out


SE = {"boot": se_boot, "dig": se_dig, "crash": se_crash,
      "bloom": se_bloom, "sparkle": se_sparkle}


# ---------------------------------------------------------------- BGM
# シーンごとの気分。(コード進行, 主旋律の音階, 楽器, 音量, 1小節の秒数)
MOODS = {
    "s1":  dict(chords=[("A3", "min"), ("F3", "maj"), ("C4", "maj"), ("G3", "maj")],
                mel=["A4", None, "C5", None, "B4", None, "A4", None],
                vol=0.16, bar=4.0, lead="box"),
    "s2":  dict(chords=[("F3", "maj"), ("G3", "maj"), ("A3", "min"), ("A3", "min")],
                mel=["C5", "D5", "E5", None, "D5", "C5", None, None],
                vol=0.17, bar=3.6, lead="box"),
    "s3":  dict(chords=[("C4", "maj"), ("G3", "maj"), ("A3", "min"), ("F3", "maj")],
                mel=["E5", "G5", "A5", None, "G5", "E5", "D5", None],
                vol=0.19, bar=3.4, lead="box"),
    "s4":  dict(chords=[("C4", "maj"), ("F3", "maj"), ("G3", "maj"), ("C4", "maj")],
                mel=["G5", "A5", "C6", "A5", "G5", "E5", "G5", None],
                vol=0.20, bar=3.0, lead="pluck"),
    "s5":  dict(chords=[("D4", "min"), ("D4", "min"), ("Bb3", "maj"), ("A3", "maj")],
                mel=["D5", "F5", "E5", None, "D5", None, "C#5", None],
                vol=0.17, bar=3.2, lead="pluck"),
    "s6":  dict(chords=[("D4", "min"), ("Bb3", "maj"), ("F3", "maj"), ("A3", "maj")],
                mel=["A4", None, "F4", None, "D4", None, None, None],
                vol=0.14, bar=4.4, lead="pad"),
    "s7":  dict(chords=[("A3", "min"), ("F3", "maj"), ("C4", "maj"), ("E3", "maj")],
                mel=["A4", None, None, "G4", None, "E4", None, None],
                vol=0.13, bar=5.0, lead="box"),
    "s8":  dict(chords=[("F3", "maj"), ("C4", "maj"), ("G3", "maj"), ("A3", "min")],
                mel=["C5", "E5", "F5", None, "G5", None, "E5", None],
                vol=0.18, bar=4.0, lead="box"),
    "s9":  dict(chords=[("C4", "maj"), ("G3", "maj"), ("A3", "min"), ("F3", "maj")],
                mel=["G5", "C6", "B5", "A5", "G5", "E5", "F5", "G5"],
                vol=0.23, bar=2.8, lead="box"),
    "s10": dict(chords=[("F3", "maj"), ("G3", "maj"), ("C4", "maj"), ("A3", "min")],
                mel=["A5", "G5", "E5", None, "F5", "G5", None, None],
                vol=0.20, bar=3.4, lead="box"),
    "end": dict(chords=[("C4", "maj"), ("F3", "maj"), ("G3", "maj"), ("C4", "maj")],
                mel=["E5", "G5", "C6", None, "G5", "E5", "C5", None],
                vol=0.21, bar=3.6, lead="box"),
}

TRIAD = {"maj": (0, 4, 7), "min": (0, 3, 7)}


def transpose(n, semis):
    return n * 2 ** (semis / 12)


def render_bgm(mood, dur, seed=0):
    n = int(dur * SR)
    out = np.zeros(n + SR)
    bar = mood["bar"]
    nbars = int(np.ceil(dur / bar)) + 1
    for b in range(nbars):
        t0 = b * bar
        root_name, quality = mood["chords"][b % len(mood["chords"])]
        root = hz(root_name)
        # ベース
        y = note_bass(root / 2, bar * 0.92, 0.30)
        s = int(t0 * SR)
        out[s:s + len(y)] += y[:max(0, len(out) - s)]
        # 和音パッド
        for iv in TRIAD[quality]:
            y = note_pad(transpose(root, iv), bar * 0.95, 0.15)
            out[s:s + len(y)] += y[:max(0, len(out) - s)]
        # 主旋律（8分割）
        step = bar / 8
        for i, nm in enumerate(mood["mel"]):
            if nm is None:
                continue
            st = int((t0 + i * step) * SR)
            y = INSTR[mood["lead"]](hz(nm), step * 1.9, 0.30)
            out[st:st + len(y)] += y[:max(0, len(out) - st)]
    out = out[:n]
    return out * mood["vol"]


# ---------------------------------------------------------------- 組み立て
def main():
    print("ナレーション合成中…")
    cursor = 0.0
    events = []          # 字幕・映像用
    narration = []       # (start_sample, wav)
    scene_bounds = {}

    for b in BEATS:
        sc = b["scene"]
        if b["kind"] == "line":
            x = synth_line(b)
            dur = len(x) / SR
            narration.append((int(cursor * SR), x))
            events.append({"kind": "line", "scene": sc, "speaker": b["speaker"],
                           "start": round(cursor, 3),
                           "end": round(cursor + dur, 3),
                           "sub": b["sub"]})
            cursor += dur + b["pad"]
        else:
            events.append({"kind": "hold", "scene": sc,
                           "start": round(cursor, 3),
                           "end": round(cursor + b["dur"], 3),
                           "sub": b.get("sub")})
            cursor += b["dur"]
        e = scene_bounds.setdefault(sc, [events[-1]["start"], 0.0])
        e[1] = round(cursor, 3)

    total = cursor
    print(f"  尺: {total:.1f} 秒 ({total/60:.2f} 分) / {len(events)} ビート")

    n_total = int(np.ceil(total * SR)) + SR
    voice = np.zeros(n_total)
    for s, x in narration:
        voice[s:s + len(x)] += x

    # BGM をシーンごとに敷いてクロスフェード
    print("BGM 合成中…")
    bgm = np.zeros(n_total)
    xf = int(1.2 * SR)
    for sc in SCENE_ORDER:
        if sc not in scene_bounds:
            continue
        st, en = scene_bounds[sc]
        seg = render_bgm(MOODS[sc], en - st + 1.2)
        s = int(st * SR)
        f = min(xf, len(seg) // 2)
        seg[:f] *= np.linspace(0, 1, f)
        seg[-f:] *= np.linspace(1, 0, f)
        bgm[s:s + len(seg)] += seg[:max(0, n_total - s)]

    # S6の「ガシャン」直後は無音にして、痛みを間で見せる
    crash_ev = next(e for e in events if e["scene"] == "s6" and e["sub"] == "ガシャン。")
    hush_s, hush_e = int(crash_ev["start"] * SR), int((crash_ev["end"] + 6.0) * SR)
    ramp = np.ones(n_total)
    ramp[hush_s:hush_e] = 0.0
    g = int(0.6 * SR)
    ramp[max(0, hush_s - g):hush_s] = np.linspace(1, 0, min(g, hush_s))
    ramp[hush_e:hush_e + int(2.5 * SR)] = np.linspace(0, 1, int(2.5 * SR))[:max(0, n_total - hush_e)]
    bgm *= ramp

    # ナレーション中は BGM を下げる（ダッキング）
    env = np.abs(voice)
    w = int(0.25 * SR)
    env = np.convolve(env, np.ones(w) / w, mode="same")
    duck = 1.0 - 0.62 * np.clip(env / 0.18, 0, 1)
    bgm *= duck

    # 効果音
    print("効果音を配置中…")
    se_track = np.zeros(n_total)

    def place(name, at, gain=1.0):
        y = SE[name]() * gain
        s = int(at * SR)
        se_track[s:s + len(y)] += y[:max(0, n_total - s)]

    def ev(scene, needle):
        return next(e for e in events
                    if e["scene"] == scene and e["sub"] and needle in e["sub"])

    place("boot", ev("s3", "あさ。ピピッ")["start"] + 0.35, 1.0)
    place("dig", ev("s4", "いきなり ほりはじめ")["end"] + 0.15, 0.9)
    place("sparkle", ev("s4", "小さな たねが")["end"] - 0.4, 0.8)
    place("dig", ev("s6", "あきかんと")["end"] + 0.1, 0.7)
    place("crash", crash_ev["start"] - 0.05, 1.0)
    place("bloom", ev("s9", "つぼみから")["end"] - 0.2, 1.0)
    place("sparkle", ev("s9", "花で いっぱいに")["start"], 0.6)

    mix = voice * 1.0 + bgm + se_track * 0.75
    peak = np.max(np.abs(mix))
    mix = mix / peak * 0.92
    # やさしいリミッター代わりのソフトクリップ
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)

    stereo = np.stack([mix, mix], axis=1)
    out_wav = os.path.join(BUILD, "audio.wav")
    wavfile.write(out_wav, SR, (stereo * 32767).astype(np.int16))
    print("書き出し:", out_wav)

    timeline = {
        "total": round(total, 3),
        "fps": 24,
        "events": events,
        "scenes": {k: {"start": v[0], "end": v[1]} for k, v in scene_bounds.items()},
        "order": SCENE_ORDER,
    }
    with open(os.path.join(BUILD, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=1)
    print("書き出し: build/timeline.json")
    for sc in SCENE_ORDER:
        if sc in scene_bounds:
            a, b2 = scene_bounds[sc]
            print(f"  {sc:4s} {a:7.2f} → {b2:7.2f}  ({b2-a:5.2f}s)")


if __name__ == "__main__":
    main()
