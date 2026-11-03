<img width="1024" height="1024" alt="FoodFluencer Logo new" src="https://github.com/user-attachments/assets/29fa59cb-52d1-4fce-8fd7-f4bf66a8dfbe" />

# FoodFluencer

One photo/video and one food in, a talking food-review video out.

You pick the score. The reviewer gets messier with every bite.

Built on the Comfy API with MiniMax H3, for the ComfyUI "Open Source Higgsfield" competition.

## How it works

1. Your photo becomes a character sheet (face, hands, teeth). Or give it a selfie video, which is used directly for your face and voice.
2. Your food (as text, a photo or both) is described, so the video can show it.
3. A score from 1 to 10 becomes a 15-second dashcam review, with cuts, speech and sound.

## Examples

One selfie video in, three reviews out. Same reviewer, different verdicts.

**The input** (here a 5-second selfie)


https://github.com/user-attachments/assets/e00076c8-e9f9-4822-aa51-010f763cb542



**1 out of 10: burrito bowl**


https://github.com/user-attachments/assets/b5ba30af-ff0d-423e-a8ba-4b89d211e76c



**8 out of 10: double-decker burger**


https://github.com/user-attachments/assets/2a179831-7ea5-40d0-a3c1-36a8ec74377c



**10 out of 10: ice cream sundae**


https://github.com/user-attachments/assets/9b73338e-35ab-412c-add9-8806023916a0



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
