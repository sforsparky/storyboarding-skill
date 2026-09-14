#!/usr/bin/env node
/* _still.mjs — headless-Chrome single-frame still exporter for export_still.py.
 *
 * A small sibling to _probe.mjs (same puppeteer-core-driving-system-Chrome approach,
 * same "serve GRAPHICS root, load the composition, wait for its registered GSAP timeline,
 * seek deterministically" recipe) but built for one thing: capture ONE full-resolution PNG
 * of ONE composition at ONE time, optionally with injected CSS/JS and a transparent
 * background. export_still.py does all crop/resize/alpha-reporting afterward in PIL.
 *
 * Usage: node _still.mjs <argsJsonPath>
 * argsJsonPath is a JSON file: {
 *   url, compId, t, scale, transparent, setType ("css"|"js"|null), setCode, outPng
 * }
 * Prints one JSON object to stdout: { png, width, height }
 */
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function findPuppeteer() {
  const tryPaths = ["puppeteer-core"];
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
    if (fs.existsSync(path.dirname(c))) {
      const base = path.dirname(c);
      const hit = fs.readdirSync(base).find(f => f.includes("chrome-headless-shell"));
      if (hit) {
        const full = path.join(base, hit);
        const stat = fs.statSync(full);
        if (stat.isDirectory()) {
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

async function main() {
  const [, , argsPath] = process.argv;
  if (!argsPath) {
    console.error("usage: node _still.mjs <argsJsonPath>");
    process.exit(2);
  }
  const args = JSON.parse(fs.readFileSync(argsPath, "utf8"));
  const { url, compId, t, scale, transparent, setType, setCode, outPng } = args;

  const puppeteer = findPuppeteer();
  const executablePath = findBrowser();
  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ["--force-color-profile=srgb", "--font-render-hinting=none", "--hide-scrollbars"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: scale || 1 });
    await page.goto(url, { waitUntil: "load", timeout: 60000 });

    // Apply --set / --transparent BEFORE the timeline is seeked, same ordering the brief
    // specifies ("inject CSS before seeking"). CSS goes in as a <style> tag; JS is evaluated
    // directly (both can toggle element visibility, recolor things, etc. for a variant still).
    if (transparent) {
      await page.evaluate(() => {
        const style = document.createElement("style");
        style.textContent = `
          #bg, #vign, #meshfx { display: none !important; }
          html, body { background: transparent !important; }
        `;
        document.head.appendChild(style);
      });
    }
    if (setType === "css" && setCode) {
      await page.evaluate((css) => {
        const style = document.createElement("style");
        style.textContent = css;
        document.head.appendChild(style);
      }, setCode);
    } else if (setType === "js" && setCode) {
      await page.evaluate((js) => {
        // eslint-disable-next-line no-eval
        (0, eval)(js);
      }, setCode);
    }

    // wait for the registered timeline to exist (booleans only across the CDP boundary —
    // see _probe.mjs's note: returning the GSAP timeline object itself breaks serialization).
    await page.waitForFunction(
      (id) => !!(window.__timelines && window.__timelines[id]),
      { timeout: 20000 },
      compId
    );
    await page.evaluate(async () => {
      try { await document.fonts.ready; } catch {}
    });
    await page.waitForFunction(() => {
      return Array.from(document.images).every(img => img.complete);
    }, { timeout: 20000 });

    await page.evaluate((id, tt) => {
      window.__timelines[id].seek(tt, false);
    }, compId, t);
    // let layout/paint settle: two rAFs + a short real wait (matches _probe.mjs)
    await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
    await new Promise(r => setTimeout(r, 150));

    fs.mkdirSync(path.dirname(outPng), { recursive: true });
    await page.screenshot({ path: outPng, omitBackground: !!transparent });

    const vp = page.viewport();
    const width = Math.round(vp.width * (vp.deviceScaleFactor || 1));
    const height = Math.round(vp.height * (vp.deviceScaleFactor || 1));
    console.log(JSON.stringify({ png: outPng, width, height }));
  } finally {
    await browser.close();
  }
}

main().catch(e => {
  console.error("STILL_PROBE_ERROR", e && e.stack || e);
  process.exit(1);
});
