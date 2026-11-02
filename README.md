# FoodFluencer

Turn one picture of a person and one food into a short food-influencer video, with the person talking.

Built for the ComfyUI "Open Source Higgsfield" competition. It runs on **one Comfy API key** and uses **MiniMax H3** (through the Comfy Router) for the video, plus Gemini models for the writing and character sheets.

## What it does

1. **Character:** you give it a photo (or a ready-made character sheet). It checks what it is, makes a character sheet if needed, and makes a close-up sheet of hands and faces (teeth included) so the person looks the same in every shot.
2. **Food:** you give it a dish as text, a photo, or both. It turns it into a filmable recipe.
3. **Style:** the app loads a style module. A style is a plain Markdown file in `modules/` that describes a camera, lens, lighting, sound and editing recipe. Gemini writes a shot list from it.
4. **Verdict (review styles):** you choose a score from 1 to 10 and the review honestly matches it.
5. **Video:** H3 makes the clip, with cuts, speech and sound in a single generation.

The style is **Parked Car Review**: a phone on a dashboard, an honest takeout review, a spoken score out of 10 that you choose, and a running gag where the reviewer gets steadily messier with sauce and grease and never notices.

Styles are plain Markdown files in `modules/`, so new ones can be added by copying `parked-car-review.md` and editing it.

## You need your own Comfy API key

Nothing here uses anyone else's key. Create an account at <https://platform.comfy.org>, add a few dollars of credit, create an API key, and keep it private.

Typical cost: character sheets about 25 cents once, the video about $0.13 per second at 768p (a 15-second video is about $2). Every script that spends credits shows the cost first.

## Setup (Windows PowerShell)

```
python -m pip install -r requirements.txt
setx COMFY_API_KEY "your-key-here"
```

Close PowerShell and open a new window after `setx`. You also need Python 3.10 or newer. ffmpeg is only needed for `scripts\stitch.py`.

## Quick start (command line)

Put your photo in `input\` first. Run these in order from the project folder:

```
python scripts\analyze_character.py input\me.jpg
python scripts\make_sheet.py input\me.jpg
python scripts\make_detail_sheet.py input\me.jpg
python scripts\food_intake.py --text "birria tacos"
python scripts\shot_list.py --score 3
python scripts\make_videos.py
```

If your photo already is a character sheet, `make_sheet.py` tells you and stops. The finished clip is saved in `output\clips\`. If you already have several sheets in `output\`, pass the ones to use with `--upload`, `--sheet` and `--detail`.

## How it is organized

- `prompts/`: the prompts for the character check, the character sheets, the food intake and the shot list.
- `modules/`: the style, as a Markdown file with the camera, lens, lighting, sound, edit rhythm and story arc.
- `scripts/`: one small script per step.

Output and your photos stay on your computer: `input/` and `output/` are not committed.

## Content notes

Styles are original genre recipes, not copies of any creator. Only upload photos of yourself or people who agreed. Keep results safe for work.

## License

MIT. See `LICENSE`.
