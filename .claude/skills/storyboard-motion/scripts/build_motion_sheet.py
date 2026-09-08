#!/usr/bin/env python3
"""Assemble a self-contained HTML "motion design sheet" from shots.json.

Each shot's still is embedded as a data URI so the sheet is one portable file (good for an Artifact
or a hand-off). One card per shot shows the still, style / text / camera treatment, duration, and
the exact Higgsfield prompt that will run — so the user approves precisely what will be generated.
This builder does NOT generate video; approval happens after this.

Usage: build_motion_sheet.py shots.json out.html
"""
import sys, os, json, base64, mimetypes, html

def data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()

def esc(s): return html.escape(str(s or ""))

def main():
    shots_path, out_path = sys.argv[1], sys.argv[2]
    doc = json.load(open(shots_path))
    base = os.path.dirname(os.path.abspath(shots_path))
    title = doc.get("title", "Motion design sheet")
    brand = doc.get("brand", "")

    cards = []
    for i, s in enumerate(doc.get("shots", []), 1):
        still = s.get("still", "")
        src = ""
        p = os.path.join(base, still) if still else ""
        if p and os.path.exists(p):
            src = data_uri(p)
        chips = "".join(
            f'<span class="chip"><b>{esc(k)}</b>{esc(v)}</span>'
            for k, v in [("Style ", s.get("style")), ("Text ", s.get("text_design")),
                         ("Angle ", s.get("camera_angle")), ("Move ", s.get("camera_move")),
                         ("Time ", f"{s.get('duration','?')}s")] if v)
        img = (f'<img src="{src}" alt="{esc(s.get("slug",""))}">' if src
               else f'<div class="missing">still not found: {esc(still)}</div>')
        cards.append(f'''
        <article class="card">
          <div class="frame">{img}<span class="num">{i}</span></div>
          <div class="body">
            <h2>{esc(s.get("slug") or s.get("id") or f"Shot {i}")}</h2>
            <div class="chips">{chips}</div>
            <div class="prompt"><span>Higgsfield prompt</span><p>{esc(s.get("prompt"))}</p></div>
          </div>
        </article>''')

    doc_html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
  :root{{--bg:#0e1512;--card:#15201b;--ink:#eaf3ee;--mut:#9db3a8;--acc:#8BE01E;--line:#28382f}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
    font:15px/1.5 Inter,system-ui,-apple-system,sans-serif}}
  header{{padding:28px 32px;border-bottom:1px solid var(--line)}}
  header h1{{margin:0;font-size:22px;letter-spacing:-.3px}}
  header p{{margin:6px 0 0;color:var(--mut)}}
  .badge{{display:inline-block;margin-top:10px;padding:4px 10px;border:1px solid var(--acc);
    color:var(--acc);border-radius:999px;font-size:12px;font-weight:600}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px;padding:24px 32px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
  .frame{{position:relative;aspect-ratio:16/9;background:#0a0f0d}}
  .frame img{{width:100%;height:100%;object-fit:cover;display:block}}
  .frame .missing{{display:flex;align-items:center;justify-content:center;height:100%;color:#e5484d;font-size:13px;padding:12px;text-align:center}}
  .num{{position:absolute;top:10px;left:10px;background:rgba(0,0,0,.6);color:#fff;
    width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:700}}
  .body{{padding:16px}} .body h2{{margin:0 0 10px;font-size:16px}}
  .chips{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}}
  .chip{{background:#0f1a15;border:1px solid var(--line);border-radius:8px;padding:4px 8px;font-size:12px;color:var(--ink)}}
  .chip b{{color:var(--acc);font-weight:600}}
  .prompt{{border-top:1px solid var(--line);padding-top:10px}}
  .prompt span{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--mut);margin-bottom:4px}}
  .prompt p{{margin:0;font-size:13px;color:#cfe0d7}}
  footer{{padding:18px 32px;color:var(--mut);border-top:1px solid var(--line);font-size:13px}}
</style></head><body>
<header>
  <h1>{esc(title)}</h1>
  <p>Proposed motion treatment for approval — no video is generated until you approve.</p>
  {f'<span class="badge">brand: {esc(brand)}</span>' if brand else ''}
</header>
<div class="grid">{''.join(cards)}</div>
<footer>Each card is one image-to-video shot (Higgsfield Cinema Studio, silent). Reply with edits or approve to generate.</footer>
</body></html>'''
    open(out_path, "w").write(doc_html)
    print(f"wrote {out_path}: {len(doc.get('shots', []))} shot(s)")

if __name__ == "__main__":
    main()
