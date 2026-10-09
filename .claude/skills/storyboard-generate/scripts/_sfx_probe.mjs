#!/usr/bin/env node
/* _sfx_probe.mjs — resolve sfx cue times against a composition's REAL timeline.
 *
 * Loads the composition over http, then evaluates each cue's `at` expression inside the page,
 * where the composition's own top-level constants (WAVE_T, …) are in scope, plus helpers:
 *   startOf(sel, n=0, prop?)  start time (s) of the n-th tween, by start time, whose targets match
 *                      sel (and, given prop, that animates that property)
 *   endOf(sel, n=0)    its end time
 *   durOf(sel, n=0)    its duration
 *   countOf(sel)       how many tweens target sel
 *   xOf(sel, n=0)      the n-th matching element's centre x in frame px (0..width) — for panning
 * `len` and `pan` may be expressions too. Prints the resolved cue list as JSON.
 *
 * usage: node _sfx_probe.mjs <url> <compId> <cues.json>
 */
import fs from "node:fs"; import path from "node:path"; import os from "node:os";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
function findPuppeteer() {
  try { return require("puppeteer-core"); } catch {}
  const root = path.join(os.homedir(), ".npm", "_npx");
  for (const d of fs.readdirSync(root)) {
    const c = path.join(root, d, "node_modules", "puppeteer-core");
    if (fs.existsSync(c)) { try { return require(c); } catch {} }
  }
  throw new Error("no puppeteer-core found");
}
function findBrowser() {
  for (const c of [process.env.HYPERFRAMES_BROWSER_PATH,
                   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   "/Applications/Chromium.app/Contents/MacOS/Chromium",
                   "/usr/bin/google-chrome", "/usr/bin/chromium-browser"]) if (c && fs.existsSync(c)) return c;
  throw new Error("no Chrome found; set HYPERFRAMES_BROWSER_PATH");
}
const [url, compId, cuesPath] = process.argv.slice(2);
const spec = JSON.parse(fs.readFileSync(cuesPath, "utf8"));
const b = await findPuppeteer().launch({ executablePath: findBrowser(), headless: true, args: ["--no-sandbox"] });
try {
  const pg = await b.newPage();
  await pg.setViewport({ width: 1920, height: 1080 });
  const errs = []; pg.on("pageerror", e => errs.push(e.message));
  await pg.goto(url, { waitUntil: "load", timeout: 60000 });
  for (let i = 0; i < 100; i++) {                       // wait for the timeline to register
    if (await pg.evaluate(id => !!(window.__timelines && window.__timelines[id]), compId)) break;
    await new Promise(r => setTimeout(r, 100));
  }
  // a classic-script `const` is a global lexical binding: in scope for an indirect eval here
  const out = await pg.evaluate((id, cues) => {
    const tl = window.__timelines[id];
    tl.seek(0);
    // one entry per (tween, element): a staggered tween is ONE tween in GSAP, but each of its
    // targets starts `each` seconds after the previous — a cue per element must see that
    const tweens = [];
    for (const t of tl.getChildren(true, true, false)) {
      let s = t.startTime(), p = t.parent;
      while (p && p !== tl) { s += p.startTime(); p = p.parent; }
      const els = (t.targets() || []).filter(x => x && x.nodeType === 1);
      const st = t.vars && t.vars.stagger;
      const each = typeof st === "number" ? st : (st && st.each) || 0;
      if (els.length > 1 && each) els.forEach((e, k) => tweens.push({ t, start: s + k * each, dur: t.duration(), els: [e] }));
      else tweens.push({ t, start: s, dur: t.duration(), els });
    }
    tweens.sort((a, c) => a.start - c.start);
    // `prop` narrows to tweens that animate that property (e.g. 'scale' = the pop-ins, not the drifts)
    const match = (sel, prop) => tweens.filter(w => w.els.some(e => e.matches(sel))
      && (!prop || (w.t.vars && Object.prototype.hasOwnProperty.call(w.t.vars, prop))));
    const pick = (sel, n, prop) => { const m = match(sel, prop); if (n >= m.length) throw new Error(`no tween #${n} for ${sel}${prop ? " animating " + prop : ""} (have ${m.length})`); return m[n]; };
    const H = {
      startOf: (sel, n = 0, prop) => pick(sel, n, prop).start,
      endOf: (sel, n = 0, prop) => { const w = pick(sel, n, prop); return w.start + w.dur; },
      durOf: (sel, n = 0, prop) => pick(sel, n, prop).dur,
      countOf: (sel, prop) => match(sel, prop).length,
      xOf: (sel, n = 0) => { const el = document.querySelectorAll(sel)[n]; const r = el.getBoundingClientRect(); return r.left + r.width / 2; },
    };
    const geval = eval;                                  // indirect: global scope
    // only STRINGS are expressions — a JSON [from, to] pan pair would otherwise be stringified and
    // collapse through the comma operator to its last value
    const ev = expr => typeof expr !== "string" ? expr
      : geval(`(function(startOf,endOf,durOf,countOf,xOf){ return (${expr}); })`)(H.startOf, H.endOf, H.durOf, H.countOf, H.xOf);
    const res = [];
    for (const c of cues) {
      const reps = c.repeat != null ? ev(String(c.repeat)) : 1;
      for (let i = 0; i < reps; i++) {
        const sub = s => typeof s === "string" ? s.replace(/\bi\b/g, String(i)) : s;
        const r = Object.assign({}, c, { at: ev(sub(c.at)) });
        if (c.len != null) r.len = ev(sub(c.len));
        if (c.pan != null) r.pan = ev(sub(c.pan));
        delete r.repeat; res.push(r);
      }
    }
    return res;
  }, compId, spec.cues);
  if (errs.length) console.error("page errors:", errs.join(" | "));
  console.log(JSON.stringify(out));
} finally { await b.close(); }
