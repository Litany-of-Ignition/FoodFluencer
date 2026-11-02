# Shot list prompt

**Used by:** the language model (Gemini through Comfy Router by default)
**Input:** a style module, the dish JSON, the character description, and a shot count
**Output:** one JSON object, nothing else

The app fills the `{{...}}` fields, sends everything below the line to the model, and parses the JSON that comes back. If the JSON does not parse, the app retries once. The video model never sees this file. It only sees each shot's `video_prompt`.

---

You write a shot list for a short food video. A different video model will make each shot separately from the prompt you write, and it has no memory of the other shots. So every `video_prompt` must stand on its own.

## Inputs

**Style module (follow it closely):**

{{style_module_markdown}}

**Dish:**

{{dish_json}}

**Character descriptor (reuse it word for word when the character appears):**

{{short_descriptor}}

**Direction from the user (follow it; "none" means no extra direction):**

{{user_direction}}

**Number of shots to write:** {{shot_count}}
**Longest clip the video model can make:** {{max_clip_seconds}} seconds

## How to build the shots

1. **Pick the beats.** Use the style module's story arc, and map the dish's recipe steps onto it. When there are fewer shots than beats, combine neighbouring beats, but always include the opening hook and the finished dish.
2. **Respect `face_visibility` in the module's frontmatter.**
   - `faceless`: never mention the face, eyes, expression or head. Frame from the collarbone down, or on hands only.
   - `partial`: follow the module's "Character on screen" section about when the face appears.
   - `full`: the face may appear.
3. **Write each `video_prompt` in plain visual language**, 60-120 words, in this order:
   1. shot size and camera angle
   2. camera movement (or "locked-off, no camera movement")
   3. lens feel and depth of field
   4. what the character is doing, using the character descriptor when they are visible
   5. the food, using the dish's colors, textures and vessel
   6. lighting, set and color from the module
   7. one short phrase of gear flavor from the module's gear notes (for example, "shot on a full-frame mirrorless camera with a 35mm lens")
4. **Write `audio_direction`** for each shot from the module's audio section and the step's `sounds`. Describe sounds in words. Do not include mix numbers.
5. **Use the module's edit rules.** Set `trim_to_seconds` to a length within the module's `cut_min` and `cut_max`. Set `clip_seconds` to the length the video model should generate, which is never more than `{{max_clip_seconds}}` and never less than `trim_to_seconds`.
6. **Speech.** If the module's `speech` is `on-camera`, put what she says in `dialogue`, written as one continuous stretch of natural talking that fills the clip (at most {{max_dialogue_words}} words). If it is `voiceover`, put it in `voiceover` the same way. (When the hard-cut rule says to write speech inside the segments, follow that rule instead.) If it is `none`, leave both empty.
7. **Text overlays** are added later by the editing script, never by the video model. Put them in `overlay_text` only when the module's edit rules call for them. Never ask the video model to render text.
8. **Choose the reference sheet for each shot** and write it in `reference`. The app has two reference sheets of the character:
   - `character_sheet`: a large face close-up, front, profile and back head studies, and three full-body views.
   - `detail_sheet`: hands and forearms, a chest-down view with no head, and three face expressions (neutral, warm smile, eyes closed savoring a bite).
   Use `character_sheet` for full-body shots and for ordinary face shots. Use `detail_sheet` for shots of hands, forearms or the chest-down torso, and for shots that need a specific facial expression. Use `both` when a shot needs several of these, such as a face and hands clearly in the same frame. Any shot where the character eats, bites, laughs or smiles with teeth visible must use `detail_sheet` or `both`, because the detail sheet holds the teeth reference. For a `faceless` module, never use `character_sheet` alone.

## Rules

{{cut_rules}}
- **Write one `scene`.** Before the shots, write a single `scene` paragraph (40-80 words) that fixes the one location for the whole video: the room or vehicle, where the character sits or stands, the main camera position and angle, the background objects, and the lighting. Say it in plain, unambiguous words (for example, "the woman sits in the driver's seat, seen from a phone on the dashboard, the steering wheel at the left edge of frame"). The app turns it into a reference picture that every shot must match, so every `video_prompt` must agree with it.
- **Same room in every shot.** Each shot is made separately with no memory of the others, so choose one set description from the module's "Set and props" and "Lighting" at the start (for example, a butcher-block island, lush indoor plants, shelves of ingredients, a large warm softbox) and repeat it, worded the same, in every `video_prompt` where the background is visible. Extreme close-ups of food may leave out the background.
- **Natural dialogue.** A `dialogue` or `voiceover` line must sound like something a real person says while cooking: concrete, specific to the dish, plain words. No slogans, catchphrases, rhymes, chants or rule-of-three lists. Speed: about 2.5 words per second. A line may be at most {{max_dialogue_words}} words.
- **Follow the module's running gag.** If the module has a "Running gag" section, make it visible in every segment or shot and let it build from one to the next, exactly as the module describes. In each segment's description, say what the mess looks like right now and where it is (for example, "a dab of red broth on his chin and a greasy shine on his fingers"), using the dish's own colors. Do this whatever the score is, and never let a spoken line mention it.
- **No repetition.** Across all of the speech, never repeat a phrase, a pet word or a sentence shape. Every line adds a new fact, opinion or joke.
- **Keep the food whole.** The video model turns food that is torn, split or pulled apart into duplicates. Never describe food being torn, split, broken in half or pulled apart. Show it held, dipped, bitten, poured, flipped or plated instead.
- **Recipe coverage.** Unless the module's concept skips the cooking (a takeout review, for example), show the dish's recipe steps in order: an opening hook, then a different recipe step for each following shot (or each cut), and the finished dish last. If there are fewer shots than steps, merge neighbouring steps. Never skip a step silently and never repeat one.
- Use only the dish and the character provided. Do not add other people, except the local cook the Field Documentary module calls for.
- Do not mention any brand, logo, restaurant, creator, or copyrighted character.
- Do not name the style module or any real person inside a `video_prompt`.
- Keep everything safe for work.
- Obey the module's "Avoid" list.
- Set `aspect_ratio` from the module's frontmatter.

## Output format

Return only this JSON object. Do not add commentary or code fences.

```json
{
  "module_id": "headless-studio",
  "aspect_ratio": "16:9",
  "scene": "A clean modern studio kitchen with a butcher-block island, lush indoor plants and shelves of spice jars behind. The woman stands behind the island facing the camera at eye level, a large warm softbox lighting her from the front left.",
  "shots": [
    {
      "shot": 1,
      "beat": "Hook: finished dish glimpsed",
      "recipe_step": 5,
      "reference": "detail_sheet",
      "clip_seconds": 5,
      "trim_to_seconds": 3.0,
      "video_prompt": "Locked-off medium shot from a high angle across a clean kitchen island, frame cut at the collarbone so no head is visible. A person in a green denim jacket over a white tee and a silver ring on the right hand lifts a halved smash burger on a paper-lined tray toward the center of frame. Melted yellow cheese stretches and glistens, steam curls upward. Large soft overhead light, clean modern studio kitchen, neutral natural color, shallow depth of field on the burger. Shot on a full-frame mirrorless camera with a 35mm lens at f/4.",
      "audio_direction": "calm, close kitchen sounds: soft paper rustle and a faint sizzle fading underneath",
      "dialogue": "",
      "voiceover": "Today, we're making the burger everyone argues about.",
      "overlay_text": ""
    }
  ]
}
```

Write exactly {{shot_count}} shots.
