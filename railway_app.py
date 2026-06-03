#!/usr/bin/env python3
"""Self-contained Railway app — uses Google Drive for storage."""
import json, os, sys, datetime, io, random
from pathlib import Path
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── GOOGLE DRIVE SETUP ──
DRIVE_FOLDER = "ai_content_business_data"  # Created on first run

def get_drive():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import urllib.request
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
    else:
        token_path = os.environ.get("GOOGLE_TOKEN_PATH", str(Path.home() / ".hermes" / "google_token.json"))
        with open(token_path) as f:
            creds = Credentials.from_authorized_user_info(json.load(f))
    return build("drive", "v3", credentials=creds)

def get_or_create_folder(service, name):
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    r = service.files().list(q=q, pageSize=1, fields="files(id)").execute()
    files = r.get("files", [])
    if files: return files[0]["id"]
    folder = service.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder"}, fields="id").execute()
    return folder["id"]

def read_drive_json(service, folder_id, filename):
    q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    r = service.files().list(q=q, pageSize=1, fields="files(id)").execute()
    files = r.get("files", [])
    if not files:
        # Create default
        default = {"payments":[],"vip_members":[],"accounts":[],"captions":[]}
        write_drive_json(service, folder_id, filename, default)
        return default
    import io
    data = service.files().get_media(fileId=files[0]["id"]).execute()
    return json.loads(data)

def write_drive_json(service, folder_id, filename, data):
    import io
    q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    r = service.files().list(q=q, pageSize=1, fields="files(id)").execute()
    files = r.get("files", [])
    body = json.dumps(data).encode()
    media = io.BytesIO(body)
    from googleapiclient.http import MediaIoBaseUpload
    media_obj = MediaIoBaseUpload(media, mimetype="application/json", resumable=False)
    if files:
        service.files().update(fileId=files[0]["id"], media_body=media_obj).execute()
    else:
        meta = {"name": filename, "parents": [folder_id]}
        service.files().create(body=meta, media_body=media_obj).execute()

def get_data():
    svc = get_drive()
    fid = get_or_create_folder(svc, DRIVE_FOLDER)
    return svc, fid, read_drive_json(svc, fid, "data.json")

def save_data(data):
    svc = get_drive()
    fid = get_or_create_folder(svc, DRIVE_FOLDER)
    write_drive_json(svc, fid, "data.json", data)

app = FastAPI()

@app.get("/api/stats")
def stats():
    _, _, d = get_data()
    payments = d.get("payments", [])
    month = sum(p.get("a",0) for p in payments if p.get("d","").startswith(datetime.date.today().strftime("%Y-%m")))
    return {"revenue_month": month, "vip_members": len(d.get("vip_members",[])), "images_ready": 0, "followers": 0}

@app.get("/api/models")
def models():
    _, _, d = get_data()
    return d.get("models", [
        {"name":"Annie","persona":"College Girl","status":"active","revenue":0,"vips":0,"images":0,"followers":0,"content_used_pct":0,"platforms":["X","Telegram","Reddit"],"lora_status":"missing"},
        {"name":"Yesha","persona":"Insta Baddie","status":"active","revenue":0,"vips":0,"images":0,"followers":0,"content_used_pct":0,"platforms":["X","Telegram","Badoo"],"lora_status":"missing"},
        {"name":"Jasmine","persona":"Fit / Athletic","status":"setup","revenue":0,"vips":0,"images":0,"followers":0,"content_used_pct":0,"platforms":["X"],"lora_status":"missing"},
    ])

@app.get("/api/accounts")
def accounts():
    _, _, d = get_data()
    return d.get("accounts", [])

@app.get("/api/revenue")
def revenue():
    _, _, d = get_data()
    payments = d.get("payments", [])
    total = sum(p.get("a",0) for p in payments)
    return {"entries": [{"date":p.get("d",""),"model":p.get("m",""),"amount":p.get("a",0),"source":p.get("s","")} for p in payments], "total": total}

@app.get("/api/captions")
def captions():
    _, _, d = get_data()
    return d.get("captions", [])

@app.get("/api/scraping")
def scraping():
    _, _, d = get_data()
    return {"data": d.get("scraping", [])}

@app.get("/api/mimicking")
def mimicking():
    _, _, d = get_data()
    return {"data": d.get("mimicking", [])}

@app.get("/api/dms")
def dms():
    _, _, d = get_data()
    return {"data": d.get("dms", [
        {"from":"@user1","preview":"How do I get VIP?","source":"X","time":"5 min ago","action":"reply"},
        {"from":"@user2","preview":"Telegram?","source":"OkCupid","time":"12 min ago","action":"link"},
    ])}

class RevEntry(BaseModel):
    amount: int; model: str; source: str

@app.post("/api/revenue/add")
def add(entry: RevEntry):
    svc, fid, d = get_data()
    d.setdefault("payments", []).append({
        "d": datetime.date.today().isoformat(),
        "m": entry.model, "a": entry.amount, "s": entry.source
    })
    write_drive_json(svc, fid, "data.json", d)
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index():
    html = Path(__file__).parent / "dashboard.html"
    return html.read_text() if html.exists() else "<h1>Dashboard</h1>"

# Mount dashboard HTML + static
HERE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()