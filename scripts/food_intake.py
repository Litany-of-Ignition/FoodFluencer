r"""Step 3 of FoodFluencer: turn a food (text, photo, or both) into a filmable recipe.

Usage (PowerShell, from the project folder):
    python scripts\food_intake.py --text "birria tacos"
    python scripts\food_intake.py --image input\dish.jpg
    python scripts\food_intake.py --text "birria tacos" --image input\dish.jpg

Saves output\dish.json. Costs a fraction of a cent.
The prompt is read from prompts/food-intake.md (everything below the first ---).
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

from analyze_character import DEFAULT_MODEL, OUTPUT_DIR, PROJECT, parse_json, read_image, response_text

PROMPT_FILE = PROJECT / "prompts" / "food-intake.md"


def load_food_prompt(path=PROMPT_FILE):
    text = Path(path).read_text(encoding="utf-8")
    if "\n---\n" not in text:
        raise SystemExit(f"Could not find the prompt (the --- line) in {path}")
    return text.split("\n---\n", 1)[1].strip()


def build_request(prompt, food_text, image):
    """image: (bytes, mime) or None."""
    prompt += f"\n\nfood_text: {food_text if food_text else '(empty)'}\n"
    prompt += "food_image: " + ("(attached)" if image else "(absent)")
    parts = [{"text": prompt}]
    if image:
        data, mime = image
        parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode("ascii")}})
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
    }


def check(info):
    if info.get("status") not in ("ok", "needs_clarification"):
        raise ValueError(f"unexpected status: {info.get('status')!r}")
    if info["status"] == "ok":
        for key in ("dish_name", "visual_description", "steps", "hero_shot"):
            if not info.get(key):
                raise ValueError(f"{key} is empty")
    return info


def run_intake(food_text, image, client, model=DEFAULT_MODEL, attempts=2):
    request = build_request(load_food_prompt(), food_text, image)
    last = None
    for _ in range(attempts):
        result = client.models.run(model, request)
        try:
            return check(parse_json(response_text(result)))
        except (ValueError, json.JSONDecodeError) as error:
            last = error
    raise RuntimeError(f"The model's reply could not be read ({last}).")


def main():
    parser = argparse.ArgumentParser(description="Turn a food input into a filmable recipe.")
    parser.add_argument("--text", default="", help='the dish, e.g. "birria tacos"')
    parser.add_argument("--image", help="photo of the dish")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    if not args.text and not args.image:
        sys.exit("Give me a food: --text \"...\" and/or --image path")
    if not os.environ.get("COMFY_API_KEY"):
        sys.exit("COMFY_API_KEY is not set. Open a NEW PowerShell window and try again.")
    image = read_image(args.image) if args.image else None
    try:
        from comfy_sdk import Comfy
    except ImportError:
        sys.exit("comfy-sdk is not installed. Run: python -m pip install -r requirements.txt")
    try:
        with Comfy() as client:
            info = run_intake(args.text, image, client, args.model)
    except Exception as error:
        print(f"\nThe call failed: {type(error).__name__}: {error}")
        sys.exit(1)

    if info["status"] != "ok":
        print(f"\nNeeds a clarification: {info.get('conflict_note')}")
        sys.exit(1)
    print(f"\nDish:  {info['dish_name']} ({info.get('cuisine', '')})")
    print(f"Hero:  {info['hero_shot']}")
    print("Steps:")
    for step in info["steps"]:
        print(f"  {step['n']}. {step['title']}: {step['visible_action']}")
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / "dish.json"
    out.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
