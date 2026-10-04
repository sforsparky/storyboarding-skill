#!/usr/bin/env python3
"""sfx_track.py — build a composition's sound-effects track from a cue sheet, timed to its timeline.

Cue sheet: <graphics>/sfx/<composition>.json
  {
    "sounds": { "tap": "assets/sfx/src/click-soft.mp3", ... },   # file sounds, relative to graphics root
    "cues": [
      { "sound": "tap",  "at": "startOf('.mark.loss', i)", "repeat": "countOf('.mark.loss')",
        "peak": -22, "pan": "xOf('.mark.loss', i)" },
      { "sound": "air",  "at": "WAVE_T", "len": "WAVE_D", "shape": "swell", "band": [500, 5000],
        "peak": -24, "pan": [-0.6, 0.6] }
    ]
  }
`at`/`len`/`pan`/`repeat` may be expressions evaluated INSIDE the page (see _sfx_probe.mjs), so a cue
follows the animation when it is retimed. `pan` as a number in frame px (from xOf) is mapped to a
gentle -0.35..0.35; a [from, to] pair sweeps across the cue.

Built-in sound "air": a synthesized noise whoosh. Noise has no pitch, so it cannot fight the music's
key, and nothing needs a licence. shape: "swell" (rises, quick tail), "rise", "fall", "puff" (short
symmetric). band: [lo, hi] Hz, swept lo->hi for swell/rise.

Mix rules (so the track sits under a producer's music): every cue is high-passed at 150 Hz, levelled
to its own `peak` dBFS (default -24), and the finished track is capped at -16 dBFS.

usage: sfx_track.py <graphics_dir> <composition_name> [--write-audio-tag]
  --write-audio-tag  add/refresh the <audio id="sfx"> element in the composition
"""
import json, os, re, subprocess, sys, threading, http.server, socket, wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
HERE = os.path.dirname(os.path.abspath(__file__))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def resolve_cues(gdir, name, spec_path):
    comp = os.path.join(gdir, "compositions", name + ".html")
    html = open(comp, encoding="utf-8").read()
    comp_id = re.search(r'data-composition-id="([^"]+)"', html).group(1)
    dur = float(re.search(r'data-composition-id="[^"]+"[^>]*data-duration="([\d.]+)"', html).group(1))
    tmp = os.path.join(gdir, f"_sfx_probe_{name}.html")
    open(tmp, "w", encoding="utf-8").write(html)
    port = free_port()
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=gdir, **k)
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(s, *a, **k): super().__init__(*a, directory=gdir, **k)
        def log_message(s, *a): pass
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Q)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        p = subprocess.run(["node", os.path.join(HERE, "_sfx_probe.mjs"),
                            f"http://127.0.0.1:{port}/{os.path.basename(tmp)}", comp_id, spec_path],
                           capture_output=True, text=True, timeout=180)
    finally:
        httpd.shutdown(); os.remove(tmp)
    if p.returncode != 0:
        sys.exit("probe failed:\n" + p.stderr)
    if p.stderr.strip():
        print("  " + p.stderr.strip())
    return comp_id, dur, json.loads(p.stdout.strip().splitlines()[-1])


def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def synth_air(length, shape="swell", band=(500, 5000), seed=1):
    """Band-limited noise whoosh. Deterministic (seeded), no pitch by construction."""
    n = max(1, int(length * SR))
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(n)
    # pink-ish: integrate a little so it is soft, not hissy
    pink = np.cumsum(white); pink -= np.convolve(pink, np.ones(4801) / 4801, mode="same")
    t = np.linspace(0, 1, n)
    lo, hi = band
    # sweep the band centre by filtering in short overlapping blocks
    out = np.zeros(n); blk = 2400; hop = 1200; win = np.hanning(blk)
    for s in range(0, n, hop):
        u = min(1.0, s / max(1, n - 1))
        prog = u if shape in ("swell", "rise") else (1 - u if shape == "fall" else 0.5)
        c = lo * (hi / lo) ** prog
        sos = butter(2, [max(60, c / 1.9), min(SR / 2 - 100, c * 1.9)], btype="band", fs=SR, output="sos")
        seg = pink[s:s + blk]
        y = sosfilt(sos, seg) * win[:len(seg)]
        out[s:s + len(seg)] += y
    if shape == "swell":   env = np.clip(t / 0.82, 0, 1) ** 2 * np.clip((1 - t) / 0.18, 0, 1) ** 0.6
    elif shape == "rise":  env = t ** 1.6 * np.clip((1 - t) / 0.08, 0, 1)
    elif shape == "fall":  env = np.clip(t / 0.06, 0, 1) * (1 - t) ** 1.8
    else:                  env = np.sin(np.pi * t) ** 2          # puff
    out *= env
    return np.stack([out, out], axis=1)


def pan_gain(p):
    p = float(np.clip(p, -1, 1)); a = (p + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


def build(gdir, name, write_tag=False):
    spec_path = os.path.join(gdir, "sfx", name + ".json")
    spec = json.load(open(spec_path))
    comp_id, dur, cues = resolve_cues(gdir, name, spec_path)
    n = int(round(dur * SR))
    mix = np.zeros((n, 2))
    hp = butter(4, 150, btype="highpass", fs=SR, output="sos")
    cache = {}
    for k, c in enumerate(cues):
        snd = c["sound"]
        if snd == "air":
            x = synth_air(float(c.get("len", 0.8)), c.get("shape", "swell"), tuple(c.get("band", (500, 5000))), seed=k + 11)
        else:
            src = os.path.join(gdir, spec["sounds"][snd])
            if src not in cache: cache[src] = load_audio(src)
            x = cache[src].copy()
        x = np.stack([sosfilt(hp, x[:, 0]), sosfilt(hp, x[:, 1])], axis=1)
        pk = np.abs(x).max()
        if pk > 0: x *= 10 ** (float(c.get("peak", -24)) / 20) / pk
        pan = c.get("pan")
        if isinstance(pan, (int, float)):
            p = (pan / 1920 * 2 - 1) * 0.35 if abs(pan) > 1.5 else pan
            gl, gr = pan_gain(p); x[:, 0] *= gl * 1.4142; x[:, 1] *= gr * 1.4142
        elif isinstance(pan, list):
            ps = np.linspace(pan[0], pan[1], len(x)); a = (np.clip(ps, -1, 1) + 1) * np.pi / 4
            x[:, 0] *= np.cos(a) * 1.4142; x[:, 1] *= np.sin(a) * 1.4142
        s = int(round(float(c["at"]) * SR)); e = min(n, s + len(x))
        if s < n: mix[s:e] += x[:e - s]
        print(f"  {snd:6s} at {float(c['at']):6.2f}s" + (f"  len {float(c['len']):.2f}s" if 'len' in c else "")
              + f"  peak {c.get('peak', -24)} dBFS")
    cap = 10 ** (-16 / 20); pk = np.abs(mix).max()
    if pk > cap: mix *= cap / pk
    out_rel = f"assets/sfx/{name}.wav"
    out = os.path.join(gdir, out_rel); os.makedirs(os.path.dirname(out), exist_ok=True)
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print(f"  wrote {out_rel}: {len(cues)} cues, {dur:.1f}s, peak {20*np.log10(np.abs(mix).max()+1e-12):.1f} dBFS")
    if write_tag:
        comp = os.path.join(gdir, "compositions", name + ".html")
        html = open(comp, encoding="utf-8").read()
        tag = (f'<audio id="sfx" src="{out_rel}" data-start="0" data-duration="{dur:g}" '
               f'data-track-index="20" data-volume="1"></audio>')
        if re.search(r'<audio id="sfx"[^>]*></audio>', html):
            html = re.sub(r'<audio id="sfx"[^>]*></audio>', tag, html)
        else:
            html = re.sub(r'(<div[^>]*data-composition-id="[^"]+"[^>]*>)',
                          r'\1\n  <!-- sound effects: built by sfx_track.py from sfx/' + name + '.json -->\n  ' + tag, html, count=1)
        open(comp, "w", encoding="utf-8").write(html)
        print("  audio tag written into the composition")
    return out


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    build(os.path.abspath(a[0]), a[1], "--write-audio-tag" in sys.argv)
