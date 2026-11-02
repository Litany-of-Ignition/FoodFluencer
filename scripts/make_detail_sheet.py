r"""Step 2 of FoodFluencer: make the detail sheet (hands, chest-down view, faces, teeth).

Usage (PowerShell, from the project folder):
    python scripts\make_detail_sheet.py input\Me.jpg

Run make_sheet.py first. This step sends the model two references so the face,
outfit and accessories stay identical:
  1. your original upload
  2. the character sheet (the upload itself if it already is a sheet, otherwise
     the newest sheet in the output folder, or whatever you pass with --sheet)

Needs the COMFY_API_KEY environment variable and the comfy-sdk package.
The prompt is read from prompts/character-sheet.md (Part C), so edit it there.
Use --dry-run to see what would be sent without spending anything.
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
from pathlib import Path

from analyze_character import read_image
from make_sheet import (
    DEFAULT_MODEL,
    OUTPUT_DIR,
    PROMPT_FILE,
    as_dict,
    explain_error,
    extra_rules,
    extract_parts,
)

MAX_TOTAL_MB = 12

# Added to the Part C prompt. Sheets often carry rulers, labels and grey face masks.
SHEET_RULE = (
    " If a reference image is a character sheet, ignore any rulers, labels or grey "
    "masks on it and take the face and teeth from its face close-ups."
)


def load_detail_prompt(path=PROMPT_FILE):
    """Pull the Part C prompt (the first ```text block after '## Part C')."""
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"## Part C.*?```text\n(.*?)\n```", text, re.S)
    if not match:
        raise SystemExit(f"Could not find the Part C prompt in {path}")
    return match.group(1).strip()


def load_character_info():
    """Read the check's result (output/character.json), or None if it is not there."""
    path = OUTPUT_DIR / "character.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def newest_generated_sheet():
    found = sorted(list(OUTPUT_DIR.glob("sheet_*.png")) + list(OUTPUT_DIR.glob("sheet_*.jpg")))
    return found[-1] if found else None


def choose_references(original, sheet_arg, info):
    """Return the list of reference image paths, without duplicates."""
    refs = [Path(original)]
    if sheet_arg:
        refs.append(Path(sheet_arg))
    elif info and info.get("image_type") == "character_sheet":
        pass  # the upload already is the sheet
    else:
        generated = newest_generated_sheet()
        if generated:
            refs.append(generated)
    unique, seen = [], set()
    for ref in refs:
        key = ref.resolve() if ref.exists() else ref
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


def build_prompt(base, info, strip_logos=False):
    prompt = base
    if info and info.get("short_descriptor"):
        prompt += f" The character is: {info['short_descriptor']}."
    return prompt + SHEET_RULE + extra_rules(strip_logos)


def build_request(prompt, images, aspect, size):
    """images: list of (bytes, mime)."""
    parts = [{"text": prompt}]
    for data, mime in images:
        parts.append({"inlineData": {"data": base64.b64encode(data).decode("ascii"), "mimeType": mime}})
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect, "imageSize": size},
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Make the detail sheet (hands, chest-down, faces, teeth).")
    parser.add_argument("image", help=r"the original upload, e.g. input\Me.jpg")
    parser.add_argument("--sheet", help="character sheet to use as the second reference")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Comfy Router model id")
    parser.add_argument("--aspect", default="16:9", help="sheet aspect ratio")
    parser.add_argument("--size", default="2K", help="1K, 2K or 4K (2K keeps hands and teeth sharper)")
    parser.add_argument("--strip-logos", action="store_true", help="swap brand and team logos on clothing for plain versions")
    parser.add_argument("--dry-run", action="store_true", help="show what would be sent, then stop")
    args = parser.parse_args()

    info = load_character_info()
    if info is None:
        print("Note: output\\character.json not found. Run make_sheet.py first for best results.")

    refs = choose_references(args.image, args.sheet, info)
    images, total = [], 0
    print("References that will be sent:")
    for ref in refs:
        data, mime = read_image(ref)
        images.append((data, mime))
        total += len(data)
        print(f"  - {ref} ({len(data) / 1024:.0f} KB)")
    if total > MAX_TOTAL_MB * 1024 * 1024:
        sys.exit(f"Those images add up to over {MAX_TOTAL_MB} MB. Use a smaller photo.")
    if len(images) == 1:
        if info and info.get("image_type") == "character_sheet":
            print("  (your upload is already the character sheet, so one image is enough)")
        else:
            print("  (only one reference: no separate character sheet was found)")
    if info and not info.get("teeth_visible"):
        print("Note: no teeth are visible in your image, so the teeth panel will be invented.")

    prompt = build_prompt(load_detail_prompt(), info, args.strip_logos)
    request = build_request(prompt, images, args.aspect, args.size)

    if args.dry_run:
        print(f"\nModel:  {args.model}\nSize:   {args.size}, {args.aspect}\n\nPrompt that would be sent:\n{prompt}")
        return

    if not os.environ.get("COMFY_API_KEY"):
        sys.exit("COMFY_API_KEY is not set. Open a NEW PowerShell window and try again.")
    try:
        from comfy_sdk import Comfy
    except ImportError:
        sys.exit("comfy-sdk is not installed. Run: python -m pip install -r requirements.txt")

    print(f"\nModel:  {args.model}")
    print("Cost:   roughly 30-40 credits (about 15-20 cents). Sending now...")
    started = time.time()
    try:
        with Comfy() as client:
            result = client.models.run(args.model, request)
    except Exception as error:
        explain_error(error)
        sys.exit(1)

    images_out, texts, urls = extract_parts(result)
    print(f"Done in {time.time() - started:.0f}s.")
    for text in texts:
        print(f"Model note: {text}")
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for index, (data, ext) in enumerate(images_out, 1):
        out = OUTPUT_DIR / f"detail_sheet_{stamp}_{index}.{ext}"
        out.write_bytes(data)
        print(f"Saved: {out}")
    for url in urls:
        print(f"Image link (expires in about 24 hours): {url}")
    if not images_out and not urls:
        print("No image came back. The raw response is below, so it can be diagnosed.")
        print(str(as_dict(result))[:2000])


if __name__ == "__main__":
    main()
