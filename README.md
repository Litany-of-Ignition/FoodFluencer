# FoodFluencer

One photo/video and one food in, a talking food-review video out.

You pick the score. The reviewer gets messier with every bite.

Built on the Comfy API with MiniMax H3, for the ComfyUI "Open Source Higgsfield" competition.

## How it works

1. Your phot becomes a character sheet (face, hands, teeth). Or give it a selfie video, which is used directly for your face and voice.
2. Your food (as text, a photo or both) is described, so the video can show it.
3. A score from 1 to 10 becomes a 15-second dashcam review, with cuts, speech and sound.

## Examples

One selfie video in, three reviews out. Same reviewer, different verdicts.

**The input** (a 6-second selfie)

**1 out of 10: burrito bowl**

**8 out of 10: double-decker burger**

**10 out of 10: ice cream sundae**

## Setup

You need Python 3.10 or newer and your own Comfy API key from <https://platform.comfy.org>.

The app asks for your key when it opens. To run the scripts without the app, set it once with `setx COMFY_API_KEY "your-key-here"` and open a new PowerShell window.

## Run

On Windows, double-click `Start FoodFluencer.bat`. The first time, it installs what the app needs. For a desktop icon, double-click `Add Desktop Shortcut.bat` once.

Or from a terminal:

```
python -m pip install -r requirements.txt
python app.py
```

A page opens in your browser. Add a photo, type a food, pick a score, and press the button. The video is saved in `output\jobs\`.

Or run the steps yourself, with your photo in `input\`:

```
python scripts\make_sheet.py input\me.jpg
python scripts\make_detail_sheet.py input\me.jpg
python scripts\food_intake.py --text "birria tacos"
python scripts\shot_list.py --score 3
python scripts\make_videos.py --upload input\me.jpg
```

## Cost

About $0.13 per second of video, so a 15-second review is about $2. The character sheets cost about 25 cents, once. The app and the scripts show the cost before spending.

## Notes

Only use photos of yourself or of people who agreed.

## License

MIT
