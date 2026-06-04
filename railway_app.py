#!/usr/bin/env python3
"""Self-contained Railway app — full NSFW/SFW pipeline dashboard."""
import json, os, sys, datetime, io, random, subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# ── GOOGLE DRIVE SETUP ──
DRIVE_FOLDER = "ai_content_business_data"

# ── In-memory fallback for when Drive token isn't available ──
MEMORY = {"models":[],"payments":[],"vip_members":[],"accounts":[],"captions":[],"scraping":[],"gallery":[],"pipeline":{}}

def get_drive():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
    else:
        token_path = os.environ.get("GOOGLE_TOKEN_PATH", str(Path.home() / ".hermes" / "google_token.json"))
        if not os.path.exists(token_path):
            raise RuntimeError("NO_DRIVE")
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
        default = {"models":[],"payments":[],"vip_members":[],"accounts":[],"captions":[],"scraping":[],"gallery":[],"pipeline":{}}
        write_drive_json(service, folder_id, filename, default)
        return default
    data = service.files().get_media(fileId=files[0]["id"]).execute()
    return json.loads(data)

def write_drive_json(service, folder_id, filename, data):
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
    try:
        svc = get_drive()
        fid = get_or_create_folder(svc, DRIVE_FOLDER)
        d = read_drive_json(svc, fid, "data.json")
        MEMORY.clear()
        MEMORY.update(d)
        MEMORY["_drive"] = True
        return svc, fid, MEMORY
    except (RuntimeError, FileNotFoundError, Exception):
        # No Drive token — use in-memory data
        if "models" not in MEMORY or not MEMORY["models"]:
            MEMORY["models"] = DEFAULT_MODELS
        return None, None, MEMORY

def save_data(data):
    if data.get("_drive"):
        try:
            svc = get_drive()
            fid = get_or_create_folder(svc, DRIVE_FOLDER)
            write_drive_json(svc, fid, "data.json", {k:v for k,v in data.items() if not k.startswith("_")})
        except:
            pass  # silently fall back to memory

# ── Default models ──
DEFAULT_MODELS = [
    {"name":"Annie","persona":"College Girl","status":"active","revenue":0,"vips":0,"images":0,"followers":0,"platforms":["X","Telegram","Reddit"],"nsfw_lora":"missing","sfw_lora":"missing","nsfw_images":0,"sfw_images":0},
    {"name":"Yesha","persona":"Insta Baddie","status":"active","revenue":0,"vips":0,"images":0,"followers":0,"platforms":["X","Telegram","Badoo"],"nsfw_lora":"missing","sfw_lora":"missing","nsfw_images":0,"sfw_images":0},
    {"name":"Jasmine","persona":"Fit / Athletic","status":"setup","revenue":0,"vips":0,"images":0,"followers":0,"platforms":["X"],"nsfw_lora":"missing","sfw_lora":"missing","nsfw_images":0,"sfw_images":0},
]

app = FastAPI()

@app.get("/api/stats")
def stats():
    _, _, d = get_data()
    models = d.get("models", DEFAULT_MODELS)
    payments = d.get("payments", [])
    today = datetime.date.today().isoformat()
    month_prefix = datetime.date.today().strftime("%Y-%m")
    total = sum(p.get("a",0) for p in payments)
    month_total = sum(p.get("a",0) for p in payments if p.get("d","").startswith(month_prefix))
    today_total = sum(p.get("a",0) for p in payments if p.get("d","") == today)
    nsfw_total = sum(p.get("a",0) for p in payments if p.get("ct","") == "nsfw")
    sfw_total = sum(p.get("a",0) for p in payments if p.get("ct","") == "sfw")
    total_nsfw_imgs = sum(m.get("nsfw_images",0) for m in models)
    total_sfw_imgs = sum(m.get("sfw_images",0) for m in models)
    return {
        "revenue_total": total, "revenue_month": month_total, "revenue_today": today_total,
        "revenue_nsfw": nsfw_total, "revenue_sfw": sfw_total,
        "vip_members": len(d.get("vip_members",[])),
        "images_ready": total_nsfw_imgs + total_sfw_imgs,
        "images_nsfw": total_nsfw_imgs, "images_sfw": total_sfw_imgs,
        "followers": sum(m.get("followers",0) for m in models),
    }

@app.get("/api/models")
def get_models():
    _, _, d = get_data()
    return d.get("models", DEFAULT_MODELS)

@app.get("/api/accounts")
def get_accounts():
    _, _, d = get_data()
    return d.get("accounts", [])

@app.get("/api/revenue")
def get_revenue():
    _, _, d = get_data()
    payments = d.get("payments", [])
    total = sum(p.get("a",0) for p in payments)
    nsfw = sum(p.get("a",0) for p in payments if p.get("ct","") == "nsfw")
    sfw = sum(p.get("a",0) for p in payments if p.get("ct","") == "sfw")
    return {
        "entries": [{"date":p.get("d",""),"model":p.get("m",""),"amount":p.get("a",0),"source":p.get("s",""),"type":p.get("ct","sfw")} for p in payments],
        "total": total, "nsfw": nsfw, "sfw": sfw
    }

@app.get("/api/captions")
def get_captions():
    _, _, d = get_data()
    return d.get("captions", [])

@app.get("/api/scraping")
def get_scraping():
    _, _, d = get_data()
    return {"data": d.get("scraping", [])}

@app.get("/api/dms")
def get_dms():
    _, _, d = get_data()
    return {"data": d.get("dms", [
        {"from":"@user1","preview":"How do I get VIP?","source":"X","type":"nsfw","time":"5 min ago","action":"reply"},
        {"from":"@user2","preview":"Telegram link?","source":"OkCupid","type":"sfw","time":"12 min ago","action":"link"},
        {"from":"@sub1","preview":"You're so pretty","source":"Reddit","type":"sfw","time":"1h ago","action":"reply"},
        {"from":"@buyer1","preview":"Sending payment now","source":"Telegram","type":"nsfw","time":"2h ago","action":"payment"},
    ])}

@app.get("/api/gallery")
def get_gallery():
    _, _, d = get_data()
    return {"data": d.get("gallery", [])}

@app.get("/api/pipeline")
def get_pipeline():
    _, _, d = get_data()
    pipe = d.get("pipeline", {})
    # Return NSFW and SFW pipeline status per model
    result = {}
    for m in d.get("models", DEFAULT_MODELS):
        name = m["name"].lower()
        nsfw = pipe.get(f"{name}_nsfw", {"train":"idle","gen":"idle","validate":"idle","strip":"idle","post":"idle"})
        sfw = pipe.get(f"{name}_sfw", {"train":"idle","gen":"idle","validate":"idle","post":"idle"})
        result[f"{name}_nsfw"] = nsfw
        result[f"{name}_sfw"] = sfw
    return result

# ── Pipeline trigger ──
class PipelineTrigger(BaseModel):
    model: str
    content_type: str  # "nsfw" or "sfw"
    step: str  # "train", "generate", "validate", "strip", "post"

@app.post("/api/pipeline/trigger")
def trigger_pipeline(req: PipelineTrigger):
    _, _, d = get_data()
    pipe = d.setdefault("pipeline", {})
    key = f"{req.model.lower()}_{req.content_type}"
    step_data = pipe.setdefault(key, {})
    step_data[req.step] = "running"
    save_data(d)
    # In real operation, this would fork the actual script
    return {"ok": True, "model": req.model, "type": req.content_type, "step": req.step, "status": "running"}

@app.post("/api/pipeline/update")
def update_pipeline(req: PipelineTrigger):
    _, _, d = get_data()
    pipe = d.setdefault("pipeline", {})
    key = f"{req.model.lower()}_{req.content_type}"
    step_data = pipe.setdefault(key, {})
    step_data[req.step] = "done"
    save_data(d)
    return {"ok": True}

# ── Revenue entry ──
class RevEntry(BaseModel):
    amount: int; model: str; source: str; content_type: Optional[str] = "sfw"

@app.post("/api/revenue/add")
def add_revenue(entry: RevEntry):
    svc, fid, d = get_data()
    d.setdefault("payments", []).append({
        "d": datetime.date.today().isoformat(),
        "m": entry.model, "a": entry.amount,
        "s": entry.source, "ct": entry.content_type
    })
    write_drive_json(svc, fid, "data.json", d)
    return {"ok": True}

# ── Model CRUD ──
@app.post("/api/models/add")
def add_model(model: dict):
    svc, fid, d = get_data()
    d.setdefault("models", []).append({
        "name": model["name"], "persona": model.get("persona",""),
        "status": "setup", "revenue": 0, "vips": 0, "images": 0,
        "followers": 0, "platforms": model.get("platforms",["X"]),
        "nsfw_lora": "missing", "sfw_lora": "missing",
        "nsfw_images": 0, "sfw_images": 0
    })
    write_drive_json(svc, fid, "data.json", d)
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index():
    html = Path(__file__).parent / "dashboard.html"
    return html.read_text() if html.exists() else "<h1>Dashboard</h1>"
# Mount dashboard HTML — no static dir needed (all CSS/JS is inline)
HERE = Path(__file__).parent

def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()