#!/usr/bin/env python3
"""Helpers for /generate: download a result, strip its audio (video is always delivered
silent — the editor sets sound), extract a poster, and register produced assets into
storyboard.json. Supports single rows, a continuous asset spanning a row range (register_span),
and a style-linked series (series_id tag). Rendering itself is driven by the skill (HyperFrames
CLI locally, Higgsfield MCP for video); this file is the plumbing so naming and row bookkeeping
stay consistent.
"""
import json, os, sys, urllib.request, subprocess, uuid, datetime as dt

def load(p): return json.load(open(p))
def save(p, d): json.dump(d, open(p, "w"), indent=2)
def row_by_n(doc, n): return next((r for r in doc["rows"] if r["n"] == int(n)), None)
def name_for(row, ext): return f"{row['n']:03d}_{row.get('slug','shot')}.{ext}"

def now_iso(): return dt.datetime.now().isoformat(timespec="seconds")

def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    return dest

def silence(path):
    """Strip the audio track in place — video is delivered without sound."""
    tmp = path + ".silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", path, "-c:v", "copy", "-an", tmp],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(tmp, path)
    return path

def poster_from(video_path, at="0.5"):
    png = os.path.splitext(video_path)[0] + ".png"
    subprocess.run(["ffmpeg", "-y", "-ss", at, "-i", video_path, "-frames:v", "1", png],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png


def _fmt_row_range(ns):
    """Render a list of row numbers as '30-35' when contiguous, else '5,7,45'."""
    ns = sorted(int(n) for n in ns)
    if len(ns) == 1:
        return str(ns[0])
    if ns == list(range(ns[0], ns[-1] + 1)):
        return f"{ns[0]}-{ns[-1]}"
    return ",".join(map(str, ns))


def parse_selector(selector, doc):
    """Parse a row selector: a single 'n', a comma list 'a,b,c', or a range 'a-b'.
    Returns a sorted list of row numbers. Raises ValueError with a clear message
    (no traceback) for a malformed selector or a row number not present in the board."""
    sel = str(selector).strip()
    if not sel:
        raise ValueError("empty row selector")
    ns = set()
    if "-" in sel.lstrip("-") and "," not in sel:
        parts = sel.split("-")
        if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            a, b = int(parts[0]), int(parts[1])
            if a > b:
                a, b = b, a
            ns.update(range(a, b + 1))
        else:
            raise ValueError(f"bad range '{sel}' — expected A-B (e.g. 30-35)")
    else:
        for p in sel.split(","):
            p = p.strip()
            if not p.isdigit():
                raise ValueError(f"bad row number '{p}' in selector '{sel}'")
            ns.add(int(p))
    existing = {r["n"] for r in doc["rows"]}
    missing = sorted(n for n in ns if n not in existing)
    if missing:
        raise ValueError(f"row(s) not found: {', '.join(map(str, missing))}")
    return sorted(ns)


def add_feedback(sb_path, selector, text, who="user"):
    """Append one feedback entry to every row targeted by `selector` (a row number, a
    comma list, or an A-B range). All targeted rows get the SAME entry object shape —
    {who, when, text, id, rows:[all targeted n]} — so a group note shows on each row's
    board cell but can be recognised as one note via `id`/`rows`. A single-row selector
    still works and now also stamps `when` (today, ISO date) and `id` (rows:[n])."""
    doc = load(sb_path)
    ns = parse_selector(selector, doc)
    entry_id = uuid.uuid4().hex[:8]
    when = dt.date.today().isoformat()
    for n in ns:
        row = row_by_n(doc, n)
        entry = {"who": who, "when": when, "text": text, "id": entry_id, "rows": list(ns)}
        row.setdefault("feedback", []).append(entry)
    save(sb_path, doc)
    print(f"rows {_fmt_row_range(ns)}: +feedback id={entry_id} ({len(ns)} row(s)): {text}")
    return entry_id


def feedback_cmd(sb_path, selector=None):
    """Print a row's (or, with no selector, every row's) feedback entries, newest first,
    with when/id/rows — for reviewing what's pending before a regenerate."""
    doc = load(sb_path)
    ns = parse_selector(selector, doc) if selector else [r["n"] for r in doc["rows"]]
    items = []
    for n in ns:
        for e in row_by_n(doc, n).get("feedback") or []:
            items.append((n, e))
    dated = sorted((it for it in items if it[1].get("when")),
                   key=lambda it: it[1]["when"], reverse=True)
    undated = [it for it in items if not it[1].get("when")]
    if not dated and not undated:
        print("no feedback" + (f" for row(s) {_fmt_row_range(ns)}" if selector else ""))
        return
    for n, e in dated + undated:
        wl = e.get("when") or "undated"
        idpart = f" id={e['id']}" if e.get("id") else ""
        rowspart = f" rows={_fmt_row_range(e['rows'])}" if e.get("rows") else ""
        print(f"[{wl}] row {n}{idpart}{rowspart}: {e.get('text', '')}")


def resolve_feedback(sb_path, selector="all", entry_id=None):
    """Mark feedback resolved: every entry on the selected rows ('all' for the whole board), or
    only the entry with `entry_id`. Stamps `resolved_at`; nothing is deleted, so the note stays
    readable on the board (shown ✔) and in `feedback`.

    This is the ONLY way a note closes for good. Resolving a comment in Google Sheets does not
    reach storyboard.json, and a regenerate newer than a note is only a guess — an undated note,
    or a record-keeping note written just after the render it describes, never clears that way."""
    doc = load(sb_path)
    ns = [r["n"] for r in doc["rows"]] if str(selector).lower() == "all" else parse_selector(selector, doc)
    stamp, count = now_iso(), 0
    for n in ns:
        for e in row_by_n(doc, n).get("feedback") or []:
            if e.get("resolved_at") or (entry_id and e.get("id") != entry_id):
                continue
            e["resolved_at"] = stamp
            count += 1
    save(sb_path, doc)
    print(f"resolved {count} feedback entr{'y' if count == 1 else 'ies'}"
          + (f" (id={entry_id})" if entry_id else "") + f" on row(s) {_fmt_row_range(ns) if ns else '-'}")
    return count


def _keep_layers(row, file_rel, asset):
    """A re-register of the SAME file keeps the layer deliverables rebuild.py recorded
    (graphic on alpha + bg); otherwise the board loses its pointer to the editor's files."""
    for old in row.get("assets") or []:
        if old.get("file") == file_rel and old.get("layers"):
            asset["layers"] = old["layers"]
    return asset

def register(sb_path, n, file_rel, poster_rel, kind, source, duration=None,
             status="Generated", series_id=None):
    doc = load(sb_path); row = row_by_n(doc, n)
    asset = {"file": file_rel, "poster": poster_rel, "kind": kind,
             "source": source, "duration": duration, "registered_at": now_iso()}
    if series_id: asset["series_id"] = series_id
    row["assets"] = [_keep_layers(row, file_rel, asset)]; row["status"] = status
    save(sb_path, doc)
    print(f"row {n}: {file_rel} ({status})" + (f" series={series_id}" if series_id else ""))

# Where inside a beat to grab its poster, as a fraction of the segment.
# A beat builds, holds, then its panel/overlay exits right at the boundary — so the widest-open
# window is late but NOT at the end. 0.78 lands after the last element has settled and before
# the exit. This is a heuristic: when the composition's own tween times are known (the agent
# authored it), pass explicit poster_times instead — the tween times are the truth.
BEAT_POSTER_AT = 0.78


def _cut_beat_posters(sb_path, rows, bounds, file_rel, poster_at, poster_times):
    """One poster per row, cut from the shared clip INSIDE that row's own segment.

    A shared clip spans several rows, so without this every row shows the same frame and a
    stakeholder reviewing copy beat-by-beat sees one screenshot repeated. Returns
    {row_n: (poster_rel, t)}; an empty dict means callers keep the shared poster.
    """
    root = os.path.dirname(os.path.abspath(sb_path))
    video = os.path.join(root, file_rel)
    out = {}
    if not os.path.exists(video):
        print(f"  ! {file_rel} not found — every row keeps the shared poster")
        return out
    for i, r in enumerate(rows):
        lo, hi = bounds[i], bounds[i + 1]
        if poster_times and i < len(poster_times) and poster_times[i] is not None:
            t = float(poster_times[i])
            if not (lo <= t <= hi):
                print(f"  ! row {r['n']}: poster time {t:.2f}s is outside its segment "
                      f"{lo:.2f}-{hi:.2f}s — cutting there anyway, check the beat boundaries")
        else:
            t = lo + (hi - lo) * poster_at
        rel = os.path.join(os.path.dirname(file_rel), name_for(r, "png"))
        try:
            subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", video,
                            "-frames:v", "1", os.path.join(root, rel)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out[r["n"]] = (rel, round(t, 3))
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  ! row {r['n']}: could not cut a beat poster ({type(e).__name__}) "
                  f"— it keeps the shared poster")
    return out


def register_clip(sb_path, a, b, file_rel, poster_rel, kind, source, total_dur, cuts=None,
                  beat_posters=True, poster_at=BEAT_POSTER_AT, poster_times=None):
    """Point every row in [a,b] at ONE shared file, each with its own in/out segment.

    cuts:         optional explicit boundary times in seconds (len = rows+1); else split evenly.
    beat_posters: cut a separate poster per row from inside its segment (default). Each row's
                  asset records `poster_t` so the frame is reproducible and reviewable.
    poster_times: explicit absolute seconds, one per row, overriding poster_at for that row.
    """
    a, b, total = int(a), int(b), float(total_dur)
    doc = load(sb_path)
    rows = [r for r in doc["rows"] if a <= r["n"] <= b]
    if not rows:
        print(f"no rows in {a}-{b}"); return
    k = len(rows)
    if cuts and len(cuts) == k + 1:
        bounds = [float(c) for c in cuts]
    else:
        step = total / k
        bounds = [round(i * step, 3) for i in range(k)] + [round(total, 3)]
    if poster_times and len(poster_times) != k:
        print(f"  ! {len(poster_times)} poster time(s) for {k} rows — extras ignored, "
              f"missing ones fall back to {poster_at:.0%} through the segment")
    beats = _cut_beat_posters(sb_path, rows, bounds, file_rel, poster_at,
                              poster_times) if beat_posters else {}
    clip_group = f"clip_{a:03d}_{b:03d}"
    registered_at = now_iso()
    for i, r in enumerate(rows):
        rel, t = beats.get(r["n"], (poster_rel, None))
        asset = {"file": file_rel, "poster": rel, "kind": kind, "source": source,
                 "duration": round(bounds[i+1] - bounds[i], 3),
                 "segment": [bounds[i], bounds[i+1]], "clip_group": clip_group,
                 "registered_at": registered_at}
        if t is not None:
            asset["poster_t"] = t          # recorded so the frame can be re-cut identically
        r["assets"] = [_keep_layers(r, file_rel, asset)]
        r["status"] = "Generated"
    save(sb_path, doc)
    print(f"clip {clip_group}: {file_rel} across rows {a}-{b}")
    for i, r in enumerate(rows):
        rel, t = beats.get(r["n"], (poster_rel, None))
        at = f"  poster @ {t:.2f}s -> {os.path.basename(rel)}" if t is not None else \
             f"  poster (shared) {os.path.basename(rel)}"
        print(f"  row {r['n']}: {bounds[i]:.2f}-{bounds[i+1]:.2f}s{at}")


EST_CREDITS_PER_CLIP = 5  # rough; exact cost is always preflighted with get_cost before spending

def _routing():
    import sys, os
    build = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                         "..", "..", "storyboard-build", "scripts")
    sys.path.insert(0, os.path.abspath(build))
    from lib_types import GENERATED_BY_TYPE, normalize_type
    return GENERATED_BY_TYPE, normalize_type

def _route_of(row, GBT, norm):
    try:
        rt = GBT.get(norm(row["visual_type"]), "hyperframes")
    except Exception:
        rt = "hyperframes"
    if rt == "video" and row.get("motion_engine") == "hyperframes":
        rt = "hyperframes"   # per-row override renders a would-be video as a local graphic
    return rt


def _asset_age(root, asset):
    """A comparable datetime for one asset: registered_at if stamped, else the mtime of the
    asset file on disk. None when there is no way to date it (no stamp and the file is missing
    or unnamed) — callers treat that as "no asset" (i.e. older than anything)."""
    ra = asset.get("registered_at")
    if ra:
        try:
            return dt.datetime.fromisoformat(ra)
        except ValueError:
            pass
    f = asset.get("file")
    if f:
        path = os.path.join(root, f)
        if os.path.exists(path):
            return dt.datetime.fromtimestamp(os.path.getmtime(path))
    return None

def _row_asset_age(root, row):
    ages = [a for a in (_asset_age(root, asset) for asset in (row.get("assets") or []))
            if a is not None]
    return max(ages) if ages else None

def _row_open_feedback(root, row):
    """Split a row's feedback into (open_entries, undated_count). An entry is "open" when its
    `when` postdates the row's newest asset — or the row has no dateable asset at all, in which
    case any DATED entry counts as open (there is nothing yet to have addressed it). Entries with
    when: null are never counted as open; they're only reported as an undated count."""
    age = _row_asset_age(root, row)
    asset_date = age.date() if age else None
    opens, undated = [], 0
    for e in row.get("feedback") or []:
        if e.get("resolved_at"):              # explicitly closed — never open, never undated
            continue
        when = e.get("when")
        if not when:
            undated += 1
            continue
        try:
            fd = dt.date.fromisoformat(when)
        except ValueError:
            undated += 1
            continue
        if asset_date is None or fd > asset_date:
            opens.append(e)
    return opens, undated


def _print_open_feedback(doc, root):
    row_open, row_undated = {}, {}
    for r in doc["rows"]:
        opens, undated = _row_open_feedback(root, r)
        if opens:
            row_open[r["n"]] = opens
        if undated:
            row_undated[r["n"]] = undated
    print("")
    print("Open feedback:")
    if not row_open and not row_undated:
        print("  none")
        return
    printed_rows = set()
    for n in sorted(row_open):
        if n in printed_rows:
            continue
        opens = row_open[n]
        grouped = False
        for e in opens:
            eid = e.get("id")
            if not eid:
                continue
            group_ns = sorted(m for m in row_open if any(e2.get("id") == eid
                                                           for e2 in row_open[m]))
            if len(group_ns) > 1:
                status = row_by_n(doc, group_ns[0]).get("status", "")
                undct = sum(row_undated.get(m, 0) for m in group_ns)
                undnote = f"  (undated: {undct})" if undct else ""
                print("    rows %-9s %-9s open: 1 newest %s  — %s%s" %
                      (_fmt_row_range(group_ns), status, e["when"], e["text"][:70], undnote))
                printed_rows.update(group_ns)
                grouped = True
                break
        if grouped:
            continue
        newest = max(opens, key=lambda e: e["when"])
        undct = row_undated.get(n, 0)
        undnote = f"  (undated: {undct})" if undct else ""
        status = row_by_n(doc, n).get("status", "")
        print("    row %3d  %-9s open: %d newest %s  — %s%s" %
              (n, status, len(opens), newest["when"], newest["text"][:70], undnote))
        printed_rows.add(n)
    only_undated = sorted(n for n in row_undated if n not in row_open and n not in printed_rows)
    if only_undated:
        print(f"  undated-only (not open): rows {_fmt_row_range(only_undated)}")


def plan(sb_path):
    """Bucket the whole board for a no-arg /storyboard-generate: free/local rows to make now,
    paid Higgsfield rows to confirm. Prints a readable plan; spends nothing."""
    GBT, norm = _routing()
    doc = load(sb_path)
    local, paid, done = [], [], 0
    for r in doc["rows"]:
        if r.get("status") in ("Generated", "Approved"):
            done += 1
            continue
        rt = _route_of(r, GBT, norm)
        (paid if rt == "video" else local).append((r["n"], rt, r.get("slug", "")))
    print("Board plan for " + sb_path + ":")
    print("  generate now (free / local): " + str(len(local)) +
          " row(s) - hyperframes graphics, still reuses, placeholders")
    for n, rt, slug in local:
        print("    row %3d  %-11s %s" % (n, rt, slug))
    est = len(paid) * EST_CREDITS_PER_CLIP
    print("")
    print("  needs confirmation (Higgsfield B-roll, PAID): " + str(len(paid)) +
          " row(s) ~ " + str(est) + " credits (est; exact cost preflighted)")
    for n, rt, slug in paid:
        print("    row %3d  video       %s" % (n, slug))
    if done:
        print("")
        print("  already Generated/Approved (skipped): " + str(done) + " row(s)")
    print("")
    print("Generate the free rows now; ask before the paid rows (or run `/storyboard-generate b-roll`).")
    root = os.path.dirname(os.path.abspath(sb_path))
    _print_open_feedback(doc, root)
    return {"local": local, "paid": paid, "done": done, "est_credits": est}

USAGE = "commands: plan | add_feedback | feedback | resolve | download | silence | poster | register | register_clip"

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print(USAGE); sys.exit(1)
        cmd = sys.argv[1]
        if cmd == "download":
            v = download(sys.argv[2], sys.argv[3]); print(v)
        elif cmd == "silence":
            print(silence(sys.argv[2]))
        elif cmd == "poster":
            print(poster_from(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "0.5"))
        elif cmd == "register":
            # register <sb> <n> <file> <poster> <kind> <source> [dur] [series_id]
            register(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7],
                     sys.argv[8] if len(sys.argv) > 8 else None,
                     series_id=sys.argv[9] if len(sys.argv) > 9 else None)
        elif cmd == "register_clip":
            # register_clip <sb> <a> <b> <file> <poster> <kind> <source> <total_dur> [t0 t1 ...]
            #   [--poster-times t,t,...]  explicit poster second per row (best: the beat settle times)
            #   [--poster-at 0.78]        else this fraction through each segment
            #   [--no-beat-posters]       every row keeps the one shared poster (old behaviour)
            argv, pos = sys.argv[2:], []
            beat_posters, poster_at, poster_times = True, BEAT_POSTER_AT, None
            i = 0
            while i < len(argv):
                if argv[i] == "--no-beat-posters":
                    beat_posters = False; i += 1
                elif argv[i] == "--poster-at":
                    poster_at = float(argv[i+1]); i += 2
                elif argv[i] == "--poster-times":
                    poster_times = [None if v.strip() in ("", "-") else float(v)
                                    for v in argv[i+1].split(",")]; i += 2
                else:
                    pos.append(argv[i]); i += 1
            register_clip(*pos[:8], cuts=(pos[8:] or None), beat_posters=beat_posters,
                          poster_at=poster_at, poster_times=poster_times)
        elif cmd == "plan":
            plan(sys.argv[2])
        elif cmd == "add_feedback":
            # add_feedback <sb> <selector> "<text>"  — selector: n | a,b,c | A-B
            add_feedback(sys.argv[2], sys.argv[3], sys.argv[4])
        elif cmd == "resolve":
            # resolve <sb> [selector|all] [--id ID]
            rest = sys.argv[3:]
            eid = None
            if "--id" in rest:
                i = rest.index("--id"); eid = rest[i + 1]; rest = rest[:i] + rest[i + 2:]
            resolve_feedback(sys.argv[2], rest[0] if rest else "all", eid)
        elif cmd == "feedback":
            # feedback <sb> [selector]
            feedback_cmd(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        else:
            print(USAGE); sys.exit(1)
    except (ValueError, KeyError, IndexError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
