#!/usr/bin/env python3
"""ingest_review.py — merge an exported stakeholder-review payload back into storyboard.json.

Usage:
    ingest_review.py <storyboard.json> <payload.json|-> [--apply]

Without --apply: prints a diff-style summary of what would change and exits without writing.
With --apply:
  - appends a feedback entry {who, when, text, id, rows, verdict} to each row that has a
    note and/or verdict in the payload
  - sets status "Approved" for rows with verdict "approve", but only if the row's current
    status is "Generated" (never lowers a status, never touches Draft/Approved rows)
  - is idempotent: an entry already recorded for the same (reviewer, exported_at, row n) is
    skipped on a re-run
"""
import argparse, json, sys, uuid
from datetime import datetime, timezone


def load_payload(path):
    if path == "-":
        raw = sys.stdin.read()
    else:
        with open(path) as f:
            raw = f.read()
    return json.loads(raw)


def date_only(exported_at):
    try:
        dt = datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return (exported_at or "")[:10]


def already_ingested(row, reviewer, exported_at, n):
    """An entry is a duplicate if some feedback item already carries the same
    (reviewer, exported_at, row n) signature. We stash the full exported_at timestamp
    in a `review_export_at` field (alongside the human-readable date in `when`) so this
    check is exact even though `when` itself is date-only — that's how --apply stays
    idempotent across re-runs of the same payload."""
    who = f"{reviewer} (review page)"
    for fb in row.get("feedback") or []:
        if (fb.get("who") == who
                and fb.get("review_export_at") == exported_at
                and n in (fb.get("rows") or [])):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard_json")
    ap.add_argument("payload")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with open(args.storyboard_json) as f:
        doc = json.load(f)
    payload = load_payload(args.payload)

    reviewer = (payload.get("reviewer") or "anonymous reviewer").strip() or "anonymous reviewer"
    exported_at = payload.get("exported_at") or datetime.now(timezone.utc).isoformat()
    when_date = date_only(exported_at)
    entries = payload.get("rows") or []

    rows_by_n = {r["n"]: r for r in doc["rows"]}

    changed = 0
    skipped = 0
    print(f"Reviewer: {reviewer}")
    print(f"Exported at: {exported_at}")
    print(f"Entries in payload: {len(entries)}")
    print("-" * 60)

    for entry in entries:
        n = entry.get("n")
        verdict = (entry.get("verdict") or "").strip()
        note = (entry.get("note") or "").strip()
        row = rows_by_n.get(n)
        if row is None:
            print(f"row {n}: NOT FOUND in storyboard — skipping")
            skipped += 1
            continue
        if not verdict and not note:
            continue

        dup = already_ingested(row, reviewer, exported_at, n)
        cur_status = row.get("status", "Draft")
        will_promote = verdict == "approve" and cur_status == "Generated"

        label = {"approve": "APPROVE", "changes": "NEEDS CHANGES"}.get(verdict, verdict or "(no verdict)")
        print(f"row {n}: {label}" + (f" — \"{note}\"" if note else ""))
        if dup:
            print(f"   already ingested for this reviewer/export — skip (idempotent)")
            skipped += 1
            continue
        if verdict == "approve":
            if will_promote:
                print(f"   status: {cur_status} -> Approved")
            elif cur_status == "Approved":
                print(f"   status: already Approved — unchanged")
            else:
                print(f"   status: staying {cur_status} (only Generated rows auto-promote on approve)")

        changed += 1

        if args.apply:
            text = note if note else f"({label.lower()}, no note)"
            fb_entry = {
                "who": f"{reviewer} (review page)",
                "when": when_date,
                "text": text,
                "id": uuid.uuid4().hex[:8],
                "rows": [n],
                "review_export_at": exported_at,
            }
            if verdict:
                fb_entry["verdict"] = verdict
            row.setdefault("feedback", []).append(fb_entry)
            if will_promote:
                row["status"] = "Approved"

    print("-" * 60)
    print(f"Rows changed: {changed}  |  Rows skipped (duplicate/not found/empty): {skipped}")

    if args.apply:
        with open(args.storyboard_json, "w") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
        print(f"Wrote {args.storyboard_json}")
    else:
        print("(dry run — pass --apply to write changes)")


if __name__ == "__main__":
    main()
