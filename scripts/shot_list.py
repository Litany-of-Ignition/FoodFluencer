r"""Step 4 of FoodFluencer: write the shot list for a style module.

Usage (PowerShell, from the project folder):
    python scripts\shot_list.py --score 3
    python scripts\shot_list.py --score 9 --note "the sauce was amazing"

Needs output\character.json (from make_sheet.py) and output\dish.json (from food_intake.py).
Saves output\shots.json and prints what the video step would cost. Costs a fraction of a cent.
Style names are the file names in the modules folder, without .md.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from analyze_character import DEFAULT_MODEL, OUTPUT_DIR, PROJECT, parse_json, response_text

PROMPT_FILE = PROJECT / "prompts" / "shot-list.md"
MODULES_DIR = PROJECT / "modules"
REFERENCES = ("character_sheet", "detail_sheet", "both")
MIN_CLIP = 4            # H3 will not make clips shorter than this
MAX_SHOTS = 8           # safety cap so one run cannot get expensive
DOLLARS_PER_SECOND = 0.13  # H3 at 768P, approximate


def load_prompt(path=PROMPT_FILE):
    text = Path(path).read_text(encoding="utf-8")
    if "\n---\n" not in text:
        raise SystemExit(f"Could not find the prompt (the --- line) in {path}")
    return text.split("\n---\n", 1)[1].strip()


SINGLE_RULE = (
    "- **One camera setup per shot.** Describe one framing and, at most, one simple camera move in each "
    "`video_prompt`. Never describe a cut, whip-pan, crash zoom or change of subject inside one shot; the "
    "video model invents strange transitions. Fast cuts come from joining separate shots."
)
CUTS_RULE = (
    "- **Hard cuts inside each clip.** Each shot is ONE clip of `clip_seconds` seconds that contains exactly "
    "{cuts} camera setups joined by plain hard cuts. Write the `video_prompt` as timed segments, for example "
    "\"0-2.5s: <setup>. Cut to 2.5-5s: <setup>. Cut to ...\". Use only the words \"Cut to\". Never use a "
    "whip-pan, crash zoom, zoom transition, dissolve, morph, or any effect between segments. Restate who is on "
    "screen (with the character descriptor), the set and the lighting in every segment, because the video model "
    "treats each segment fresh. Segment lengths follow the module's `cut_min` and `cut_max` and add up to "
    "`clip_seconds`. Each segment is 30-60 words before its spoken line, so the whole `video_prompt` is longer "
    "than usual. Set `trim_to_seconds` equal to `clip_seconds`.\n"
    "- **Speech goes inside the segments.** If the module's `speech` is `on-camera` or `voiceover`, the "
    "character talks through almost every segment, in one continuous voice, each line picking up the last "
    "like one natural spoken explanation of the cooking. Write each line inside its own segment, in this form: "
    "She says: \"...\". When she is in frame she speaks to the camera. In close-ups of food, her voice "
    "continues from off-screen. Use straight double quotes ONLY around spoken lines, and leave the `dialogue` "
    "and `voiceover` fields empty. Each line may be at most {{max_dialogue_words}} words."
)
SCORE_GUIDE = {
    (1, 2): "genuinely bad: something is clearly wrong (cold, soggy, bland, greasy, the wrong order). She is visibly let down and bluntly honest, but never cruel to people.",
    (3, 4): "disappointing: one or two real positives, but the flaws outweigh them. She is fair, specific about what went wrong, and a little deflated.",
    (5, 6): "mixed and fine: decent but forgettable. She is shrugging, even-handed, and names one thing that worked and one that did not.",
    (7, 8): "good: she enjoys it, with one small nitpick. Warm and recommending, but not gushing.",
    (9, 10): "outstanding: she is blown away, talking with her mouth full, and cannot stop praising specific details.",
}


def direction_text(score=None, note=""):
    """Turn the user's score and note into direction for the shot list. 'none' if neither is given."""
    parts = []
    if score is not None:
        mood = next(v for (lo, hi), v in SCORE_GUIDE.items() if lo <= score <= hi)
        parts.append(
            f"The reviewer's final score is {score} out of 10. In the last segment she says the score out loud "
            f"as \"{score} out of 10\". Every comment before it must honestly support that score. For a {score}/10 "
            f"the review is {mood} Describe flaws and praise in concrete, physical terms about the food (crunch, "
            f"temperature, saltiness, grease, texture), never about a named restaurant, brand or person."
        )
    if note.strip():
        parts.append(f"The user adds: {note.strip()}")
    return " ".join(parts) if parts else "none"


EDIT_WORDS = ("bite", "eat", "chew", "taste", "smile", "grin", "laugh")
# Phrases that mean a camera transition. Whole phrases only, so "whipped cream" is fine.
BANNED = re.compile(
    r"\b(whip[- ]?pans?|whip[- ]?zoom|crash[- ]?zooms?|zoom transition|match cut|cross[- ]?dissolves?|"
    r"dissolves? (?:to|into)|morphs? (?:to|into)|morphing|smash cut)\b", re.I)


def list_styles():
    return sorted(p.stem for p in MODULES_DIR.glob("*.md") if p.stem.lower() != "readme")


def load_module(style):
    path = MODULES_DIR / f"{style}.md"
    if not path.is_file():
        raise SystemExit(f"No style called '{style}'. Choose one of: {', '.join(list_styles())}")
    text = path.read_text(encoding="utf-8")
    meta = {}
    match = re.match(r"---\n(.*?)\n---", text, re.S)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip().strip('"')
    return text, meta


def load_json(path, hint):
    if not path.is_file():
        raise SystemExit(f"Missing {path.name}. {hint}")
    return json.loads(path.read_text(encoding="utf-8"))


def max_words(max_clip, cuts):
    """Longest spoken line that fits: whole clip in single mode, one segment when there are cuts."""
    if cuts > 1:
        return max(3, round(max_clip / cuts * 2.4))
    return max(3, int((max_clip - 0.6) * 2.5))


def build_prompt(module_text, dish, descriptor, shots, max_clip, cuts=1, direction="none"):
    prompt = load_prompt()
    fills = {
        "{{cut_rules}}": CUTS_RULE.replace("{cuts}", str(cuts)) if cuts > 1 else SINGLE_RULE,
        "{{max_dialogue_words}}": str(max_words(max_clip, cuts)),
        "{{user_direction}}": direction,
        "{{style_module_markdown}}": module_text,
        "{{dish_json}}": json.dumps(dish, indent=2),
        "{{short_descriptor}}": descriptor,
        "{{shot_count}}": str(shots),
        "{{max_clip_seconds}}": str(max_clip),
    }
    for key, value in fills.items():
        prompt = prompt.replace(key, value)
    return prompt


def check(info, meta, shots, max_clip, cuts=1):
    """Validate the reply and quietly fix small slips. Raises ValueError if unusable."""
    items = info.get("shots")
    if not isinstance(items, list) or len(items) != shots:
        raise ValueError(f"expected {shots} shots, got {len(items) if isinstance(items, list) else 'none'}")
    for number, shot in enumerate(items, 1):
        if not shot.get("video_prompt"):
            raise ValueError(f"shot {number} has no video_prompt")
        shot["shot"] = number
        if shot.get("reference") not in REFERENCES:
            shot["reference"] = "both"
        if meta.get("face_visibility") == "faceless" and shot["reference"] == "character_sheet":
            shot["reference"] = "detail_sheet"
        trim = float(shot.get("trim_to_seconds") or MIN_CLIP)
        words = len(((shot.get("dialogue") or "") + " " + (shot.get("voiceover") or "")).split())
        trim = max(trim, words / 2.5 + 0.6 if words else 0)  # long enough to say the line
        prompt_text = shot["video_prompt"].lower()
        if cuts > 1:
            if prompt_text.count("cut to") != cuts - 1:
                raise ValueError(f"shot {number} should have {cuts - 1} 'Cut to' cuts")
            found = BANNED.search(shot["video_prompt"])
            if found:
                raise ValueError(f"shot {number} uses a transition ({found.group(0)})")
        if cuts > 1:
            # Speech is written inside the timed segments; keep a copy for display.
            shot["spoken"] = re.findall(r'"([^"]+)"', shot["video_prompt"])
            shot["dialogue"] = shot["voiceover"] = ""
        speaks = bool(shot.get("dialogue") or shot.get("spoken"))
        # Whoever speaks or eats on camera needs the teeth reference, whatever the model chose.
        if meta.get("face_visibility") != "faceless" and (
                speaks or any(w in prompt_text for w in EDIT_WORDS)):
            shot["reference"] = "both"
        clip = float(shot.get("clip_seconds") or MIN_CLIP)
        clip = max(MIN_CLIP, min(max_clip, clip, 15))
        shot["clip_seconds"] = int(round(max(clip, min(trim, max_clip))))
        shot["trim_to_seconds"] = shot["clip_seconds"] if cuts > 1 else min(trim, shot["clip_seconds"])
    if not str(info.get("scene") or "").strip():
        raise ValueError("the reply has no scene")
    info.setdefault("module_id", meta.get("id", ""))
    info.setdefault("aspect_ratio", meta.get("aspect_ratio", "16:9"))
    return info


def make_shot_list(module_text, meta, dish, descriptor, shots, max_clip, client, model=DEFAULT_MODEL, attempts=2, cuts=1, direction="none"):
    prompt = build_prompt(module_text, dish, descriptor, shots, max_clip, cuts, direction)
    request = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 16384},
    }
    last = None
    for _ in range(attempts):
        result = client.models.run(model, request)
        try:
            return check(parse_json(response_text(result)), meta, shots, max_clip, cuts)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            last = error
    raise RuntimeError(f"The model's reply could not be read ({last}).")


def main():
    parser = argparse.ArgumentParser(description="Write a shot list for a style module.")
    parser.add_argument("--style", default="parked-car-review", help="style name (a file in the modules folder)")
    parser.add_argument("--shots", type=int, default=1, help=f"number of clips (1-{MAX_SHOTS}, default 1)")
    parser.add_argument("--max-clip", type=int, default=15, help="clip length in seconds (4-15, default 15)")
    parser.add_argument("--cuts", type=int, default=5, help="hard cuts inside each clip (1 = no cuts; 3-5 for fast styles with longer clips)")
    parser.add_argument("--score", type=int, help="for review styles: the final score out of 10 (1-10)")
    parser.add_argument("--note", default="", help="extra direction in your own words, e.g. \"the tacos were cold\"")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    if args.score is not None and not 1 <= args.score <= 10:
        sys.exit("--score must be between 1 and 10.")
    if not 1 <= args.cuts <= 8:
        sys.exit("--cuts must be between 1 and 8.")
    if not 1 <= args.shots <= MAX_SHOTS:
        sys.exit(f"--shots must be between 1 and {MAX_SHOTS}.")
    if not MIN_CLIP <= args.max_clip <= 15:
        sys.exit(f"--max-clip must be between {MIN_CLIP} and 15.")
    if not os.environ.get("COMFY_API_KEY"):
        sys.exit("COMFY_API_KEY is not set. Open a NEW PowerShell window and try again.")

    module_text, meta = load_module(args.style)
    character = load_json(OUTPUT_DIR / "character.json", "Run make_sheet.py first.")
    dish = load_json(OUTPUT_DIR / "dish.json", "Run food_intake.py first.")
    if dish.get("status") != "ok":
        sys.exit("dish.json needs a clarification. Re-run food_intake.py.")
    descriptor = character.get("short_descriptor", "")
    if not descriptor:
        sys.exit("character.json has no description. Run make_sheet.py again.")

    try:
        from comfy_sdk import Comfy
    except ImportError:
        sys.exit("comfy-sdk is not installed. Run: python -m pip install -r requirements.txt")
    try:
        with Comfy() as client:
            info = make_shot_list(module_text, meta, dish, descriptor, args.shots, args.max_clip, client, args.model, cuts=args.cuts,
                                  direction=direction_text(args.score, args.note))
    except Exception as error:
        print(f"\nThe call failed: {type(error).__name__}: {error}")
        sys.exit(1)

    total = sum(s["clip_seconds"] for s in info["shots"])
    print(f"\nStyle: {meta.get('name', args.style)}   Dish: {dish['dish_name']}   Character: {descriptor}")
    print(f"\nScene (the shared setup): {info['scene']}")
    for shot in info["shots"]:
        print(f"\nShot {shot['shot']}: {shot.get('beat', '')}  "
              f"[{shot['clip_seconds']}s clip, trimmed to {shot['trim_to_seconds']}s, uses {shot['reference']}]")
        print(f"  {shot['video_prompt']}")
        for key in ("dialogue", "voiceover", "spoken", "overlay_text"):
            if shot.get(key):
                print(f"  {key}: {shot[key]}")
    print(f"\nVideo step would generate {total}s of footage: about ${total * DOLLARS_PER_SECOND:.2f}.")
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / "shots.json"
    out.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
