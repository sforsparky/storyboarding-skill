---
name: storyboard-motion
description: >
  Turn static brand infographic stills into animated clips — but plan first. Build an HTML "motion
  design sheet" that proposes, per shot, the animation style, text design, camera angle, camera
  movement, and which ENGINE renders it: deterministic HyperFrames (pixel-exact text/data) or
  Higgsfield image-to-video (organic/atmospheric). Present it for approval, and ONLY after the user
  approves, generate the clips (silent). Use to enhance brand infographic stills into high-tech motion.
---

# /storyboard-motion — stills → motion design sheet → animated clips

Approval is a hard gate. This skill NEVER generates video before the user approves the motion
design sheet. The sheet is the deliverable of phase 1; generation is phase 2.

## Inputs
- One or more stills: HyperFrames posters (`assets/NNN_slug.png`), `/storyboard-generate series`
  frames, or any brand infographic frames the user points at.
- The project brand (`brands/<brand>/brand.json`) for palette, type, motifs, `graphic_style`.

## Choose the engine PER SHOT (the fidelity rule)

Every shot declares an `engine`. Pick it from what the shot must protect:

- **`hyperframes` — deterministic HTML/CSS/GSAP render. This is the DEFAULT for any information-
  bearing shot.** Use it whenever the frame carries text, numbers, charts, candles, bars, counters,
  a logo lockup, or kinetic typography whose legibility and exact values matter. The render is
  pixel-exact and reproducible — a "+284%" counts up truthfully, candles and trend lines draw
  precisely, bars grow to real heights. Image-to-video models re-interpret the still and WARP fine
  text and data (drifting digits, melting glyphs, wrong chart shapes), which is unacceptable on a
  finance/data VSL — so information graphics do NOT go to Higgsfield.
- **`higgsfield` — image-to-video (Cinema Studio), the still as the start frame.** Use it for
  atmospheric, photographic, or organic shots where there is little exact text to protect: b-roll
  moods, textured backgrounds, a presenter/plate, a purely decorative reveal. Reinterpretation is a
  feature here, not a risk.

When a shot is mixed (a hero number over a lush moving background), prefer `hyperframes` and animate
the background there, or split it into two shots. State the chosen engine and one-line reason in the
plan. The user can override any shot's engine — fold that back into `shots.json` and rebuild.

## Phase 1 — build the motion design sheet (HTML), then STOP for approval
1. For each still, write a motion spec: `engine` (`hyperframes` | `higgsfield`, per the rule above),
   `style` (e.g. high-tech company / holographic / clean corporate), `text_design` (how
   titles/numbers animate in), `camera_angle` (e.g. straight-on, low 3/4, top-down tilt),
   `camera_move` (e.g. slow push-in, orbit, parallax rack-focus, crane-up), `duration` (3-12s), and
   the `prompt` — for `higgsfield` this is the exact generation prompt; for `hyperframes` it is the
   motion direction (cited HyperFrames rules/blueprints, e.g. `3d-camera-flight`,
   `counting-dynamic-scale`, `stat-bars-and-fills`, `svg-path-draw`).
2. Assemble one self-contained sheet:
   `scripts/build_motion_sheet.py shots.json motion-sheet.html`
   It embeds each still as a data URI and renders a card per shot: the still, an ENGINE badge, the
   style/text/camera chips, duration, and the prompt/motion direction. `shots.json` schema below.
3. Present it for approval — publish as an Artifact (preferred; renders inline and is shareable)
   or send the HTML file. Then STOP and ask for approval or edits. Do not proceed to phase 2 until
   the user says go. Fold their edits (including engine overrides) back into `shots.json` and rebuild.

## Phase 2 — generate (only after approval)

Route each approved shot by its `engine`.

### 2A · `hyperframes` shots (deterministic — default for information graphics)
Recreate the still as an animated, seek-safe HyperFrames composition. Load `/hyperframes` and route
through `/general-video` (or `/motion-graphics` for a single ≤10s unit).
1. Scaffold once per project: `npx hyperframes init "videos/<project>" --non-interactive --example=blank --skill=general-video`.
   Copy the shared background / logos into the project's `assets/`.
2. Author a scene per shot (one composition, or one per shot): rebuild the frame's elements in
   HTML/CSS at final state, then animate from the cited rules — camera on an inner `.world`
   (perspective on `.stage`, `preserve-3d`), kinetic type, count-ups, candle/bar draws. Keep the
   brand palette/type; SF-style rounded display type falls back to an embeddable Poppins in the
   render engine (embed a licensed webfont only if the exact wordmark font is required).
3. `npx hyperframes check` until **0 errors** (fix seek-safety: `fromTo` not CSS+GSAP transform
   conflicts, boundary `tl.set` hard-kills, static `d` before `getTotalLength`, contrast, overlap).
   Snapshot scene midpoints (`npx hyperframes snapshot --at ...`) and eyeball the contact sheet.
4. `npx hyperframes render` → MP4 (silent; the editor sets sound). Copy to `assets/NNN_slug_motion.mp4`.

### 2B · `higgsfield` shots (image-to-video — atmospheric only)
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

### Register (both engines)
If a shot is tied to a storyboard row, register the clip in that row's `assets[]` with kind `motion`
and set status `Generated`; re-render the board xlsx (`/storyboard-build`) so the new thumbnail shows.

## shots.json schema
```json
{
  "title": "Brand — motion design sheet",
  "brand": "acme",
  "shots": [
    {
      "id": "s1", "still": "assets/007_portfolio-drop.png", "slug": "portfolio-drop",
      "engine": "hyperframes",
      "style": "High-tech corporate, holographic depth",
      "text_design": "Numbers count up then lock; label fades in on a glass panel",
      "camera_angle": "Low 3/4", "camera_move": "Slow push-in with subtle parallax",
      "duration": 6,
      "prompt": "counting-dynamic-scale on the %, stat-bars-and-fills bars grow, 3d-camera-flight low-3/4 push-in with parallax. Silent."
    },
    {
      "id": "s2", "still": "assets/010_broll-desk.png", "slug": "broll-desk",
      "engine": "higgsfield",
      "style": "Warm cinematic b-roll",
      "text_design": "None — atmospheric only",
      "camera_angle": "Straight-on", "camera_move": "Slow drift + rack-focus",
      "duration": 5,
      "prompt": "Animate this desk scene, warm cinematic b-roll, slow drift with a gentle rack-focus. Silent."
    }
  ]
}
```
Notes: `still` paths are relative to `shots.json`. `engine` defaults to `hyperframes` for any
information/data/text shot; reserve `higgsfield` for atmospheric shots with no exact text to protect.
Keep the brand palette/motif in every `prompt` so animated shots match the stills. Video is always silent.
