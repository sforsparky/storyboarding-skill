---
name: storyboard-motion
description: >
  Turn static HyperFrames infographic stills into animated Higgsfield clips — but plan first. Build
  an HTML "motion design sheet" that proposes per-shot animation style, text design, camera angles
  and camera movements, present it for approval, and ONLY after the user approves, generate the
  clips (silent, image-to-video). Use to enhance brand infographic stills into high-tech motion.
---

# /storyboard-motion — stills → motion design sheet → animated clips

Approval is a hard gate. This skill NEVER generates video before the user approves the motion
design sheet. The sheet is the deliverable of phase 1; generation is phase 2.

## Inputs
- One or more stills: HyperFrames posters (`assets/NNN_slug.png`), `/storyboard-generate series`
  frames, or any brand infographic frames the user points at.
- The project brand (`brands/<brand>/brand.json`) for palette, type, motifs, `graphic_style`.

## Phase 1 — build the motion design sheet (HTML), then STOP for approval
1. For each still, write a motion spec: `style` (e.g. high-tech company / holographic / clean
   corporate), `text_design` (how titles/numbers animate in), `camera_angle` (e.g. straight-on,
   low 3/4, top-down tilt), `camera_move` (e.g. slow push-in, orbit, parallax rack-focus,
   crane-up), `duration` (3-12s), and the exact Higgsfield `prompt` that will be used.
2. Assemble one self-contained sheet:
   `scripts/build_motion_sheet.py shots.json motion-sheet.html`
   It embeds each still as a data URI and renders a card per shot: the still, style/text/camera
   chips, duration, and the generation prompt. `shots.json` schema below.
3. Present it for approval — publish as an Artifact (preferred; renders inline and is shareable)
   or send the HTML file. Then STOP and ask for approval or edits. Do not proceed to phase 2 until
   the user says go. Fold their edits back into `shots.json` and rebuild the sheet.

## Phase 2 — generate (only after approval)
Per approved shot, image-to-video with the still as the start frame:
1. Upload the local still to Higgsfield: `media_upload_widget` (as the only tool that turn) to get
   a `media_id`. Never pass a local path or https URL as the media value.
2. `generate_video` with model `cinematic_studio_video_v2` (Cinema Studio):
   - `medias: [{value: <media_id>, role: "start_image"}]`
   - `params.sound: "off"` (silent — the editor sets sound), `params.genre` to match the style,
     `params.multi_shots: true` with a `multi_prompt` when the shot wants several camera angles,
     `params.speedramp` for time effects. `aspect_ratio: "16:9"`, `duration` from the spec.
   - Preflight with `get_cost:true`; batch several shots with `generate_video_batch` + `jobs_wait`.
3. Download to `assets/NNN_slug_motion.mp4`, `generate_row.py silence` it, extract a poster.
4. If tied to a storyboard row, register the clip in that row's `assets[]` with kind `motion` and
   set status `Generated`; re-run `/storyboard-sheet`.

## shots.json schema
```json
{
  "title": "Brand — motion design sheet",
  "brand": "acme",
  "shots": [
    {
      "id": "s1", "still": "assets/007_portfolio-drop.png", "slug": "portfolio-drop",
      "style": "High-tech corporate, holographic depth",
      "text_design": "Numbers count up then lock; label fades in on a glass panel",
      "camera_angle": "Low 3/4", "camera_move": "Slow push-in with subtle parallax",
      "duration": 6,
      "prompt": "Animate this infographic in a high-tech company style: holographic depth, glass panels, the bar drop and the percentage animating, clean kinetic typography; low 3/4 angle, slow push-in with parallax. Silent."
    }
  ]
}
```
Notes: `still` paths are relative to `shots.json`. Keep the brand palette/motif in every `prompt`
so animated shots match the stills. Video is always silent.
