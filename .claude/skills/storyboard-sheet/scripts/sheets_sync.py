#!/usr/bin/env python3
"""Sync storyboard.json <-> a Google Sheet, with no server and no database.

  sheets_sync.py push  projects/<name>/storyboard.json
  sheets_sync.py pull  projects/<name>/storyboard.json

Auth: a one-time Desktop-OAuth consent. Put the client secret at .secrets/credentials.json;
the first run caches .secrets/token.json. Both are gitignored. Scopes cover Sheets + Drive
(Drive is used to host poster images that the sheet references with =IMAGE()).

This file is intentionally dependency-light and defensive: if google libraries or credentials
are absent it explains the one-time setup instead of stack-tracing, so the pipeline is usable
offline (xlsx fallback) until the user opts into Sheets.
"""
import json, os, sys

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", ".."))
SECRETS = os.path.join(ROOT, ".secrets")
sys.path.insert(0, os.path.join(ROOT, ".claude", "skills", "storyboard-build", "scripts"))
from lib_types import (VISUAL_TYPES, TALKING_HEAD_TYPES, STATUSES, normalize_type,
                       MOTION_ENGINES, default_motion_engine)

HEADERS = ["Line #","Visual","Script","Visual Direction","Notes","Engine","_rowid"]

def _need(msg):
    print(msg); print("""
One-time setup for Google Sheets sync:
  1. Google Cloud console → enable Sheets API and Drive API.
  2. Create an OAuth client of type 'Desktop app'; download the JSON.
  3. Save it as .secrets/credentials.json in this repo.
  4. Re-run; a browser opens once for consent and caches .secrets/token.json.
Until then, use the offline xlsx: sb_to_xlsx.py <storyboard.json> <out.xlsx>.""")
    sys.exit(2)

def get_services():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        _need("Google API libraries not installed (pip install google-api-python-client "
              "google-auth-oauthlib).")
    cred_path = os.path.join(SECRETS, "credentials.json")
    tok_path = os.path.join(SECRETS, "token.json")
    if not os.path.exists(cred_path):
        _need(f"Missing {cred_path}.")
    creds = None
    if os.path.exists(tok_path):
        creds = Credentials.from_authorized_user_file(tok_path, SCOPES)
    if not creds or not creds.valid:
        from google.auth.transport.requests import Request
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
        open(tok_path, "w").write(creds.to_json())
    from googleapiclient.discovery import build
    return build("sheets", "v4", credentials=creds), build("drive", "v3", credentials=creds)

def hex_to_rgb(h):
    h = h.lstrip("#"); return {"red":int(h[0:2],16)/255,"green":int(h[2:4],16)/255,"blue":int(h[4:6],16)/255}

def ensure_folder(drive, doc, name):
    if doc.get("drive_folder_id"): return doc["drive_folder_id"]
    meta = {"name": f"Storyboard assets — {name}", "mimeType": "application/vnd.google-apps.folder"}
    f = drive.files().create(body=meta, fields="id").execute()
    drive.permissions().create(fileId=f["id"], body={"type":"anyone","role":"reader"}).execute()
    doc["drive_folder_id"] = f["id"]; return f["id"]

def upload_poster(drive, folder_id, path):
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(path, mimetype="image/png")
    f = drive.files().create(body={"name": os.path.basename(path), "parents":[folder_id]},
                             media_body=media, fields="id").execute()
    fid = f["id"]
    drive.permissions().create(fileId=fid, body={"type":"anyone","role":"reader"}).execute()
    return f"https://drive.google.com/uc?export=view&id={fid}"

def build_rows(doc, proj_dir, drive, folder_id):
    values = [HEADERS]; last_section=None; poster_cache={}
    def poster_url(row):
        src = row
        if row.get("reuse_of"):
            src = next((r for r in doc["rows"] if r["id"]==row["reuse_of"]), row)
        for a in (src.get("assets") or []):
            if a.get("poster"):
                p = os.path.join(proj_dir, a["poster"])
                if p in poster_cache: return poster_cache[p]
                if os.path.exists(p) and drive and folder_id:
                    url = upload_poster(drive, folder_id, p); poster_cache[p]=url; return url
        return ""
    types = []
    for r in doc["rows"]:
        sec = r.get("section")
        if sec and sec != last_section:
            values.append([f"▶ {sec}","","","","","",""]); types.append(None); last_section=sec
        vt = normalize_type(r["visual_type"])
        label = vt + (f" ↩{r['reuse_of']}" if r.get("reuse_of") else "")
        url = poster_url(r)
        # the thumbnail REPLACES the type label in the Visual cell once it exists
        visual = f'=IMAGE("{url}")' if url else label
        engine = r.get("motion_engine") or default_motion_engine(vt)
        values.append([r["n"], visual, r.get("script",""),
                       "" if vt in TALKING_HEAD_TYPES else r.get("visual_direction",""),
                       "" if vt in TALKING_HEAD_TYPES else r.get("notes",""),
                       engine, r["id"]])
        types.append((vt, bool(url)))
    return values, types

def push(sb_path):
    doc = json.load(open(sb_path)); proj_dir = os.path.dirname(os.path.abspath(sb_path))
    sheets, drive = get_services()
    folder_id = ensure_folder(drive, doc, doc.get("project","project"))
    if not doc.get("sheet_id"):
        ss = sheets.spreadsheets().create(body={"properties":{"title":f"Storyboard — {doc.get('project')}"}}).execute()
        doc["sheet_id"] = ss["spreadsheetId"]
    sid = doc["sheet_id"]
    values, types = build_rows(doc, proj_dir, drive, folder_id)
    sheets.spreadsheets().values().clear(spreadsheetId=sid, range="A:Z").execute()
    sheets.spreadsheets().values().update(spreadsheetId=sid, range="A1",
        valueInputOption="USER_ENTERED", body={"values": values}).execute()
    # color the Visual column per type + hide the rowid column
    sheet0 = sheets.spreadsheets().get(spreadsheetId=sid).execute()["sheets"][0]["properties"]["sheetId"]
    # reset formatting/validation/hidden state first so a re-push after a layout change is clean
    reqs = [{"repeatCell":{"range":{"sheetId":sheet0},"cell":{"userEnteredFormat":{}},"fields":"userEnteredFormat"}},
            {"setDataValidation":{"range":{"sheetId":sheet0,"startRowIndex":1}}},
            {"updateDimensionProperties":{"range":{"sheetId":sheet0,"dimension":"COLUMNS","startIndex":0,"endIndex":26},
             "properties":{"hiddenByUser":False},"fields":"hiddenByUser"}},
            {"repeatCell":{"range":{"sheetId":sheet0,"startRowIndex":0,"endRowIndex":1},
             "cell":{"userEnteredFormat":{"textFormat":{"bold":True}}},"fields":"userEnteredFormat.textFormat.bold"}},
            {"updateDimensionProperties":{"range":{"sheetId":sheet0,"dimension":"COLUMNS","startIndex":6,"endIndex":7},
             "properties":{"hiddenByUser":True},"fields":"hiddenByUser"}}]
    # widen the Visual column so the in-cell thumbnail is legible
    reqs.append({"updateDimensionProperties":{"range":{"sheetId":sheet0,"dimension":"COLUMNS","startIndex":1,"endIndex":2},
        "properties":{"pixelSize":240},"fields":"pixelSize"}})
    for i, t in enumerate(types, start=1):
        if not t:
            continue   # section header row
        vt, has_img = t
        hexc = VISUAL_TYPES.get(vt)
        if hexc:
            # type color fills the Visual cell (a colored frame behind the thumbnail; the label text when none)
            reqs.append({"repeatCell":{"range":{"sheetId":sheet0,"startRowIndex":i,"endRowIndex":i+1,
                "startColumnIndex":1,"endColumnIndex":2},
                "cell":{"userEnteredFormat":{"backgroundColor":hex_to_rgb(hexc),
                    "textFormat":{"foregroundColor":{"red":1,"green":1,"blue":1},"bold":True}}},
                "fields":"userEnteredFormat(backgroundColor,textFormat)"}})
        if has_img:
            # give rows with a thumbnail a 16:9-friendly height
            reqs.append({"updateDimensionProperties":{"range":{"sheetId":sheet0,"dimension":"ROWS",
                "startIndex":i,"endIndex":i+1},"properties":{"pixelSize":135},"fields":"pixelSize"}})
    # engine data validation (motion engine per row — editable in-sheet, read back on pull)
    reqs.append({"setDataValidation":{"range":{"sheetId":sheet0,"startRowIndex":1,"startColumnIndex":5,"endColumnIndex":6},
        "rule":{"condition":{"type":"ONE_OF_LIST","values":[{"userEnteredValue":e} for e in MOTION_ENGINES]},"showCustomUi":True}}})
    sheets.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests":reqs}).execute()
    json.dump(doc, open(sb_path,"w"), indent=2)
    print(f"pushed → https://docs.google.com/spreadsheets/d/{sid}/edit  ({len(doc['rows'])} rows)")

def pull(sb_path):
    doc = json.load(open(sb_path)); sheets, drive = get_services()
    sid = doc.get("sheet_id")
    if not sid: print("No sheet_id yet — run push first."); return
    vals = sheets.spreadsheets().values().get(spreadsheetId=sid, range="A:G").execute().get("values",[])
    hdr = vals[0]; ci = {h:i for i,h in enumerate(hdr)}
    by_id = {r["id"]: r for r in doc["rows"]}
    changed = 0
    for row in vals[1:]:
        rid = row[ci["_rowid"]] if len(row)>ci["_rowid"] else ""
        if rid not in by_id: continue
        r = by_id[rid]
        note = row[ci["Notes"]] if len(row)>ci["Notes"] else ""
        if "Status" in ci:
            status = row[ci["Status"]] if len(row)>ci["Status"] else ""
            if status and status != r.get("status"): r["status"]=status; changed+=1
        if "Engine" in ci:
            engine = (row[ci["Engine"]] if len(row)>ci["Engine"] else "").strip().lower()
            if engine in MOTION_ENGINES and engine != r.get("motion_engine"):
                r["motion_engine"]=engine; changed+=1
        if note and note not in [f.get("text") for f in r.get("feedback",[])]:
            r.setdefault("feedback",[]).append({"who":"sheet","when":None,"text":note}); changed+=1
    # Drive comments on poster files would be read here via drive.comments().list per file id.
    json.dump(doc, open(sb_path,"w"), indent=2)
    print(f"pulled feedback: {changed} update(s) merged into {sb_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("push","pull"):
        print("usage: sheets_sync.py {push|pull} <storyboard.json>"); sys.exit(1)
    (push if sys.argv[1]=="push" else pull)(sys.argv[2])
