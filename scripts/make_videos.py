r"""Step 5 of FoodFluencer: turn the shot list into video clips with MiniMax H3.

Usage (PowerShell, from the project folder):
    python scripts\make_videos.py --only 1        (one shot: the cheap first test)
    python scripts\make_videos.py                 (all shots in output\shots.json)

Reads output\shots.json and the character sheets in the output and input folders.
Shows the cost and asks before spending anything. Clips are saved in output\clips.
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from analyze_character import OUTPUT_DIR, PROJECT, as_dict, read_image
from make_sheet import explain_error

MODEL = "minimax/minimax-h3"
RESOLUTION = "768P"
DOLLARS_PER_SECOND = 0.13
MAX_TOTAL_SECONDS = 60          # safety cap per run; --allow-big lifts it
MAX_SIDE = 1536                 # reference images are shrunk to this many pixels
CLIPS_DIR = OUTPUT_DIR / "clips"
SCENE_NOTE = (
    " One reference image shows the exact setting: keep the same room or vehicle, the same seat, the "
    "same camera position and the same background objects."
)
REFERENCE_NOTE = (
    "Use the attached reference images for the character's exact face, teeth, hands, "
    "hair, clothing and jewelry."
)
VIDEO_NOTE = (
    "Use the person in the attached reference video, and the reference photo of them, as the character: "
    "their exact face, likeness and voice (timbre, pitch, accent and pace) for every line the character "
    "speaks. Only their face, likeness and voice come from the reference video. Never show the reference "
    "video's room, background or props, not even for a moment: every cut, including the last one, stays "
    "inside the setting described above."
)
MAX_REF_VIDEO_MB = 30           # request bodies carry the video encoded as text, so keep it small


def newest(pattern):
    found = sorted(OUTPUT_DIR.glob(pattern))
    return found[-1] if found else None


def find_sheets(character_info, upload=None):
    """Return {'character_sheet': Path|None, 'detail_sheet': Path|None}."""
    if character_info.get("image_type") == "character_sheet" and upload:
        sheet = Path(upload)
    else:
        sheet = newest("sheet_*.png") or newest("sheet_*.jpg")
    return {"character_sheet": sheet, "detail_sheet": newest("detail_sheet_*.png") or newest("detail_sheet_*.jpg")}


def shrink(path):
    """Return (bytes, mime), shrunk so request bodies stay small."""
    data, mime = read_image(path)
    try:
        from PIL import Image
    except ImportError:
        print("Note: Pillow is not installed, so images are sent full size. Run: python -m pip install -r requirements.txt")
        return data, mime
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88)
    return buffer.getvalue(), "image/jpeg"


def data_uri(data, mime):
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def scene_path(plan):
    """The scene reference made for THIS shot list, or None."""
    name = plan.get("scene_image")
    path = OUTPUT_DIR / name if name else None
    return path if path and path.is_file() else None


def references_for(shot, sheets):
    wanted = {"character_sheet": ["character_sheet"], "detail_sheet": ["detail_sheet"],
              "both": ["character_sheet", "detail_sheet"]}[shot["reference"]]
    paths = [sheets[name] for name in wanted if sheets.get(name)]
    if not paths:
        raise SystemExit(f"Shot {shot['shot']} needs {shot['reference']}, but that sheet was not found in the output folder.")
    return paths


def read_ref_video(path):
    """Return a data URI for a short selfie video to use as the reference, or exit if it is too big."""
    path = Path(path)
    if not path.is_file():
        sys.exit(f"Could not find the reference video: {path}")
    megabytes = path.stat().st_size / 1_000_000
    if megabytes > MAX_REF_VIDEO_MB:
        sys.exit(f"That video is {megabytes:.0f} MB; the limit here is {MAX_REF_VIDEO_MB} MB. Trim it to 15 seconds or less first.")
    mime = "video/quicktime" if path.suffix.lower() == ".mov" else "video/mp4"
    return data_uri(path.read_bytes(), mime)


def build_text(shot, with_scene=False, with_video=False):
    parts = [shot["video_prompt"].strip()]
    if shot.get("dialogue"):
        parts.append(f'The character says to camera, in a natural voice: "{shot["dialogue"].strip()}"')
    if shot.get("voiceover"):
        parts.append(f'A calm voiceover says: "{shot["voiceover"].strip()}"')
    if shot.get("audio_direction"):
        parts.append(f"Sound: {shot['audio_direction'].strip()}")
    parts.append((VIDEO_NOTE if with_video else REFERENCE_NOTE) + (SCENE_NOTE if with_scene else ""))
    return " ".join(parts)


def build_body(shot, uris, ratio, with_scene=False, video_uri=None):
    content = [{"type": "text", "text": build_text(shot, with_scene, bool(video_uri))}]
    for uri in uris:
        content.append({"type": "image_url", "image_url": {"url": uri}, "role": "reference_image"})
    if video_uri:
        content.append({"type": "video_url", "video_url": {"url": video_uri}, "role": "reference_video"})
    return {"content": content, "duration": int(shot["clip_seconds"]), "resolution": RESOLUTION, "ratio": ratio}


def video_url(result):
    data = as_dict(result)
    task = data.get("task", data)
    content = task.get("content") or {}
    return content.get("url") if isinstance(content, dict) else None


def main():
    parser = argparse.ArgumentParser(description="Make video clips from the shot list with MiniMax H3.")
    parser.add_argument("--only", type=int, action="append", help="only this shot number (repeatable)")
    parser.add_argument("--upload", help=r"your original upload, e.g. input\Me.jpg (used when it already is a character sheet)")
    parser.add_argument("--sheet", help="character sheet to use (default: your upload if it is a sheet, otherwise the newest one made)")
    parser.add_argument("--detail", help="detail sheet to use (default: the newest one made)")
    parser.add_argument("--ref-video", help="a selfie video (15s or less): used as the face and voice reference instead of character sheets (pair it with --upload <a photo of the same person>)")
    parser.add_argument("--no-scene", action="store_true", help="ignore the scene reference image")
    parser.add_argument("--yes", action="store_true", help="do not ask before spending")
    parser.add_argument("--redo", action="store_true", help="remake clips that already exist")
    parser.add_argument("--allow-big", action="store_true", help=f"allow more than {MAX_TOTAL_SECONDS}s of footage in one run")
    args = parser.parse_args()

    shots_path = OUTPUT_DIR / "shots.json"
    if not shots_path.is_file():
        sys.exit("Missing output\\shots.json. Run shot_list.py first.")
    plan = json.loads(shots_path.read_text(encoding="utf-8"))
    character = json.loads((OUTPUT_DIR / "character.json").read_text(encoding="utf-8")) if (OUTPUT_DIR / "character.json").is_file() else {}
    video_uri = read_ref_video(args.ref_video) if args.ref_video else None
    sheets = {} if video_uri else find_sheets(character, args.upload)   # a selfie video replaces the sheets
    if args.sheet and not video_uri:
        sheets["character_sheet"] = Path(args.sheet)
    if args.detail and not video_uri:
        sheets["detail_sheet"] = Path(args.detail)
    for name, path in sheets.items():
        if path and not path.is_file():
            sys.exit(f"Could not find the {name}: {path}")
    ratio = plan.get("aspect_ratio", "16:9")

    shots = [s for s in plan["shots"] if not args.only or s["shot"] in args.only]
    if not shots:
        sys.exit("No matching shots.")
    todo = [s for s in shots if args.redo or not (CLIPS_DIR / f"shot_{s['shot']:02d}.mp4").exists()]
    skipped = [s["shot"] for s in shots if s not in todo]
    if skipped:
        print(f"Already made (skipping): shots {skipped}. Use --redo to remake them.")
    if not todo:
        sys.exit("Nothing to make.")

    total = sum(int(s["clip_seconds"]) for s in todo)
    if total > MAX_TOTAL_SECONDS and not args.allow_big:
        sys.exit(f"That is {total}s of footage (limit {MAX_TOTAL_SECONDS}s per run). Use --only, or add --allow-big.")
    print(f"\nWill make {len(todo)} clip(s), {total}s of 768P video with sound, about ${total * DOLLARS_PER_SECOND:.2f}.")
    scene = None if args.no_scene else scene_path(plan)
    for name, path in sheets.items():
        print(f"  {name}: {path if path else 'NOT FOUND'}")
    print(f"  scene: {scene if scene else 'none (run make_scene.py to keep the setting consistent)'}")
    if video_uri:
        print(f"  reference video: {args.ref_video}")
        print(f"  reference photo: {args.upload if args.upload else 'none'}")
    if not args.yes and input("Go ahead and spend that? Type y then Enter: ").strip().lower() != "y":
        sys.exit("Cancelled. Nothing was spent.")

    if not os.environ.get("COMFY_API_KEY"):
        sys.exit("COMFY_API_KEY is not set. Open a NEW PowerShell window and try again.")
    try:
        from comfy_sdk import Comfy
    except ImportError:
        sys.exit("comfy-sdk is not installed. Run: python -m pip install -r requirements.txt")

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    cache = {}
    with Comfy() as client:
        for shot in todo:
            number = shot["shot"]
            uris = []
            for path in ([Path(args.upload)] if video_uri and args.upload else [] if video_uri else references_for(shot, sheets)):
                if path not in cache:
                    cache[path] = data_uri(*shrink(path))
                uris.append(cache[path])
            if scene:
                if scene not in cache:
                    cache[scene] = data_uri(*shrink(scene))
                uris = uris + [cache[scene]]
            body = build_body(shot, uris, ratio, with_scene=bool(scene), video_uri=video_uri)
            extra = " and the selfie video" if video_uri else ""
            print(f"\nShot {number}: {shot['clip_seconds']}s, {len(uris)} reference image(s){extra}. Sending (this can take a few minutes)...")
            started = time.time()
            try:
                result = client.models.run(MODEL, body)
            except Exception as error:
                explain_error(error)
                print("Stopping here so nothing else is spent. Clips already made are kept.")
                sys.exit(1)
            (CLIPS_DIR / f"shot_{number:02d}.json").write_text(json.dumps(as_dict(result), indent=2, default=str), encoding="utf-8")
            url = video_url(result)
            if not url:
                print("No video link came back. The raw reply was saved next to the clips.")
                sys.exit(1)
            out = CLIPS_DIR / f"shot_{number:02d}.mp4"
            urllib.request.urlretrieve(url, out)
            print(f"Done in {time.time() - started:.0f}s. Saved: {out}")


if __name__ == "__main__":
    main()
