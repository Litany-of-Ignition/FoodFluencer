r"""Look at an uploaded character image and say what it is.

Usage (PowerShell, from the project folder):
    python scripts\analyze_character.py input\Me.jpg

Tells you whether the upload is a photo, an existing character sheet, and so on,
describes the character, and saves the result to output\character.json.
Costs a fraction of a cent. The prompt is read from prompts/character-sheet.md (Part A).
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PROMPT_FILE = PROJECT / "prompts" / "character-sheet.md"
OUTPUT_DIR = PROJECT / "output"
# Gemini 2.5 Flash was retired on 2026-10-16; this is the replacement Comfy names.
DEFAULT_MODEL = "vertexai/gemini-3.5-flash"
MAX_IMAGE_MB = 10

IMAGE_TYPES = ("photo", "character_sheet", "illustration", "multiple_people", "no_person")
NEXT_STEP = {
    "photo": "A new character sheet will be made from this photo.",
    "illustration": "A new character sheet will be made from this image.",
    "character_sheet": "This is already a character sheet, so no new one is needed.",
}


def load_analysis_prompt(path=PROMPT_FILE):
    """Pull the Part A prompt (the first ```text block after '## Part A')."""
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"## Part A.*?```text\n(.*?)\n```", text, re.S)
    if not match:
        raise SystemExit(f"Could not find the Part A prompt in {path}")
    return match.group(1).strip()


def as_dict(obj):
    """The SDK may hand back a dict or a model object; always return a dict."""
    if isinstance(obj, dict):
        return obj
    for name in ("model_dump", "dict"):
        fn = getattr(obj, name, None)
        if callable(fn):
            return fn()
    raise TypeError(f"Unexpected result type: {type(obj).__name__}")


def build_request(prompt, image_bytes, mime):
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": mime, "data": base64.b64encode(image_bytes).decode("ascii")}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
    }


def response_text(result):
    """Join the model's visible text, skipping any 'thinking' parts."""
    pieces = []
    for candidate in as_dict(result).get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            if part.get("thought"):
                continue
            if part.get("text"):
                pieces.append(part["text"])
        if pieces:
            break
    return "".join(pieces)


def parse_json(text):
    """Find the JSON object in the model's reply, even if it added code fences."""
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in the reply")
    return json.loads(text[start : end + 1])


def check(info):
    """Raise ValueError if the reply is missing the fields the app depends on."""
    if info.get("status") not in ("ok", "needs_clarification"):
        raise ValueError(f"unexpected status: {info.get('status')!r}")
    if info.get("image_type") not in IMAGE_TYPES:
        raise ValueError(f"unexpected image_type: {info.get('image_type')!r}")
    if info["status"] == "ok" and not info.get("short_descriptor"):
        raise ValueError("short_descriptor is empty")
    return info


def analyze(image_bytes, mime, client, model=DEFAULT_MODEL, attempts=2):
    """Ask the model about the image. Retries once if the reply is not usable."""
    request = build_request(load_analysis_prompt(), image_bytes, mime)
    last_error = None
    for _ in range(attempts):
        result = client.models.run(model, request)
        try:
            return check(parse_json(response_text(result)))
        except (ValueError, json.JSONDecodeError) as error:
            last_error = error
    raise RuntimeError(f"The model's reply could not be read ({last_error}).")


def summarize(info):
    print("\nWhat the check found:")
    print(f"  Image type:    {info.get('image_type')}")
    if info.get("status") != "ok":
        print(f"  Problem:       {info.get('note') or 'the image could not be used'}")
        return
    print(f"  Character:     {info.get('short_descriptor')}")
    logos = info.get("has_logos_or_text")
    note = info.get("logos_or_text_note") or ""
    print(f"  Logos or text: {'yes - ' + note if logos else 'none seen'}")
    print(f"  Teeth visible: {'yes' if info.get('teeth_visible') else 'no'}")
    print(f"  Next:          {NEXT_STEP.get(info.get('image_type'), '')}")


def save_analysis(info):
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / "character.json"
    out.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"  Saved:         {out}")
    return out


def read_image(path):
    """Return (bytes, mime) or exit with a plain-English message."""
    image_path = Path(path)
    if not image_path.is_file():
        sys.exit(f"Could not find the photo: {image_path}")
    data = image_path.read_bytes()
    if len(data) > MAX_IMAGE_MB * 1024 * 1024:
        sys.exit(f"That image is over {MAX_IMAGE_MB} MB. Resize or compress it first.")
    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    if mime not in ("image/png", "image/jpeg", "image/webp"):
        sys.exit(f"Use a PNG, JPG or WebP image (this one looks like {mime}).")
    return data, mime


def main():
    parser = argparse.ArgumentParser(description="Check what a character upload is.")
    parser.add_argument("image", help=r"path to the image, e.g. input\Me.jpg")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Comfy Router model id")
    args = parser.parse_args()

    if not os.environ.get("COMFY_API_KEY"):
        sys.exit("COMFY_API_KEY is not set. Open a NEW PowerShell window and try again.")
    data, mime = read_image(args.image)
    try:
        from comfy_sdk import Comfy
    except ImportError:
        sys.exit("comfy-sdk is not installed. Run: python -m pip install -r requirements.txt")

    try:
        with Comfy() as client:
            info = analyze(data, mime, client, model=args.model)
    except Exception as error:
        print(f"\nThe call failed: {type(error).__name__}: {error}")
        sys.exit(1)

    summarize(info)
    save_analysis(info)


if __name__ == "__main__":
    main()
