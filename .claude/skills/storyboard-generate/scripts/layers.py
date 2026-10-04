#!/usr/bin/env python3
"""layers.py — deliver a graphic as LAYERS: the graphic on alpha, its background on its own,
and a composited preview for the board.

Why: an editor who composites wants the motion graphic floating on a transparent layer over a
background of THEIR choosing, and wants the designed background (often a subtle motion bed) as a
separate asset they can keep, swap or drop. The storyboard still needs to show the frame as
designed, so the preview is the graphic over its own background.

Contract (declared by the composition, read here — nothing project-specific lives in this file):
  mark every background element with  data-sb-layer="bg"
  - they must be DIRECT CHILDREN of the composition root ([data-composition-id]); the background
    pass hides every other direct child, so a marked element nested deeper would be hidden with
    its parent
  - everything not marked is the graphic
  - a composition with no marked element is delivered flat, exactly as before

Three outputs from two renders (never a third render for the preview):
  renders/<name>.graphic.mov  ProRes 4444 with alpha — background hidden, page transparent;
                              carries the row's sound effects, since they belong to the graphic
  renders/<name>.bg.mp4       the background alone, opaque, silent
  renders/<name>.mp4          graphic over background, composited by ffmpeg — what posters, the
                              board thumbnail, the review page and the checkers keep using

Each pass renders a temporary copy of the composition with one injected <style>; the source file
is never modified.
"""
import os, re, shutil, subprocess

# fallback for running this file directly; rebuild.py passes its own pinned version so the layer
# passes can never render on a different HyperFrames than a flat render
HF_PKG = "hyperframes@0.8.34"
BG_ATTR_RE = re.compile(r"""data-sb-layer\s*=\s*["']bg["']""")

GRAPHIC_CSS = ('[data-sb-layer="bg"]{display:none!important}'
               'html,body,[data-composition-id]{background:transparent!important}')
BG_CSS = '[data-composition-id] > *:not([data-sb-layer="bg"]){display:none!important}'


def declares_bg_layer(comp_path):
    with open(comp_path, encoding="utf-8") as f:
        return bool(BG_ATTR_RE.search(f.read()))


def _variant(html, css, strip_audio):
    if strip_audio:      # display:none does not silence an <audio>; the mixer reads the tag itself
        html = re.sub(r"<audio\b[^>]*>\s*</audio>", "", html, flags=re.S)
    tag = f'<style data-sb-layer-pass>{css}</style>'
    return html.replace("</head>", tag + "\n</head>", 1) if "</head>" in html else tag + html


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _has_audio(path):
    p = _run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
              "-of", "csv=p=0", path], None)
    return bool(p.stdout.strip())


def render_layers(graphics_dir, name, fast_capture=False, crf=None, log=print, hf_pkg=None):
    """Render compositions/<name>.html as layers. Returns {'graphic','bg','preview'} — paths
    relative to graphics_dir. Raises RuntimeError with the renderer's output on failure."""
    comp = os.path.join(graphics_dir, "compositions", name + ".html")
    with open(comp, encoding="utf-8") as f:
        html = f.read()
    out = {"graphic": f"renders/{name}.graphic.mov", "bg": f"renders/{name}.bg.mp4",
           "preview": f"renders/{name}.mp4"}
    passes = [("graphic", GRAPHIC_CSS, False, ["--format", "mov"]),
              ("bg", BG_CSS, True, [])]
    for key, css, strip, fmt in passes:
        tmp_rel = f"compositions/_layer_{key}_{name}.html"
        tmp = os.path.join(graphics_dir, tmp_rel)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(_variant(html, css, strip))
        try:
            cmd = ["npx", "--yes", hf_pkg or HF_PKG, "render", "--composition", tmp_rel,
                   "--quality", "high", "-o", out[key], "--quiet"] + fmt
            if not fast_capture:
                cmd += ["--experimental-fast-capture=false"]
            if crf and key == "bg":
                cmd += ["--crf", str(crf)]
            p = _run(cmd, graphics_dir)
            if p.returncode != 0 or not os.path.exists(os.path.join(graphics_dir, out[key])):
                raise RuntimeError(f"{key} layer render failed:\n{p.stdout}\n{p.stderr}")
        finally:
            os.remove(tmp)
        log(f"  rendered {out[key]}")

    g, b, pv = (os.path.join(graphics_dir, out[k]) for k in ("graphic", "bg", "preview"))
    # The graphic carries the sound. If the renderer left it out of the .mov, mux the row's own
    # sfx track in rather than deliver a silent graphic.
    sfx = os.path.join(graphics_dir, "assets", "sfx", name + ".wav")
    if os.path.exists(sfx) and not _has_audio(g):
        tmp = g + ".mux.mov"
        p = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", g, "-i", sfx, "-map", "0:v", "-map", "1:a",
                  "-c:v", "copy", "-c:a", "pcm_s16le", "-shortest", tmp], None)
        if p.returncode != 0:
            raise RuntimeError("could not mux sfx into the graphic layer:\n" + p.stderr)
        os.replace(tmp, g)
        log("  sfx muxed into the graphic layer")

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", b, "-i", g,
           "-filter_complex", "[0:v][1:v]overlay=format=auto:alpha=straight[v]", "-map", "[v]"]
    if _has_audio(g):
        cmd += ["-map", "1:a", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-crf", str(crf or 16), "-preset", "medium", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", pv]
    p = _run(cmd, None)
    if p.returncode != 0:
        raise RuntimeError("layer composite failed:\n" + p.stderr)
    log(f"  composited {out['preview']} (graphic over its background)")
    return out


if __name__ == "__main__":
    import sys
    print(render_layers(os.path.abspath(sys.argv[1]), sys.argv[2]))
