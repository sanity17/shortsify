# 🎬 YouTube Shorts Creator — Setup & Usage Guide

## What It Does
Downloads viral clips → cuts funniest moments → crops to 9:16 vertical →
adds meme-style captions → exports ready-to-upload YouTube Shorts MP4s.
Bonus: auto-builds a Top-5 compilation video from all clips.

---

## Step 1 — Install System Tools

### macOS (Homebrew)
```bash
brew install ffmpeg yt-dlp
```

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install ffmpeg -y
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
     -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp
```

### Windows (PowerShell, as Admin)
```powershell
# Install Scoop first: https://scoop.sh
scoop install ffmpeg yt-dlp
```

Verify:
```bash
ffmpeg -version
yt-dlp --version
```

---

## Step 2 — Python Environment

```bash
# Create venv (recommended)
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows

# Install Python packages
pip install moviepy pillow numpy yt-dlp
```

> **Optional — AI auto-captions (Whisper):**
> ```bash
> pip install openai-whisper
> ```
> (Whisper integration can be added by calling `whisper <clip.mp4>` and
>  piping the SRT into ffmpeg's subtitle filter.)

---

## Step 3 — Project Layout

After running the script once, this structure is created automatically:

```
project/
├── shorts_creator.py   ← the main script
├── downloads/          ← raw downloaded videos
├── clips/              ← intermediate cut/vertical clips
├── output/             ← ✅ FINAL YouTube Shorts go here
│   ├── video1.mp4
│   ├── video2.mp4
│   └── TOP5_compilation.mp4
└── fonts/              ← Roboto-Bold.ttf (auto-downloaded)
```

---

## Step 4 — Run It

### Default (uses the 5 hardcoded examples)
```bash
python3 shorts_creator.py
```

### Add a custom clip via CLI
```bash
python3 shorts_creator.py \
    "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" \
    12.5 \
    27.0 \
    "WAIT FOR IT 😂" \
    my_funny_clip
```
Arguments: `<url> <start_sec> <end_sec> <caption_text> <output_name>`

---

## Step 5 — Customize the Clip List

Edit the `CLIPS_LIST` section in `shorts_creator.py`:

```python
CLIPS_LIST: list[ClipSpec] = [
    ClipSpec(
        url     = "https://www.youtube.com/watch?v=YOUR_VIDEO",
        start   = 10.0,    # start time in seconds
        end     = 23.0,    # end time in seconds (5–15 sec clips only)
        caption = "THIS IS INSANE 😂🔥",
        title   = "my_clip_name",  # used for filenames
        zoom    = 1.15,    # subtle zoom-in (1.0 = none, 1.3 = big)
    ),
    # add more ClipSpec(...) entries here
]
```

---

## Step 6 — Download Your Shorts

After the script finishes, collect everything from the `output/` folder:

```bash
ls -lh output/
# video1.mp4    → Short #1
# video2.mp4    → Short #2
# ...
# TOP5_compilation.mp4  → Bonus compilation
```

Upload directly to YouTube → **Create → Upload Video → select Shorts format**.

---

## Configuration Reference

| Variable            | Default    | Description                              |
|---------------------|------------|------------------------------------------|
| `SHORTS_W / H`      | 1080×1920  | YouTube Shorts resolution                |
| `CAPTION_FONT_SIZE` | 72         | Caption text size in pixels              |
| `CAPTION_STROKE_W`  | 6          | Black outline thickness                  |
| `CAPTION_POSITION`  | 0.72       | Vertical position (0=top, 1=bottom)      |
| `TARGET_FPS`        | 30         | Output frame rate                        |
| `CRF`               | 23         | Video quality (18=best, 28=smallest)     |
| `PRESET`            | medium     | ffmpeg speed/quality tradeoff            |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `yt-dlp` rate-limited / blocked | Add `--cookies-from-browser chrome` to yt-dlp cmd in script |
| `zoompan` makes video slow | Reduce clip `zoom` to `1.05` or `1.0` |
| Captions look bad | Increase `CAPTION_FONT_SIZE` or change `CAPTION_POSITION` |
| Audio out of sync | Change `CRF` from `23` → `18` for higher quality |
| `moviepy` ImportError | `pip install moviepy==1.0.3` (stable version) |
| Font not loading | Place `Roboto-Bold.ttf` manually in `fonts/` folder |

---

## Example URLs (Safe Public Domain / Well-Known)

```
# Rick Astley - Never Gonna Give You Up
https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Me at the zoo (first YouTube video)
https://www.youtube.com/watch?v=jNQXAC9IVRw

# Charlie Bit My Finger
https://www.youtube.com/watch?v=FtutLA63Cp8

# Evolution of Dance
https://www.youtube.com/watch?v=e_DqV1xdf-Y
```

> ⚠️ **Copyright notice:** Only use clips you have rights to, or
> clips under Creative Commons license. Use `yt-dlp --list-formats <url>`
> to inspect available quality options.

---

## Optional: Auto-Captions with Whisper

```bash
pip install openai-whisper

# Generate SRT for a clip:
whisper clips/my_clip_raw.mp4 --model base --output_format srt

# Then burn into video with ffmpeg:
ffmpeg -i clips/my_clip_vertical.mp4 \
       -vf "subtitles=clips/my_clip_raw.srt:force_style='FontSize=24,PrimaryColour=&Hffffff&'" \
       output/video1.mp4
```
