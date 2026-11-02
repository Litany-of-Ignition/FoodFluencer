# FoodFluencer

One photo and one food in, a talking food-review video out.

You pick the score. The reviewer gets messier with every bite.

Built on the Comfy API with MiniMax H3, for the ComfyUI "Open Source Higgsfield" competition.

## How it works

1. Your photo becomes a character sheet (face, hands, teeth).
2. A food, as text, a photo, or both, becomes a recipe.
3. A score from 1 to 10 becomes a 15-second dashcam review, with cuts, speech and sound.

## Setup

You need Python 3.10 or newer and your own Comfy API key from <https://platform.comfy.org>.

```
python -m pip install -r requirements.txt
setx COMFY_API_KEY "your-key-here"
```

Open a new PowerShell window after `setx`.

## Run

Put your photo in `input\`, then:

```
python scripts\analyze_character.py input\me.jpg
python scripts\make_sheet.py input\me.jpg
python scripts\make_detail_sheet.py input\me.jpg
python scripts\food_intake.py --text "birria tacos"
python scripts\shot_list.py --score 3
python scripts\make_videos.py
```

The video is saved in `output\clips\`.

## Cost

About $0.13 per second of video, so a 15-second review is about $2. The character sheets cost about 25 cents, once. Each script shows its cost before spending.

## Notes

Only use photos of yourself or of people who agreed.

## License

MIT
