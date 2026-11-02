# Character sheet prompts

The character step has three parts. Part A uses a language model to check what was uploaded and write a short, consistent description of the character. Part B uses an image model (FLUX 3 by default) to generate the main character sheet. Part C generates a second, detail sheet with hands, a chest-down view and face expressions, for the shots where the main sheet is not close enough.

**Consent:** the app should tell users to upload only photos of themselves or of people who have agreed to it.

---

## Part A: look at the upload and describe the character

**Used by:** the language model (Gemini through Comfy Router by default)
**Input:** `{{character_image}}`: the uploaded image
**Output:** one JSON object, nothing else

This step runs first. It checks what kind of image was uploaded, so the app can skip work it does not need, and it writes the short description of the character that every video shot reuses.

| `image_type` | What the app does |
| :--- | :--- |
| `photo` | Make a character sheet (Part B), then the detail sheet (Part C) |
| `illustration` | Same as a photo |
| `character_sheet` | The upload already is a sheet. Skip Part B, use the upload as the sheet, and go to Part C |
| `multiple_people`, `no_person` | Stop and ask the user for a different image |

The app reports any logos or labels it sees, for information only. Clothing keeps its logos by default; the `--strip-logos` switch swaps them for plain versions.

Send everything in the block below to the model.

```text
You look at one uploaded image of a character and describe what is visible, so that an artist can draw the character consistently.

Step 1: decide what kind of image it is. Set "image_type" to exactly one of:
- "photo": one real person in a single view (a portrait, a snapshot, or a scene).
- "character_sheet": one person or character shown in several views or panels on one image, for example a large face close-up beside front, side and back full-body views. Sheets often have labels, rulers, tags or a plain backdrop.
- "illustration": a drawing, painting, 3D render or cartoon of one character in a single view.
- "multiple_people": several different people and no single main subject.
- "no_person": no person or character is visible.

Step 2: describe the character.
- Describe only what is visible: hair, build, skin tone, clothing, accessories, distinguishing visible features.
- For a character sheet, describe the one character that all the panels share.
- Do not guess names, ages, health, ethnicity, nationality, occupation, or personality.
- Do not name any brand, team, logo or other person. If logos, brand marks, readable text, labels or rulers appear anywhere in the image, set "has_logos_or_text" to true and say what and where in "logos_or_text_note" without naming the brand (for example "team logo on the cap, a height ruler and a tag on the sheet").
- Set "teeth_visible" to true only if teeth can be seen in at least one view. If teeth are visible, note anything distinctive (a gap, spacing, an unusual shape) in "distinguishing_features".
- Keep every field short and plain.
- If "image_type" is "multiple_people" or "no_person", set "status" to "needs_clarification", put a short question for the user in "note", and leave the other fields empty.

Return only this JSON object, with no commentary and no code fences:

{
  "status": "ok",
  "note": "",
  "image_type": "photo",
  "short_descriptor": "a person with short curly dark hair, round glasses, and a green denim jacket over a white tee",
  "hair": "short, curly, dark brown",
  "build": "medium build",
  "outfit": "green denim jacket over a plain white t-shirt, dark jeans",
  "accessories": ["round wire-frame glasses", "silver ring on right hand"],
  "distinguishing_features": ["small beard"],
  "teeth_visible": false,
  "has_logos_or_text": false,
  "logos_or_text_note": ""
}
```

`short_descriptor` is reused in every video shot prompt, so keep it to one sentence and make it describe the person as they appear in the upload.

---

## Part B: character sheet image prompt

**Used by:** the image model (FLUX 3 through Comfy Router by default)
**Input:** `{{character_image}}` as the reference image
**Output:** one character sheet image

The app sends this as the prompt, with the uploaded photo attached as the reference image. This prompt was tested by the project author: it turned a scene photo of a person in a kitchen into a clean sheet on white, with the same face, hair, outfit and accessories in every panel. The only change from the tested version is that the image tag in the original prompt is replaced with "the reference image."

```text
A multi-panel photo realistic character sheet layout on a white background, featuring a single, consistent character based on the reference image. On the far left, a high-detail, close-up feature bust. To the right of that, a vertical column featuring front, profile, and back head busts in high detail. To the right of that, a horizontal row of three matching-style full-body figures: direct front, three-quarter front, and three-quarter back views, all in neutral poses showing full gear. The perspectives and layout are precise, replicating exactly with the new character's details. No additional text.
```

### What the sheet contains

1. One large face-and-shoulders close-up (far left)
2. A column of three head studies: front, profile, back
3. Three full-body views: front, three-quarter front, three-quarter back

---

## Part C: detail sheet image prompt (hands, chest-down, faces)

**Used by:** the image model (same model as Part B)
**Input:** `{{character_image}}` and the character sheet from Part B, both attached as reference images
**Output:** one detail sheet image

This sheet exists for the shots the main sheet cannot cover: hands and forearms for the faceless styles, a chest-down view for torso-only framing, and a few facial expressions for the styles that show the face. Attaching the Part B sheet as well as the original photo helps keep the face, outfit and accessories identical.

This prompt follows the structure of the tested Part B prompt but has **not been tested yet**. Treat it as a first draft.

```text
A multi-panel photo realistic detail sheet on a white background, featuring the same single, consistent character as the reference images. On the left, two large stacked panels: the top panel shows both forearms held out in front of the body toward the camera, hands palm-down with the backs of the hands facing the camera and fingers relaxed, never held behind the back; the bottom panel shows both palms facing up with fingers gently curled in a neutral, cooking-ready pose. In the center, one tall panel showing a chest-down front view from the collarbone to the waist, hands resting at the sides, with the clothing, pockets, buttons, trim and accessories the character actually wears in sharp detail and no head visible. On the right, a grid of exactly four face close-ups, two across and two down, of the character: a neutral expression, a soft closed-mouth smile, a wide natural smile with the upper and lower teeth clearly visible in sharp detail, and eyes closed savoring a bite with a small satisfied smile. Anatomically correct hands with five fingers each. Show exactly the watches, rings and bracelets visible in the reference images, on the same wrist or finger, and no more: if the reference shows one watch, show one watch. Skin tone, hair, outfit and accessories match the reference images exactly, with the same lighting style and image quality as the character sheet. Do not add any clothing, aprons or accessories that are not in the reference images. No additional text.
```

### What the sheet contains

1. Backs of both hands and forearms (top left)
2. Both palms up (bottom left)
3. A tall chest-down front view with the head out of frame (center)
4. Four face close-ups in a grid: neutral, soft closed-mouth smile, wide smile showing the upper and lower teeth, eyes closed savoring a bite (right)

### Which shots use which sheet

| Shot type | Reference sheet |
| :--- | :--- |
| Full body, standard face shots | Part B character sheet |
| Hands, forearms, chest-down framing (faceless styles) | Part C detail sheet |
| A specific facial expression, or any shot where the character eats, bites, laughs or smiles with teeth visible | Part C detail sheet |
| Face and hands clearly in the same shot | Both |

The shot-list prompt chooses one of these for every shot and writes it into the `reference` field.

---

## Notes for later

- Image models often struggle with hands. If the hands in Part C come out wrong, regenerate, or split the hands into their own image.
- If the Part C panels look crowded, drop the face panels to three (neutral, wide smile with teeth, savoring). Keep the teeth panel.
- Teeth are only as faithful as the source photo. If the original image does not show the character's teeth, the model will invent them. For a real person, start from a photo with a natural smile that shows teeth. Once a teeth panel looks right, reuse it as the reference for every eating shot so the teeth stay consistent.
- Part A's `short_descriptor` is not used in the sheet prompts, but it is used in every video shot prompt.
- Whether FLUX 3 on Comfy Router accepts reference images, and how many, is not yet confirmed. If it does not, switch Parts B and C to an image model that does. Ask a Comfy dev at the build night.
- How many reference images the video model accepts per shot is also unconfirmed. Test with one sheet first, then two.
- Faceless style modules use only the body, hands, outfit and accessories from the sheets.
- A strongly styled outfit (like the floral dress, apron and headband in the test) makes the faceless modules funnier, because the character is recognizable from the chest down.
