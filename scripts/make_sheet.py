r"""Step 1 of FoodFluencer: turn a character photo into a character sheet.

Usage (PowerShell, from the project folder):
    python scripts\make_sheet.py input\Me.jpg

First it checks what the upload is. If it is already a character sheet, it stops
and tells you, so you do not pay to remake it. Use --force to make a new sheet
anyway, or --skip-check to skip the check.

Needs the COMFY_API_KEY environment variable and the comfy-sdk package.
The prompt is read from prompts/character-sheet.md (Part B), so edit it there.
"""
import argparse
import base64
import os
import re
import sys
import time
from pathlib import Path

from analyze_character import analyze, read_image, save_analysis, summarize

PROJECT = Path(__file__).resolve().parent.parent
PROMPT_FILE = PROJECT / "prompts" / "character-sheet.md"
OUTPUT_DIR = PROJECT / "output"
# Nano Banana 2. The original Nano Banana is "vertexai/gemini-2.5-flash-image".
DEFAULT_MODEL = "vertexai/gemini-3.1-flash-image"

# Always added to the end of a sheet prompt: keeps stray text out of the sheet.
NO_LABELS_RULE = " Do not add rulers, measurement marks, labels, captions or hashtags."
# Only added with --strip-logos: swaps brand and team logos for plain versions.
STRIP_LOGOS_RULE = (
    " Replace any brand logos, team logos or readable text on clothing and "
    "accessories with plain, unbranded versions."
)


def extra_rules(strip_logos=False):
    """Rules appended to the sheet prompts. Logos stay on clothing unless asked."""
    return (STRIP_LOGOS_RULE if strip_logos else "") + NO_LABELS_RULE


def load_sheet_prompt(path=PROMPT_FILE):
    """Pull the Part B prompt (the first ```text block after '## Part B')."""
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"## Part B.*?```text\n(.*?)\n```", text, re.S)
    if not match:
        raise SystemExit(f"Could not find the Part B prompt in {path}")
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


def extract_parts(result):
    """Return (images, texts, urls) from a Gemini-style response.

    images: list of (bytes, file_extension)
    texts:  list of strings the model wrote
    urls:   list of signed URLs, if the response used links instead of data
    """
    data = as_dict(result)
    images, texts, urls = [], [], []
    for candidate in data.get("candidates", []) or []:
        for part in (candidate.get("content") or {}).get("parts", []) or []:
            inline = part.get("inlineData") or part.get("inline_data")
            file_data = part.get("fileData") or part.get("file_data")
            if inline:
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                ext = "png" if mime == "image/png" else "jpg"
                images.append((base64.b64decode(inline["data"]), ext))
            elif file_data:
                urls.append(file_data.get("fileUri") or file_data.get("file_uri"))
            elif part.get("text"):
                texts.append(part["text"])
    return images, texts, urls


def build_request(prompt, image_bytes, mime, aspect, size):
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                            "mimeType": mime,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect, "imageSize": size},
        },
    }


def explain_error(error):
    print(f"\nThe call failed: {type(error).__name__}: {error}")
    message = str(error).lower()
    if "402" in message or "insufficient" in message:
        print("This usually means there are no credits on the account.")
    elif "422" in message:
        print("The request was rejected before it was billed. Send me this error.")
    elif "413" in message or "too large" in message:
        print("The images are too big for one request. Use a smaller photo.")
    elif "401" in message or "unauthorized" in message:
        print("The API key was not accepted. Check COMFY_API_KEY.")


def main():
    parser = argparse.ArgumentParser(description="Make a character sheet from a photo.")
    parser.add_argument("image", help=r"path to the character photo, e.g. input\Me.jpg")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Comfy Router model id for the sheet")
    parser.add_argument("--aspect", default="16:9", help="sheet aspect ratio")
    parser.add_argument("--size", default="1K", help="1K, 2K or 4K")
    parser.add_argument("--strip-logos", action="store_true", help="swap brand and team logos on clothing for plain versions")
    parser.add_argument("--skip-check", action="store_true", help="do not check what the upload is first")
    parser.add_argument("--force", action="store_true", help="make a new sheet even if the upload already is one")
    args = parser.parse_args()

    if not os.environ.get("COMFY_API_KEY"):
        sys.exit("COMFY_API_KEY is not set. Open a NEW PowerShell window and try again.")

    image_bytes, mime = read_image(args.image)

    try:
        from comfy_sdk import Comfy
    except ImportError:
        sys.exit("comfy-sdk is not installed. Run: python -m pip install -r requirements.txt")

    prompt = load_sheet_prompt() + extra_rules(args.strip_logos)
    request = build_request(prompt, image_bytes, mime, args.aspect, args.size)

    try:
        with Comfy() as client:
            if not args.skip_check:
                print(f"Photo:  {args.image} ({len(image_bytes) / 1024:.0f} KB)")
                print("Checking what kind of image this is (a fraction of a cent)...")
                info = analyze(image_bytes, mime, client)
                summarize(info)
                save_analysis(info)
                if info.get("status") != "ok":
                    sys.exit(1)
                if info.get("image_type") == "character_sheet" and not args.force:
                    print("\nNothing more to do here: use this image as the character sheet.")
                    print("(Add --force if you want a new sheet made from it anyway.)")
                    return

            print(f"\nModel:  {args.model}")
            print("Cost:   roughly 20-30 credits (about 10-15 cents) at 1K. Sending now...")
            started = time.time()
            result = client.models.run(args.model, request)
    except SystemExit:
        raise
    except Exception as error:  # show the real error so it can be fixed
        explain_error(error)
        sys.exit(1)

    images, texts, urls = extract_parts(result)
    print(f"Done in {time.time() - started:.0f}s.")
    for text in texts:
        print(f"Model note: {text}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for index, (data, ext) in enumerate(images, 1):
        out = OUTPUT_DIR / f"sheet_{stamp}_{index}.{ext}"
        out.write_bytes(data)
        print(f"Saved: {out}")
    for url in urls:
        print(f"Image link (expires in about 24 hours): {url}")
    if not images and not urls:
        print("No image came back. The raw response is below, so it can be diagnosed.")
        print(str(as_dict(result))[:2000])


if __name__ == "__main__":
    main()
