# ここほれ、シロ！ 〜はなさかじいさん 2026〜

日本の昔ばなし『はなさかじいさん』を、いまの子ども（5〜12歳）に届く形に作り変えた
アニメーション動画の制作リポジトリです。**人物・時代設定は現代に置き換え、
昔の人が伝えようとした芯（見返りを求めない優しさ／欲では実らない／命は巡る）はそのまま**にしています。

## 成果物

| ファイル | 内容 |
|---|---|
| `out/kokohore_shiro.mp4` | 本編 16:9 / 1920×1080 / 24fps / 約 4分12秒 |
| `out/kokohore_shiro_shorts.mp4` | 縦型 9:16 / 1080×1920 / 約 60秒 |
| `out/kokohore_shiro.ja.srt` | 日本語字幕（ひらがな＋分かち書き） |
| `out/thumbnail.png` | サムネイル 1280×720 |
| `publish/youtube.md` | タイトル・説明文・タグ・公開設定 |

## 作り方

すべてコードから生成しています。素材の外部ダウンロードはありません
（フォントの M PLUS Rounded 1c のみ Google Fonts から取得）。

```
src/story.py          台本データ（セリフ・字幕・話者）— ここが唯一の情報源
src/build_audio.py    ナレーション(pyopenjtalk) + BGM + 効果音 → build/audio.wav, build/timeline.json
src/movie.html        フラット絵本風の SVG シーン。window.__seek(t) で時刻 t の絵を決定的に描く
src/build_video.py    Chromium で 1 コマずつ撮り、ffmpeg へ直接流して MP4 化
src/render_frames.py  --check で代表カットだけ書き出して絵づくりを確認する
src/build_subs.py     SRT 字幕
src/build_thumbnail.py サムネイル
```

### 実行

```bash
pip install pyopenjtalk numpy scipy playwright imageio-ffmpeg pillow
python3 src/build_audio.py
python3 src/build_video.py
python3 src/build_video.py --shorts
python3 src/build_subs.py
python3 src/build_thumbnail.py
```

音を先に作り、その実測長から `build/timeline.json` を組み立てて、映像はそれに従います。
だからセリフを書き換えると、絵の尺も字幕も自動で追従します。

## ドキュメント

- `story/script.md` — 脚本と、原作からの改変方針の対応表
- `story/reviews/` — 6 名によるレビューと 3 ラウンドの改訂記録
