r"""Step 4b of FoodFluencer: make one reference picture of the shared setting.

Usage (PowerShell, from the project folder):
    python scripts\make_scene.py

Run it after shot_list.py and before make_videos.py. It makes a single still of the
character in the scene described in output\shots.json, so every video clip can match
the same room, seat and camera position. Costs about 10-15 cents.
"""
import argparse
import json
import os
import sys
import time

from pathlib import Path

from analyze_character import OUTPUT_DIR
from make_sheet import DEFAULT_MODEL, NO_LABELS_RULE, as_dict, explain_error, extract_parts
from make_videos import data_uri, find_sheets, shrink

SCENE_PROMPT = (
    "A single realistic, natural photograph of the same person as in the reference images, with exactly the "
    "same face, hair, clothing and jewelry. This one frame establishes the setting for a video. The scene: "
    "{scene} Use the reference images only to show who she is. Keep the camera position, angle and framing "
    "exactly as the scene describes. The look is a real, unretouched photo."
)


def build_request(prompt, images, aspect, size):
    parts = [{"text": prompt}] + [
        {"inlineData": {"data": data_uri(*img).split(",", 1)[1], "mimeType": img[1]}} for img in images
    ]
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"],
                             "imageConfig": {"aspectRatio": aspect, "imageSize": size}},
    }


def main():
    parser = argparse.ArgumentParser(description="Make the scene reference picture.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default="1K")
    parser.add_argument("--upload", help=r"your original upload, e.g. input\Me.jpg")
    parser.add_argument("--sheet", help="character sheet to use")
    parser.add_argument("--detail", help="detail sheet to use")
    args = parser.parse_args()

    plan_path = OUTPUT_DIR / "shots.json"
    if not plan_path.is_file():
        sys.exit("Missing output\\shots.json. Run shot_list.py first.")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    scene = (plan.get("scene") or "").strip()
    if not scene:
        sys.exit("shots.json has no scene. Run shot_list.py again.")
    char_path = OUTPUT_DIR / "character.json"
    info = json.loads(char_path.read_text(encoding="utf-8")) if char_path.is_file() else {}
    sheets = find_sheets(info, args.upload)
    if args.sheet:
        sheets["character_sheet"] = Path(args.sheet)
    if args.detail:
        sheets["detail_sheet"] = Path(args.detail)
    refs = [path for path in sheets.values() if path]
    if not refs:
        sys.exit("No character sheets found in the output folder.")
    if not os.environ.get("COMFY_API_KEY"):
        sys.exit("COMFY_API_KEY is not set. Open a NEW PowerShell window and try again.")
    try:
        from comfy_sdk import Comfy
    except ImportError:
        sys.exit("comfy-sdk is not installed. Run: python -m pip install -r requirements.txt")

    prompt = SCENE_PROMPT.format(scene=scene)
    if info.get("short_descriptor"):
        prompt += f" The person is: {info['short_descriptor']}."
    prompt += NO_LABELS_RULE
    aspect = plan.get("aspect_ratio", "16:9")
    request = build_request(prompt, [shrink(path) for path in refs], aspect, args.size)
    print(f"Scene: {scene}\nReferences: {', '.join(p.name for p in refs)}\nAbout 10-15 cents. Sending...")
    started = time.time()
    try:
        with Comfy() as client:
            result = client.models.run(args.model, request)
    except Exception as error:
        explain_error(error)
        sys.exit(1)
    images, texts, urls = extract_parts(result)
    if not images:
        print("No image came back. Raw reply:\n" + str(as_dict(result))[:1500])
        sys.exit(1)
    data, ext = images[0]
    name = f"scene_{time.strftime('%Y%m%d-%H%M%S')}.{ext}"
    (OUTPUT_DIR / name).write_bytes(data)
    plan["scene_image"] = name
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"Done in {time.time() - started:.0f}s. Saved: {OUTPUT_DIR / name}")
    print("Look at it. If the setting is wrong, run this again before making any video.")


if __name__ == "__main__":
    main()
