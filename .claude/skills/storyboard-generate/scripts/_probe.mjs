#!/usr/bin/env node
/* _probe.mjs — headless-browser driver for check_row.py.
 *
 * Loads a HyperFrames composition over a local http URL, seeks its registered GSAP timeline
 * to a list of times, and for each time captures a full-frame PNG plus an element report
 * (bbox, opacity, text/img content) used by check_row.py's craft checks.
 *
 * Usage: node _probe.mjs <url> <compId> <outDir> <t1,t2,...> <ignoreSelectorsCSV>
 * Prints one JSON object to stdout: { width, height, frames: [{t, png, elements: [...]}] }
 *
 * Browser: puppeteer-core driving a real Chrome/Chromium binary. We don't bundle a browser —
 * we reuse whichever one is already on disk (system Google Chrome, or the chrome-headless-shell
 * HyperFrames itself downloaded to ~/.cache/hyperframes/chrome), found via findBrowser() below.
 */
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function findPuppeteer() {
  // Prefer a puppeteer-core already resolvable from cwd (a project may have one), else
  // fall back to the copy hyperframes' own npx cache pulled down (same major, no install).
  const tryPaths = [
    "puppeteer-core",
  ];
  for (const p of tryPaths) {
    try { return require(p); } catch {}
  }
  const npxRoot = path.join(os.homedir(), ".npm", "_npx");
  if (fs.existsSync(npxRoot)) {
    for (const d of fs.readdirSync(npxRoot)) {
      const cand = path.join(npxRoot, d, "node_modules", "puppeteer-core");
      if (fs.existsSync(cand)) {
        try { return require(cand); } catch {}
      }
    }
  }
  throw new Error("no puppeteer-core found (checked cwd resolution and ~/.npm/_npx/*/node_modules)");
}

function findBrowser() {
  if (process.env.HYPERFRAMES_BROWSER_PATH && fs.existsSync(process.env.HYPERFRAMES_BROWSER_PATH)) {
    return process.env.HYPERFRAMES_BROWSER_PATH;
  }
  const candidates = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    path.join(os.homedir(), ".cache/hyperframes/chrome/chrome-headless-shell"),
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
    // chrome-headless-shell may be nested under a version dir
    if (fs.existsSync(path.dirname(c))) {
      const base = path.dirname(c);
      const hit = fs.readdirSync(base).find(f => f.includes("chrome-headless-shell"));
      if (hit) {
        const full = path.join(base, hit);
        const stat = fs.statSync(full);
        if (stat.isDirectory()) {
          // typical layout: chrome-headless-shell/<platform>/chrome-headless-shell
          for (const sub of fs.readdirSync(full)) {
            const inner = path.join(full, sub, "chrome-headless-shell");
            if (fs.existsSync(inner)) return inner;
          }
        } else {
          return full;
        }
      }
    }
  }
  throw new Error("no Chrome/Chromium binary found; set HYPERFRAMES_BROWSER_PATH");
}

const IGNORE_ID_SELECTORS = ["#root", "#bg", "#vign", "#meshfx"];
const IGNORE_CLASS_SELECTORS = [".stage", ".world"];
const IGNORE_TAG_SELECTORS = ["canvas", "html", "body", "script", "style", "head", "link", "meta"];
const DEFAULT_EXTRA_IGNORE = [".ledge", "#spot"];

async function collectFrameReport(page, extraIgnoreCSV) {
  const extraIgnore = (extraIgnoreCSV || "").split(",").map(s => s.trim()).filter(Boolean);
  return await page.evaluate((structuralSel, defaultIgnoreSel, extraIgnoreSel) => {
    function effectiveOpacity(el) {
      let node = el, op = 1;
      while (node && node.nodeType === 1) {
        const cs = getComputedStyle(node);
        if (cs.visibility === "hidden") return 0;
        const o = parseFloat(cs.opacity);
        if (!Number.isNaN(o)) op *= o;
        node = node.parentElement;
      }
      return op;
    }
    function domPath(el) {
      const p = [];
      let node = el;
      while (node && node.parentElement) {
        const parent = node.parentElement;
        p.unshift(Array.prototype.indexOf.call(parent.children, node));
        node = parent;
      }
      return p;
    }
    function hasDirectText(el) {
      for (const n of el.childNodes) {
        if (n.nodeType === 3 && n.textContent.trim().length > 0) return true;
      }
      return false;
    }
    // Tight bbox of the element's own direct-text glyphs (via Range), not its full box.
    // A block-level label/kicker is often much wider than the text it holds (block layout,
    // no explicit width) — comparing full element boxes then reports "overlaps" against a
    // corner badge/icon that floats well clear of where the glyphs actually end. Off-frame
    // and overlap checks care about what a viewer actually SEES, so they use this when present.
    function textBBox(el) {
      let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity, found = false;
      for (const n of el.childNodes) {
        if (n.nodeType !== 3 || n.textContent.trim().length === 0) continue;
        const range = document.createRange();
        range.selectNodeContents(n);
        for (const rc of range.getClientRects()) {
          if (rc.width <= 0 || rc.height <= 0) continue;
          found = true;
          l = Math.min(l, rc.left); t = Math.min(t, rc.top);
          r = Math.max(r, rc.right); b = Math.max(b, rc.bottom);
        }
      }
      return found ? { l, t, r, b } : null;
    }
    const ignoreSel = [...defaultIgnoreSel, ...extraIgnoreSel];
    const all = Array.from(document.querySelectorAll("*"));
    const out = [];
    for (const el of all) {
      const tag = el.tagName.toLowerCase();
      // structural containers: skip recording the element itself, still walk its children
      if (structuralSel.some(sel => el.matches(sel))) continue;
      // svg internals: only the outer <svg> is recorded, not path/circle/g/etc inside one
      if (tag !== "svg" && el.closest("svg")) continue;
      // explicit ignore list (default .ledge/#spot + user --ignore) is an OFF_FRAME/OVERLAP
      // concern only (deliberately oversized bleed elements) — mark it, don't drop the
      // element, because HARD_EDGE still needs its bbox to recognise its own edges as a real
      // border (e.g. the bright shelf-ledge line is SUPPOSED to be a crisp line, not a defect).
      // NOTE: must coerce to a real boolean. el.closest(...) returns an Element (or null), and
      // GSAP stashes a circular-referencing cache (`_gsap`) directly on animated elements — a
      // leaked Element reference here makes the whole return value unserializable (Puppeteer
      // fails silently, resolving the call to `undefined` instead of rejecting).
      // selfIgnored: the element itself (not just an ancestor) matches the ignore list — e.g.
      // the `.ledge` bar div itself. That's a deliberately crisp line, still fine as a HARD_EDGE
      // border reference. `ignored` alone also covers its descendants (e.g. the shadow `i`
      // inside it) — those are NOT safe self-references (their own edge is exactly what a
      // gradient/overlay defect would show up as), so check_row.py keeps the two apart.
      const selfIgnored = ignoreSel.length > 0 && el.matches(ignoreSel.join(","));
      const ignored = selfIgnored || (ignoreSel.length > 0 && !!el.closest(ignoreSel.join(",")));

      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      const opacity = effectiveOpacity(el);
      if (opacity <= 0.05) continue;

      const cs = getComputedStyle(el);
      let lineHeight = parseFloat(cs.lineHeight);
      const fontSize = parseFloat(cs.fontSize);
      if (Number.isNaN(lineHeight)) lineHeight = fontSize * 1.2;
      const hasText = hasDirectText(el);

      out.push({
        tag,
        id: el.id || null,
        classes: Array.from(el.classList || []),
        bbox: { l: rect.left, t: rect.top, r: rect.right, b: rect.bottom },
        textBbox: hasText ? textBBox(el) : null,
        hasText,
        fontSize,
        lineHeight,
        src: tag === "img" ? (el.currentSrc || el.src || null) : null,
        // paint facts for the SOFT_EDGE check: a gradient-painted box with no border/radius
        // has hard edges wherever its box ends inside the frame
        bgImage: cs.backgroundImage || "none",
        borderWidth: parseFloat(cs.borderTopWidth) || 0,
        borderRadius: parseFloat(cs.borderTopLeftRadius) || 0,
        boxShadow: cs.boxShadow || "none",
        path: domPath(el),
        ignored,
        selfIgnored,
      });
    }
    return out;
  }, [...IGNORE_ID_SELECTORS, ...IGNORE_CLASS_SELECTORS, ...IGNORE_TAG_SELECTORS], DEFAULT_EXTRA_IGNORE, extraIgnore);
}

async function main() {
  const [, , url, compId, outDir, timesCSV, ignoreCSV] = process.argv;
  if (!url || !compId || !outDir || !timesCSV) {
    console.error("usage: node _probe.mjs <url> <compId> <outDir> <t1,t2,...> [ignoreSelectorsCSV]");
    process.exit(2);
  }
  const times = timesCSV.split(",").map(Number);
  fs.mkdirSync(outDir, { recursive: true });

  const puppeteer = findPuppeteer();
  const executablePath = findBrowser();
  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ["--force-color-profile=srgb", "--font-render-hinting=none", "--hide-scrollbars"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
    await page.goto(url, { waitUntil: "load", timeout: 60000 });

    // wait for the registered timeline to exist. NOTE: the predicate must return a plain
    // boolean, not the (GSAP timeline) object itself — puppeteer's waitForFunction tries to
    // serialize the truthy return value on every poll, and a GSAP timeline's internal structure
    // makes that serialization fail silently on every attempt, so it just spins to the timeout.
    await page.waitForFunction(
      (id) => !!(window.__timelines && window.__timelines[id]),
      { timeout: 20000 },
      compId
    );
    // wait for fonts + images
    await page.evaluate(async () => {
      try { await document.fonts.ready; } catch {}
    });
    await page.waitForFunction(() => {
      return Array.from(document.images).every(img => img.complete);
    }, { timeout: 20000 });

    const frames = [];
    for (const t of times) {
      await page.evaluate((id, tt) => {
        window.__timelines[id].seek(tt, false);
      }, compId, t);
      // let layout/paint settle: two rAFs + a short real wait
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      await new Promise(r => setTimeout(r, 150));

      const fname = `f_${t}.png`;
      const fpath = path.join(outDir, fname);
      await page.screenshot({ path: fpath });
      const elements = await collectFrameReport(page, ignoreCSV);
      frames.push({ t, png: fpath, elements });
    }

    console.log(JSON.stringify({ width: 1920, height: 1080, frames }));
  } finally {
    await browser.close();
  }
}

main().catch(e => {
  console.error("PROBE_ERROR", e && e.stack || e);
  process.exit(1);
});
