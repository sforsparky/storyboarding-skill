#!/usr/bin/env python3
"""Render every composition in <graphics_dir>/plan.json onto the board, then rebuild the xlsx once.

  render_plan.py <storyboard.json> [name-fragment ...] [--stale] [--rows A-B] [--dry-run]

Each entry goes through rebuild.py, which renders, registers the entry's rows (segments, poster
times, kind, layers) and cuts their posters in one pass — no post-steps. Then the board is
rebuilt once at the end.

  name-fragment  only entries whose name contains one of these
  --stale        only entries whose render is older than its composition or anything it can load
                 (shared/, assets/, the composition itself) — the "a style change landed, re-render
                 what it touched" pass
  --rows A-B     only entries that cover a row in this range

Exit 0 when every render passed its craft check, 3 when any was flagged, 1 when any failed.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.realpath(__file__))
REBUILD = os.path.join(HERE, "rebuild.py")
SB_TO_XLSX = os.path.normpath(os.path.join(HERE, "..", "..", "storyboard-build", "scripts", "sb_to_xlsx.py"))
sys.path.insert(0, HERE)
from rebuild import find_xlsx, archive_if_commented, DEFAULT_GRAPHICS_DIR  # noqa: E402


def newest_input(graphics_dir, name):
    """mtime of the newest file a composition can depend on: itself, shared/ and assets/."""
    paths = [os.path.join(graphics_dir, "compositions", name + ".html")]
    for sub in ("shared", "assets"):
        for root, _d, files in os.walk(os.path.join(graphics_dir, sub)):
            paths += [os.path.join(root, f) for f in files]
    return max((os.path.getmtime(p) for p in paths if os.path.exists(p)), default=0)


def main():
    ap = argparse.ArgumentParser(description="Render the plan.json compositions onto the board.")
    ap.add_argument("storyboard")
    ap.add_argument("only", nargs="*")
    ap.add_argument("--stale", action="store_true")
    ap.add_argument("--rows")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sb = os.path.abspath(args.storyboard)
    project = os.path.dirname(sb)
    doc = json.load(open(sb))
    gdir = os.path.join(project, doc.get("graphics_dir", DEFAULT_GRAPHICS_DIR))
    plan_path = os.path.join(gdir, "plan.json")
    if not os.path.exists(plan_path):
        sys.exit(f"error: no plan at {plan_path}")
    plan = json.load(open(plan_path))

    lo = hi = None
    if args.rows:
        lo, hi = (int(x) for x in args.rows.split("-")) if "-" in args.rows else (int(args.rows),) * 2
    todo = []
    for name, e in plan.items():
        if args.only and not any(o in name for o in args.only):
            continue
        if lo is not None and (e["rows"][1] < lo or e["rows"][0] > hi):
            continue
        if args.stale:
            out = os.path.join(project, "assets", name + ".mp4")
            if os.path.exists(out) and os.path.getmtime(out) >= newest_input(gdir, name):
                continue
        todo.append(name)

    print(f"{len(todo)} composition(s) to render" + (" (dry run)" if args.dry_run else ""))
    results = {}
    for name in todo:
        cmd = [sys.executable, REBUILD, sb, name, "--no-xlsx"] + (["--dry-run"] if args.dry_run else [])
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=project)
        out = p.stdout + p.stderr
        status = {0: "ok", 3: "CHECK"}.get(p.returncode, "FAIL")
        results[name] = status
        print(f"{status:5} {name}", flush=True)
        if status != "ok" or args.dry_run:
            keep = [l for l in out.splitlines()
                    if args.dry_run or l.strip().startswith(("[", "!", "error")) or "FAILED" in l]
            print("\n".join("      " + l for l in keep[:30]), flush=True)

    if todo and not args.dry_run:
        xlsx = find_xlsx(project, doc)
        kept = archive_if_commented(project, xlsx)
        if kept:
            print(f"! {xlsx} carries reviewer comments — archived to {kept} before overwrite")
        p = subprocess.run(["python3", SB_TO_XLSX, "storyboard.json", xlsx], cwd=project,
                           capture_output=True, text=True)
        print(f"board rebuilt ({xlsx})" if p.returncode == 0 else f"! xlsx rebuild failed:\n{p.stderr}")

    bad = [n for n, s in results.items() if s != "ok"]
    print("flagged/failed:", ", ".join(bad) if bad else "none")
    sys.exit(1 if "FAIL" in results.values() else 3 if bad else 0)


if __name__ == "__main__":
    main()
