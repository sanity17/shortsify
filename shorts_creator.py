#!/usr/bin/env python3
"""
YouTube Shorts Creator
======================
Automatically downloads viral clips, cuts funniest moments,
converts to vertical 9:16 format, adds captions, and exports
ready-to-upload YouTube Shorts MP4s.

Author: Senior Python Developer
Requirements: yt-dlp, ffmpeg, moviepy, pillow, numpy
"""

import os
import sys
import json
import subprocess
import shutil
import textwrap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import time

# ─────────────────────────────────────────────
#  DEPENDENCY CHECK
# ─────────────────────────────────────────────
def check_dependencies():
    missing = []
    for cmd in ["ffmpeg", "ffprobe", "yt-dlp"]:
        if not shutil.which(cmd):
            missing.append(cmd)
    if missing:
        print(f"[ERROR] Missing system tools: {', '.join(missing)}")
        print("  Install with: brew install ffmpeg yt-dlp  (macOS)")
        print("  Or:           sudo apt install ffmpeg && pip install yt-dlp  (Linux)")
        sys.exit(1)
    try:
        from moviepy.editor import VideoFileClip
    except ImportError:
        print("[ERROR] moviepy not installed. Run: pip install moviepy")
        sys.exit(1)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[ERROR] pillow not installed. Run: pip install pillow")
        sys.exit(1)

check_dependencies()

# ─────────────────────────────────────────────
#  IMPORTS (after dep check)
# ─────────────────────────────────────────────
import numpy as np
from moviepy.editor import (
    VideoFileClip, CompositeVideoClip, ImageClip,
    concatenate_videoclips, ColorClip, TextClip
)
from PIL import Image, ImageDraw, ImageFont
import urllib.request

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.resolve()
DOWNLOADS    = BASE_DIR / "downloads"
CLIPS        = BASE_DIR / "clips"
OUTPUT       = BASE_DIR / "output"
FONTS_DIR    = BASE_DIR / "fonts"

# YouTube Shorts target resolution
SHORTS_W = 1080
SHORTS_H = 1920

# Caption style
CAPTION_FONT_SIZE   = 72          # px inside PIL
CAPTION_STROKE_W    = 6           # outline width
CAPTION_COLOR       = (255, 255, 255)
CAPTION_STROKE      = (0, 0, 0)
CAPTION_BG_ALPHA    = 180         # 0-255
CAPTION_POSITION    = 0.72        # vertical fraction from top

# Video quality
TARGET_FPS    = 30
CRF           = 23                # ffmpeg CRF (lower = better quality)
PRESET        = "medium"          # ffmpeg preset

# ─────────────────────────────────────────────
#  CLIP DATA MODEL
# ─────────────────────────────────────────────
@dataclass
class ClipSpec:
    url:        str
    start:      float          # seconds
    end:        float          # seconds
    caption:    str = ""       # meme text shown on screen
    title:      str = "clip"   # used for filenames
    zoom:       float = 1.15   # subtle zoom-in factor

    @property
    def duration(self) -> float:
        return self.end - self.start

    def validate(self):
        if self.duration < 5 or self.duration > 15:
            raise ValueError(
                f"Clip '{self.title}' is {self.duration:.1f}s — must be 5–15 s"
            )

# ─────────────────────────────────────────────
#  HARDCODED EXAMPLE CLIPS  ← edit these!
# ─────────────────────────────────────────────
CLIPS_LIST: list[ClipSpec] = [
    ClipSpec(
        url     = "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        start   = 14.0,
        end     = 26.0,
        caption = "NOBODY EXPECTED THIS 😂",
        title   = "rickroll_moment",
        zoom    = 1.1,
    ),
    ClipSpec(
        url     = "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        start   = 0.0,
        end     = 13.0,
        caption = "THE FIRST EVER YOUTUBE VIDEO 🐘",
        title   = "first_youtube_video",
        zoom    = 1.2,
    ),
    ClipSpec(
        url     = "https://www.youtube.com/watch?v=FtutLA63Cp8",
        start   = 5.0,
        end     = 18.0,
        caption = "CHARLIE BIT MY FINGER 😱",
        title   = "charlie_bit_finger",
        zoom    = 1.15,
    ),
    ClipSpec(
        url     = "https://www.youtube.com/watch?v=e_DqV1xdf-Y",
        start   = 0.0,
        end     = 12.0,
        caption = "EVOLUTION OF DANCE 🕺",
        title   = "evolution_of_dance",
        zoom    = 1.1,
    ),
    ClipSpec(
        url     = "https://www.youtube.com/watch?v=KmtzQCSh6xk",
        start   = 0.0,
        end     = 14.0,
        caption = "NUMA NUMA GUY GOES VIRAL 🎵",
        title   = "numa_numa",
        zoom    = 1.2,
    ),
]

# ─────────────────────────────────────────────
#  DIRECTORY SETUP
# ─────────────────────────────────────────────
def setup_dirs():
    for d in [DOWNLOADS, CLIPS, OUTPUT, FONTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    print(f"[+] Directories ready: downloads/ clips/ output/ fonts/")

# ─────────────────────────────────────────────
#  FONT HELPER
# ─────────────────────────────────────────────
FONT_URL = (
    "https://github.com/googlefonts/roboto/raw/main/src/hinted/"
    "Roboto-Bold.ttf"
)

def get_font(size: int = CAPTION_FONT_SIZE) -> ImageFont.FreeTypeFont:
    """Return a bold font, downloading one if needed."""
    font_path = FONTS_DIR / "Roboto-Bold.ttf"
    if not font_path.exists():
        print("[~] Downloading Roboto-Bold font …")
        try:
            urllib.request.urlretrieve(FONT_URL, font_path)
            print("[+] Font downloaded.")
        except Exception:
            print("[!] Could not download font — using PIL default.")
            return ImageFont.load_default()
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default()

# ─────────────────────────────────────────────
#  1. DOWNLOAD
# ─────────────────────────────────────────────
def download_video(spec: ClipSpec) -> Optional[Path]:
    """Download best quality video using yt-dlp. Returns local path."""
    out_tmpl = str(DOWNLOADS / f"{spec.title}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", out_tmpl,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        spec.url,
    ]
    print(f"  [↓] Downloading '{spec.title}' …")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [!] yt-dlp failed for '{spec.title}':\n{result.stderr.strip()}")
        return None

    # Find the downloaded file
    for ext in ["mp4", "mkv", "webm", "avi"]:
        p = DOWNLOADS / f"{spec.title}.{ext}"
        if p.exists():
            print(f"  [✓] Downloaded → {p.name}")
            return p
    print(f"  [!] Downloaded file not found for '{spec.title}'")
    return None

# ─────────────────────────────────────────────
#  2. CUT CLIP
# ─────────────────────────────────────────────
def cut_clip(src: Path, spec: ClipSpec) -> Optional[Path]:
    """Cut start–end using ffmpeg (lossless stream copy first, then re-encode)."""
    out = CLIPS / f"{spec.title}_raw.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(spec.start),
        "-i", str(src),
        "-t", str(spec.duration),
        "-c:v", "libx264", "-crf", str(CRF), "-preset", PRESET,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-loglevel", "error",
        str(out),
    ]
    print(f"  [✂] Cutting {spec.start}s – {spec.end}s …")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out.exists():
        print(f"  [!] ffmpeg cut failed:\n{result.stderr.strip()}")
        return None
    print(f"  [✓] Raw clip → {out.name}")
    return out

# ─────────────────────────────────────────────
#  3. CONVERT TO VERTICAL 9:16 WITH ZOOM
# ─────────────────────────────────────────────
def to_vertical(src: Path, spec: ClipSpec) -> Optional[Path]:
    """
    Crop + scale to 1080×1920 with a subtle zoom-in effect.
    Strategy:
      - Scale the video so its height fills 1920 (or width fills 1080)
      - Center-crop to 1080×1920
      - Apply a slow zoom-in (scale from zoom_factor back to 1.0 over duration)
    """
    out = CLIPS / f"{spec.title}_vertical.mp4"

    # Build a complex ffmpeg filter for zoom + crop
    # zoompan: z=zoom expression, x/y=pan expression, d=frames, fps=FPS
    # Then scale to final size
    duration   = spec.duration
    fps        = TARGET_FPS
    total_f    = int(duration * fps)
    zoom_start = spec.zoom          # e.g. 1.15
    zoom_end   = 1.0

    # ffmpeg zoompan: zoom expression interpolated over frames
    # z = 'if(lte(on,1),{zoom_start}, zoom - ({zoom_start}-{zoom_end})/{total_f})'
    zoom_expr = (
        f"if(lte(on,1),{zoom_start},"
        f"zoom-({zoom_start}-{zoom_end})/{total_f})"
    )

    vf = (
        # 1. Scale keeping aspect, ensuring both dims ≥ target*zoom_start
        f"scale='if(gt(iw/ih,{SHORTS_W}/{SHORTS_H}),"
        f"-2,{int(SHORTS_W*zoom_start)})':"
        f"'if(gt(iw/ih,{SHORTS_W}/{SHORTS_H}),{int(SHORTS_H*zoom_start)},-2)',"
        # 2. Pad to exact dimensions in case rounding mismatches
        f"pad={int(SHORTS_W*zoom_start)}:{int(SHORTS_H*zoom_start)}:"
        f"(ow-iw)/2:(oh-ih)/2,"
        # 3. Zoom-pan effect
        f"zoompan=z='{zoom_expr}':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={total_f}:fps={fps}:s={SHORTS_W}x{SHORTS_H},"
        # 4. Final safety crop
        f"crop={SHORTS_W}:{SHORTS_H}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(CRF), "-preset", PRESET,
        "-c:a", "aac", "-b:a", "192k",
        "-r", str(fps),
        "-movflags", "+faststart",
        "-loglevel", "error",
        str(out),
    ]
    print(f"  [↕] Converting to 9:16 vertical …")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out.exists():
        print(f"  [!] Vertical conversion failed:\n{result.stderr.strip()}")
        # Fallback: simple crop without zoompan
        return to_vertical_simple(src, spec)
    print(f"  [✓] Vertical → {out.name}")
    return out

def to_vertical_simple(src: Path, spec: ClipSpec) -> Optional[Path]:
    """Fallback: plain scale + center crop to 9:16."""
    out = CLIPS / f"{spec.title}_vertical.mp4"
    vf = (
        f"scale='if(gt(iw/ih,{SHORTS_W}/{SHORTS_H}),-2,{SHORTS_W})':"
        f"'if(gt(iw/ih,{SHORTS_W}/{SHORTS_H}),{SHORTS_H},-2)',"
        f"crop={SHORTS_W}:{SHORTS_H}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(CRF), "-preset", PRESET,
        "-c:a", "aac", "-b:a", "192k",
        "-r", str(TARGET_FPS),
        "-movflags", "+faststart",
        "-loglevel", "error",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out.exists():
        print(f"  [!] Simple vertical fallback also failed:\n{result.stderr.strip()}")
        return None
    return out

# ─────────────────────────────────────────────
#  4. CAPTION FRAME GENERATOR (PIL)
# ─────────────────────────────────────────────
def make_caption_frame(
    text: str,
    width: int = SHORTS_W,
    font_size: int = CAPTION_FONT_SIZE,
    max_chars_per_line: int = 22,
) -> np.ndarray:
    """
    Render meme-style bold white text with black outline on a
    semi-transparent dark bar. Returns RGBA numpy array (H, W, 4).
    """
    font = get_font(font_size)

    # Word-wrap
    lines = textwrap.wrap(text, width=max_chars_per_line)
    if not lines:
        lines = [""]

    # Measure total text block height
    dummy_img = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    line_heights = []
    line_widths  = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    padding    = 30
    line_gap   = 12
    text_h     = sum(line_heights) + line_gap * (len(lines) - 1)
    bar_h      = text_h + padding * 2

    # Create transparent canvas (bar_h × width)
    img = Image.new("RGBA", (width, bar_h), (0, 0, 0, 0))

    # Semi-transparent background bar
    overlay = Image.new("RGBA", (width, bar_h), (0, 0, 0, CAPTION_BG_ALPHA))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Draw each line centered
    y_cursor = padding
    for i, line in enumerate(lines):
        x = (width - line_widths[i]) // 2
        # Stroke / outline
        for dx in range(-CAPTION_STROKE_W, CAPTION_STROKE_W + 1):
            for dy in range(-CAPTION_STROKE_W, CAPTION_STROKE_W + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text(
                    (x + dx, y_cursor + dy), line,
                    font=font, fill=(*CAPTION_STROKE, 255)
                )
        # Main text
        draw.text((x, y_cursor), line, font=font, fill=(*CAPTION_COLOR, 255))
        y_cursor += line_heights[i] + line_gap

    return np.array(img)

# ─────────────────────────────────────────────
#  5. BURN CAPTIONS ONTO VIDEO
# ─────────────────────────────────────────────
def burn_captions(src: Path, spec: ClipSpec) -> Optional[Path]:
    """
    Overlay meme-style caption using moviepy ImageClip.
    The caption appears for the full duration of the clip.
    """
    if not spec.caption:
        return src  # No caption needed, pass through

    out = CLIPS / f"{spec.title}_captioned.mp4"
    print(f"  [💬] Burning captions …")

    try:
        video = VideoFileClip(str(src))

        # Build caption image
        cap_arr  = make_caption_frame(spec.caption.upper(), width=SHORTS_W)
        cap_h, cap_w = cap_arr.shape[:2]

        # Position: CAPTION_POSITION fraction down the screen
        y_pos = int(SHORTS_H * CAPTION_POSITION)

        cap_clip = (
            ImageClip(cap_arr, ismask=False)
            .set_duration(video.duration)
            .set_position(("center", y_pos))
        )

        final = CompositeVideoClip(
            [video, cap_clip],
            size=(SHORTS_W, SHORTS_H)
        )
        final.write_videofile(
            str(out),
            fps=TARGET_FPS,
            codec="libx264",
            audio_codec="aac",
            bitrate="5000k",
            logger=None,
            temp_audiofile=str(CLIPS / f"{spec.title}_tmp_audio.m4a"),
        )
        video.close()
        final.close()

        print(f"  [✓] Captioned → {out.name}")
        return out

    except Exception as e:
        print(f"  [!] Caption burn failed ({e}), using uncaptioned clip.")
        return src

# ─────────────────────────────────────────────
#  6. EXPORT FINAL SHORT
# ─────────────────────────────────────────────
def export_short(src: Path, spec: ClipSpec, index: int) -> Optional[Path]:
    """Final export: copy/re-encode to /output/videoN.mp4"""
    out = OUTPUT / f"video{index}.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-c:v", "libx264", "-crf", str(CRF), "-preset", PRESET,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-loglevel", "error",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out.exists():
        print(f"  [!] Export failed:\n{result.stderr.strip()}")
        return None
    size_mb = out.stat().st_size / 1_048_576
    print(f"  [✓] Exported → {out.name}  ({size_mb:.1f} MB)")
    return out

# ─────────────────────────────────────────────
#  7. BONUS: TOP-5 COMPILATION
# ─────────────────────────────────────────────
def make_compilation(finished_clips: list[Path]) -> Optional[Path]:
    """
    Concatenate all finished Shorts into one vertical compilation video.
    Adds a simple title card between clips.
    """
    if len(finished_clips) < 2:
        print("[!] Need ≥2 clips for a compilation.")
        return None

    out = OUTPUT / "TOP5_compilation.mp4"
    print(f"\n[🎬] Building TOP-5 compilation from {len(finished_clips)} clips …")

    segments: list = []
    for i, clip_path in enumerate(finished_clips, 1):
        try:
            clip = VideoFileClip(str(clip_path))

            # Title card: "#1", "#2", …
            title_arr  = make_caption_frame(
                f"#{i}", width=SHORTS_W, font_size=180, max_chars_per_line=4
            )
            title_card = (
                ColorClip(size=(SHORTS_W, SHORTS_H), color=[0, 0, 0])
                .set_duration(1.5)
            )
            title_cap = (
                ImageClip(title_arr, ismask=False)
                .set_duration(1.5)
                .set_position(("center", "center"))
            )
            card = CompositeVideoClip([title_card, title_cap], size=(SHORTS_W, SHORTS_H))
            card = card.set_audio(None)

            segments.append(card)
            segments.append(clip)
        except Exception as e:
            print(f"  [!] Skipping clip {i} in compilation: {e}")

    if not segments:
        return None

    try:
        compilation = concatenate_videoclips(segments, method="compose")
        compilation.write_videofile(
            str(out),
            fps=TARGET_FPS,
            codec="libx264",
            audio_codec="aac",
            bitrate="5000k",
            logger=None,
        )
        compilation.close()
        size_mb = out.stat().st_size / 1_048_576
        print(f"[✓] Compilation → {out.name}  ({size_mb:.1f} MB)")
        return out
    except Exception as e:
        print(f"[!] Compilation failed: {e}")
        return None

# ─────────────────────────────────────────────
#  PIPELINE: process one ClipSpec end-to-end
# ─────────────────────────────────────────────
def process_clip(spec: ClipSpec, index: int) -> Optional[Path]:
    print(f"\n{'─'*55}")
    print(f"[{index}] Processing: {spec.title}")
    print(f"    URL:      {spec.url}")
    print(f"    Segment:  {spec.start}s – {spec.end}s  ({spec.duration:.1f}s)")
    print(f"    Caption:  {spec.caption or '(none)'}")

    try:
        spec.validate()
    except ValueError as e:
        print(f"  [!] Skipping — {e}")
        return None

    # Step 1: Download
    downloaded = download_video(spec)
    if not downloaded:
        return None

    # Step 2: Cut
    raw_clip = cut_clip(downloaded, spec)
    if not raw_clip:
        return None

    # Step 3: Vertical 9:16 + zoom
    vertical = to_vertical(raw_clip, spec)
    if not vertical:
        return None

    # Step 4: Captions
    captioned = burn_captions(vertical, spec)
    if not captioned:
        captioned = vertical  # fall back to no-caption

    # Step 5: Export
    final = export_short(captioned, spec, index)
    return final

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  🎬  YouTube Shorts Creator  🎬")
    print("=" * 55)

    setup_dirs()

    start_time    = time.time()
    finished      = []
    failed        = []

    for i, spec in enumerate(CLIPS_LIST, 1):
        result = process_clip(spec, i)
        if result:
            finished.append(result)
        else:
            failed.append(spec.title)

    # Compilation (bonus)
    if finished:
        make_compilation(finished)

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*55}")
    print(f"  Done in {elapsed:.0f}s")
    print(f"  ✅  {len(finished)} Shorts created → /output/")
    if failed:
        print(f"  ❌  {len(failed)} failed: {', '.join(failed)}")
    print(f"\n  Output files:")
    for p in sorted(OUTPUT.glob("*.mp4")):
        size_mb = p.stat().st_size / 1_048_576
        print(f"    {p.name:<30} {size_mb:>6.1f} MB")
    print("=" * 55)


# ─────────────────────────────────────────────
#  CLI ENTRY POINTS
# ─────────────────────────────────────────────
def add_custom_clip(
    url: str,
    start: float,
    end: float,
    caption: str = "",
    title: str = "custom",
    zoom: float = 1.15,
):
    """Convenience function: add your own clip at runtime."""
    spec = ClipSpec(
        url=url, start=start, end=end,
        caption=caption, title=title, zoom=zoom,
    )
    CLIPS_LIST.append(spec)


if __name__ == "__main__":
    # ── OPTIONAL: add extra clips from CLI args ──────────────
    # Example:
    #   python shorts_creator.py \
    #       "https://youtube.com/watch?v=XYZ" 10 22 "HILARIOUS 😂" my_clip
    if len(sys.argv) >= 4:
        cli_url     = sys.argv[1]
        cli_start   = float(sys.argv[2])
        cli_end     = float(sys.argv[3])
        cli_caption = sys.argv[4] if len(sys.argv) > 4 else ""
        cli_title   = sys.argv[5] if len(sys.argv) > 5 else "cli_clip"
        add_custom_clip(cli_url, cli_start, cli_end, cli_caption, cli_title)
        print(f"[+] Added CLI clip: {cli_title}  {cli_start}–{cli_end}s")

    main()
