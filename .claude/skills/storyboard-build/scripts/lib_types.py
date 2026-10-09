"""Shared visual-type vocabulary and inference for the storyboard pipeline.

One place defines the eight visual types (mirroring the installed vsl-storyboard
skill) plus the section + status vocabulary the sheet uses. Both the sheet sync
and the generator import from here so a type is spelled and colored one way only.
"""

VISUAL_TYPES = {
    "TALKING HEAD":               "2E75B6",
    "B-ROLL":                     "548235",
    "CUSTOM GRAPHIC":             "7030A0",
    "SCREENCAST":                 "ED7D31",
    "TESTIMONIAL":                "D6408C",
    "TALKING HEAD + LOWER THIRD": "00A19A",
    "B-ROLL / GRAPHIC":           "8B5A2B",
    "GRAPHIC / SCREENCAST":       "5B7A99",
    "TALKING HEAD + OVERLAY":     "C9A227",
}
TALKING_HEAD_TYPES = {"TALKING HEAD", "TALKING HEAD + LOWER THIRD"}
# Talking head shot wide (4K, waist up) and reframed so a transparent graphic overlay fits beside
# it or as a lower third. NOT in TALKING_HEAD_TYPES: these rows keep brief/direction/notes.
# Placement lives in visual_direction + brief: "lower third" | "left" | "right" (the side the
# overlay sits on; the presenter is reframed to the opposite side).
OVERLAY_TYPES = {"TALKING HEAD + OVERLAY"}
OVERLAY_PLACEMENTS = ["lower third", "left", "right"]
GENERATED_BY_TYPE = {  # which /generate route each visual type takes
    "CUSTOM GRAPHIC": "hyperframes",
    "GRAPHIC / SCREENCAST": "hyperframes",
    "B-ROLL": "video",
    "B-ROLL / GRAPHIC": "video",
    "TESTIMONIAL": "video",
    "SCREENCAST": "placeholder",
    "TALKING HEAD": "still",
    "TALKING HEAD + LOWER THIRD": "still",
    "TALKING HEAD + OVERLAY": "hyperframes",   # alpha overlay; board poster = overlay over a silhouette
}
# Which motion engine animates this type's still into a clip (the /storyboard-motion step).
#   hyperframes = deterministic HTML/CSS/GSAP render — pixel-exact text/data; DEFAULT for info graphics
#   higgsfield  = image-to-video — organic/atmospheric shots with no exact text to protect
#   none        = captured footage (talking head, screencast); not animated from a still
MOTION_ENGINE_BY_TYPE = {
    "CUSTOM GRAPHIC": "hyperframes",
    "GRAPHIC / SCREENCAST": "hyperframes",
    "B-ROLL / GRAPHIC": "hyperframes",   # mixed: protect any on-frame text/data
    "B-ROLL": "higgsfield",
    "TESTIMONIAL": "higgsfield",
    "SCREENCAST": "none",
    "TALKING HEAD": "none",
    "TALKING HEAD + LOWER THIRD": "none",
    "TALKING HEAD + OVERLAY": "hyperframes",   # text/data on alpha: never higgsfield
}
MOTION_ENGINES = ["hyperframes", "higgsfield", "none"]

STATUSES = ["Draft", "Generating", "Generated", "Approved", "Reshoot"]

def normalize_type(vtype: str) -> str:
    key = (vtype or "").strip().upper()
    if key in VISUAL_TYPES:
        return key
    for k in VISUAL_TYPES:
        if k.replace(" ", "") == key.replace(" ", ""):
            return k
    raise ValueError(f"Unknown visual_type: {vtype!r}")

def default_motion_engine(vtype: str) -> str:
    """The engine that animates this visual type's still (see MOTION_ENGINE_BY_TYPE).
    Information graphics default to deterministic hyperframes so text/numbers stay exact."""
    try:
        return MOTION_ENGINE_BY_TYPE.get(normalize_type(vtype), "hyperframes")
    except ValueError:
        return "hyperframes"

def infer_type(direction: str) -> str:
    """Best-effort visual type from a free-text visual-direction line."""
    d = (direction or "").lower()
    if not d.strip():
        return "TALKING HEAD"
    has_th = "talking head" in d
    if "overlay" in d and (has_th or "presenter" in d):
        return "TALKING HEAD + OVERLAY"
    if "testimonial" in d or "wins channel" in d:
        return "TESTIMONIAL"
    if "screencap" in d or "screen recording" in d or "screencast" in d or "coinmarketcap" in d:
        return "SCREENCAST"
    if "custom graphic" in d or "lower third" in d or "title card" in d or "text overlay" in d \
       or "diagram" in d or "graphic:" in d:
        if "lower third" in d:
            return "TALKING HEAD + LOWER THIRD"
        return "CUSTOM GRAPHIC"
    if "cutaway" in d:
        return "B-ROLL"
    if "b-roll" in d or "b roll" in d:
        if has_th:
            return "B-ROLL / GRAPHIC"
        return "B-ROLL"
    if has_th:
        return "TALKING HEAD"
    return "B-ROLL"
