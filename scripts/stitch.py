r"""Step 6 of FoodFluencer: trim the clips to the style's cut rhythm and join them.

Usage (PowerShell, from the project folder):
    python scripts\stitch.py
    python scripts\stitch.py --no-overlays --soften-audio

Reads output\shots.json and output\clips\shot_NN.mp4. Writes output\final_<time>.mp4.
Needs ffmpeg on your PATH. Costs nothing: it all runs on your computer.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from analyze_character import OUTPUT_DIR

CLIPS_DIR = OUTPUT_DIR / "clips"
SIZES = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (960, 960), "4:3": (1024, 768),
         "3:4": (768, 1024), "21:9": (1344, 576)}
FONT_CANDIDATES = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
# Takes the thin edge off generated voices: a little low-mid body, a little less top-end fizz.
SOFTEN = "equalizer=f=180:t=h:width=250:g=3,equalizer=f=7000:t=h:width=4000:g=-4,"


def spoken_seconds(shot):
    """Rough time needed to say the shot's words: about 2.5 words a second plus a short pause."""
    words = len(((shot.get("dialogue") or "") + " " + (shot.get("voiceover") or "")).split())
    return words / 2.5 + 0.6 if words else 0.0


def clip_length(path, fallback):
    """The real length of a clip in seconds (needs ffprobe, which comes with ffmpeg)."""
    if not shutil.which("ffprobe"):
        return float(fallback)
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return float(fallback)


def find_font():
    return next((Path(p) for p in FONT_CANDIDATES if Path(p).is_file()), None)


def run(cmd, cwd):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("ffmpeg failed:\n" + result.stderr[-1500:])


def segment_command(src, out, width, height, trim, overlay_file, font_name, soften):
    fade_out = max(0.0, trim - 0.04)
    video = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
             f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30")
    if overlay_file:
        # Small caption in the lower third on a soft dark box, clear of the face.
        video += (f",drawtext=fontfile={font_name}:textfile={overlay_file}:fontcolor=white:"
                  f"fontsize={height // 20}:borderw=2:bordercolor=black@0.6:"
                  f"box=1:boxcolor=black@0.45:boxborderw={height // 50}:"
                  f"x=(w-text_w)/2:y=h-text_h-h*0.07")
    audio = f"{SOFTEN if soften else ''}afade=t=in:d=0.04,afade=t=out:st={fade_out:.3f}:d=0.04,aresample=48000"
    return ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-t", f"{trim:.3f}",
            "-vf", video, "-af", audio, "-ac", "2",
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", out]


def main():
    parser = argparse.ArgumentParser(description="Trim and join the clips into one video.")
    parser.add_argument("--no-overlays", action="store_true", help="do not draw the overlay text")
    parser.add_argument("--soften-audio", action="store_true", help="reduce the thin, tinny sound of generated voices")
    parser.add_argument("--name", default="final", help="start of the output file name")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg was not found on your PATH.")
    plan_path = OUTPUT_DIR / "shots.json"
    if not plan_path.is_file():
        sys.exit("Missing output\\shots.json. Run shot_list.py first.")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    width, height = SIZES.get(plan.get("aspect_ratio", "16:9"), SIZES["16:9"])

    shots = []
    for shot in plan["shots"]:
        clip = CLIPS_DIR / f"shot_{shot['shot']:02d}.mp4"
        if clip.is_file():
            shots.append((shot, clip))
        else:
            print(f"Note: no clip for shot {shot['shot']}, leaving it out.")
    if not shots:
        sys.exit("No clips found in output\\clips. Run make_videos.py first.")

    font = None if args.no_overlays else find_font()
    if not args.no_overlays and font is None and any(s.get("overlay_text") for s, _ in shots):
        print("Note: no font found, so overlay text will be skipped.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Everything runs inside this folder with plain file names, which avoids
        # Windows drive-letter problems in ffmpeg's filter text.
        if font:
            shutil.copy(font, tmp / "font.ttf")
        names = []
        for shot, clip in shots:
            n = shot["shot"]
            shutil.copy(clip, tmp / f"in{n}.mp4")
            overlay = None
            if font and shot.get("overlay_text"):
                overlay = f"text{n}.txt"
                (tmp / overlay).write_text(shot["overlay_text"], encoding="utf-8")
            trim = float(shot.get("trim_to_seconds") or shot["clip_seconds"])
            needed = spoken_seconds(shot)
            if needed > trim:
                trim = min(needed, clip_length(clip, shot["clip_seconds"]))
                print(f"Shot {n}: extended so the spoken line finishes")
            print(f"Shot {n}: keeping the first {trim:.1f}s" + (f", overlay '{shot['overlay_text']}'" if overlay else ""))
            cmd = segment_command(f"in{n}.mp4", f"seg{n}.mp4", width, height, trim, overlay, "font.ttf", args.soften_audio)
            run(cmd, tmp)
            names.append(f"seg{n}.mp4")
        (tmp / "list.txt").write_text("".join(f"file '{n}'\n" for n in names), encoding="utf-8")
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-i", "list.txt", "-c", "copy", "joined.mp4"], tmp)
        out = OUTPUT_DIR / f"{args.name}_{time.strftime('%Y%m%d-%H%M%S')}.mp4"
        shutil.copy(tmp / "joined.mp4", out)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
