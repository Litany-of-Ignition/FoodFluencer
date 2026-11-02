# Style modules

Each file in this folder is one food-video "style module." The app ships with one, `parked-car-review`. To add another, copy that file, give it a new `id`, and edit it. The app loads a module, combines it with the character sheet and the dish, and asks a language model to write a shot list in that style.

## How a module is used

| Section | Goes to | Notes |
| :--- | :--- | :--- |
| Frontmatter | The app / stitching script | Aspect ratio, cut length, face visibility, speech type |
| Story arc | Shot-list writer (LLM) | Beats the video should hit; mapped onto the recipe steps |
| Character on screen | Shot-list writer (LLM) | How much of the character sheet is ever shown |
| Visual prompt tokens | Video model prompt | Framing, lens feel, lighting, set, color |
| Gear notes | Video model prompt (short flavor phrase) | Camera, lens, light and mic hardware; documentation first, prompt flavor second |
| Audio direction | Video model prompt (native audio) or post-processing | Described in words; mix specs are for ffmpeg if needed |
| Edit rules | Shot-list writer and stitching script | Cut length and cut style. The shot list writes the cuts inside one generated clip as "Cut to" segments; text overlays are added afterward |
| Avoid | Negative guidance | What would break the style |

## Frontmatter keys

- `id`: matches the file name
- `name`: display name in the app
- `aspect_ratio`: `"9:16"` or `"16:9"`
- `cut_avg`, `cut_min`, `cut_max`: shot length in seconds, used by the stitcher
- `face_visibility`: `faceless`, `partial`, or `full`
- `speech`: `none`, `voiceover`, or `on-camera`
- `camera_motion`: `locked`, `handheld`, `gimbal`, or `mixed`

## Faceless modules

A faceless module crops the character at the chest or hands. The character sheet still sets the body, clothing, hands and accessories, so the person is recognizable without a face. 

## Style, not people

Modules describe production techniques (framing, lighting, pacing, sound). They do not name creators, reuse catchphrases, or copy signature gestures. The character always comes from the user's own character sheet.
