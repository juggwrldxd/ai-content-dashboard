#!/usr/bin/env python3
"""Railway app — Analytics-first command center for AI Content Business."""
import json, os, datetime, io, random
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

DRIVE_FOLDER = "ai_content_business_data"
MEMORY = {"models":[],"payments":[],"accounts":[],"captions":[],"scraping":[],"gallery":[],"pipeline":{}}
DEFAULT_MODELS = [
    {"name":"Annie","persona":"","status":"setup","revenue":0,"images":0,"followers":0,"platforms":["X","Telegram","Reddit"],"lora":"missing"},
    {"name":"Yesha","persona":"","status":"setup","revenue":0,"images":0,"followers":0,"platforms":["X","Telegram","Badoo"],"lora":"missing"},
    {"name":"Jasmine","persona":"","status":"setup","revenue":0,"images":0,"followers":0,"platforms":["X"],"lora":"missing"},
]

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
    files = r.get("files", []); return files[0]["id"] if files else service.files().create(body={"name":name,"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]

def read_drive_json(service, folder_id, filename):
    q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    r = service.files().list(q=q, pageSize=1, fields="files(id)").execute()
    files = r.get("files", [])
    if not files:
        default = {"models":[],"payments":[],"accounts":[],"captions":[],"scraping":[],"gallery":[],"pipeline":{}}
        write_drive_json(service, folder_id, filename, default); return default
    return json.loads(service.files().get_media(fileId=files[0]["id"]).execute())

def write_drive_json(service, folder_id, filename, data):
    q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    r = service.files().list(q=q, pageSize=1, fields="files(id)").execute()
    files = r.get("files", [])
    from googleapiclient.http import MediaIoBaseUpload
    media = io.BytesIO(json.dumps(data).encode())
    m = MediaIoBaseUpload(media, mimetype="application/json", resumable=False)
    if files: service.files().update(fileId=files[0]["id"], media_body=m).execute()
    else: service.files().create(body={"name":filename,"parents":[folder_id]},media_body=m).execute()

def get_data():
    try:
        svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
        d = read_drive_json(svc, fid, "data.json")
        MEMORY.clear(); MEMORY.update(d); MEMORY["_drive"] = True
        return svc, fid, MEMORY
    except:
        MEMORY.setdefault("models", DEFAULT_MODELS)
        return None, None, MEMORY

def save_data(data):
    if data.get("_drive"):
        try:
            svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
            write_drive_json(svc, fid, "data.json", {k:v for k,v in data.items() if not k.startswith("_")})
        except: pass

app = FastAPI()

# ── ANALYTICS ──
@app.get("/api/analytics")
def analytics():
    _, _, d = get_data()
    models = d.get("models", DEFAULT_MODELS)
    payments = d.get("payments", [])
    pipe = d.get("pipeline", {})
    priorities = []
    for m in models:
        name = m["name"]
        key = name.lower()
        nsfw_p = pipe.get(f"{key}_nsfw", {}); sfw_p = pipe.get(f"{key}_sfw", {})
        if m.get("lora") != "ready":
            priorities.append({"model":name,"action":"Train LoRA","priority":"high","detail":"No LoRA trained. Upload 5-10 photos to begin.","type":"nsfw"})
            priorities.append({"model":name,"action":"Train SFW LoRA","priority":"high","detail":"No SFW LoRA trained. Upload 5-10 SFW photos.","type":"sfw"})
        if m.get("images",0) == 0:
            priorities.append({"model":name,"action":"Generate images","priority":"medium","detail":"LoRA ready but no images generated yet.","type":"nsfw"})
        accts = d.get("accounts", [])
        model_accts = [a for a in accts if a.get("model") == name]
        if not model_accts:
            priorities.append({"model":name,"action":"Create accounts","priority":"high","detail":"No accounts set up for this model.","type":"all"})
        else:
            for a in model_accts:
                if a.get("warmup",0) < 100 and a.get("status") == "warmup":
                    priorities.append({"model":name,"action":f"Warmup {a['platform']}","priority":"medium","detail":f"Account at {a['warmup']}% warmup.","type":"sfw"})
        caps = d.get("captions", [])
        model_caps = [c for c in caps if c.get("model") == name]
        if len(model_caps) < 3:
            priorities.append({"model":name,"action":"Write captions","priority":"low","detail":f"Only {len(model_caps)} captions queued. Need 3+.","type":"all"})
        if m.get("revenue",0) == 0:
            priorities.append({"model":name,"action":"Log revenue","priority":"low","detail":"No revenue logged yet.","type":"all"})
    needs_attention = [m["name"] for m in models if any(p["model"]==m["name"] and p["priority"]=="high" for p in priorities)]
    total_rev = sum(p.get("a",0) for p in payments)
    total_imgs = sum(m.get("images",0) for m in models)
    total_lora = sum(1 for m in models if m.get("lora")=="ready")
    return {
        "priorities": sorted(priorities, key=lambda p: {"high":0,"medium":1,"low":2}[p["priority"]]),
        "summary": {
            "models_total": len(models),
            "models_ready": total_lora,
            "images_total": total_imgs,
            "revenue_total": total_rev,
            "needs_attention": len(needs_attention),
            "needs_attention_names": needs_attention
        }
    }

# ── MODELS ──
@app.get("/api/models")
def get_models():
    _, _, d = get_data(); return d.get("models", DEFAULT_MODELS)

@app.post("/api/models/update")
def update_model(data: dict):
    _, _, d = get_data()
    models = d.setdefault("models", [])
    for i, m in enumerate(models):
        if m["name"] == data.get("name"):
            models[i].update({k:v for k,v in data.items() if k != "name"})
            save_data(d); return {"ok":True}
    models.append({"name":data["name"],"persona":"","status":"setup","revenue":0,"images":0,"followers":0,"platforms":["X"],"lora":"missing"})
    save_data(d); return {"ok":True}

@app.post("/api/models/delete")
def delete_model(data: dict):
    _, _, d = get_data()
    d["models"] = [m for m in d.get("models",[]) if m["name"] != data.get("name")]
    save_data(d); return {"ok":True}

# ── REVENUE ──
@app.get("/api/revenue")
def get_revenue():
    _, _, d = get_data()
    payments = d.get("payments", [])
    return {"entries":[{"date":p.get("d",""),"model":p.get("m",""),"amount":p.get("a",0),"source":p.get("s","")} for p in payments],"total":sum(p.get("a",0) for p in payments)}

class RevEntry(BaseModel):
    amount: int; model: str; source: str

@app.post("/api/revenue/add")
def add_revenue(entry: RevEntry):
    _, _, d = get_data()
    d.setdefault("payments", []).append({"d":datetime.date.today().isoformat(),"m":entry.model,"a":entry.amount,"s":entry.source})
    save_data(d); return {"ok":True}

@app.post("/api/revenue/delete")
def delete_revenue(data: dict):
    _, _, d = get_data()
    idx = data.get("index")
    payments = d.get("payments", [])
    if 0 <= idx < len(payments):
        payments.pop(idx)
        save_data(d)
    return {"ok":True}

# ── CAPTIONS ──
@app.get("/api/captions")
def get_captions():
    _, _, d = get_data(); return d.get("captions", [])

class CaptionEntry(BaseModel):
    model: str; text: str; tags: Optional[str] = ""

@app.post("/api/captions/add")
def add_caption(entry: CaptionEntry):
    _, _, d = get_data()
    d.setdefault("captions", []).append({"model":entry.model,"text":entry.text,"tags":entry.tags or ""})
    save_data(d); return {"ok":True}

@app.post("/api/captions/delete")
def delete_caption(data: dict):
    _, _, d = get_data()
    idx = data.get("index")
    caps = d.get("captions", [])
    if 0 <= idx < len(caps):
        caps.pop(idx)
        save_data(d)
    return {"ok":True}

# ── SCRAPING ──
@app.get("/api/scraping")
def get_scraping():
    _, _, d = get_data(); return d.get("scraping", [])

class ScrapeEntry(BaseModel):
    model: str; target_vibes: Optional[str] = ""; target_accounts: Optional[str] = ""; hashtags: Optional[str] = ""

@app.post("/api/scraping/update")
def update_scraping(entry: ScrapeEntry):
    _, _, d = get_data()
    scraper = d.setdefault("scraping", [])
    for i, s in enumerate(scraper):
        if s["model"] == entry.model:
            scraper[i] = {"model":entry.model,"target_vibes":entry.target_vibes or "","target_accounts":entry.target_accounts or "","hashtags":entry.hashtags or "","last_scraped":"Not started"}
            save_data(d); return {"ok":True}
    scraper.append({"model":entry.model,"target_vibes":entry.target_vibes or "","target_accounts":entry.target_accounts or "","hashtags":entry.hashtags or "","last_scraped":"Not started"})
    save_data(d); return {"ok":True}

# ── GALLERY ──
@app.get("/api/gallery")
def get_gallery():
    _, _, d = get_data(); return {"data": d.get("gallery", [])}

@app.post("/api/gallery/add")
def add_gallery(data: dict):
    _, _, d = get_data()
    d.setdefault("gallery", []).append({"model":data.get("model","?"),"file":data.get("file",""),"tag":data.get("tag","pending")})
    save_data(d); return {"ok":True}

@app.post("/api/gallery/tag")
def tag_gallery(data: dict):
    _, _, d = get_data()
    gal = d.get("gallery", [])
    idx, tag = data.get("index"), data.get("tag","pending")
    if 0 <= idx < len(gal):
        gal[idx]["tag"] = tag
        save_data(d)
    return {"ok":True}

# ── PIPELINE ──
@app.get("/api/pipeline")
def get_pipeline():
    _, _, d = get_data()
    pipe = d.get("pipeline", {})
    result = {}
    for m in d.get("models", DEFAULT_MODELS):
        n = m["name"].lower()
        for t in ("nsfw","sfw"):
            key = f"{n}_{t}"
            result[key] = pipe.get(key, {"train":"idle","generate":"idle","validate":"idle","post":"idle"})
            if t == "nsfw":
                result[key]["strip"] = pipe.get(key, {}).get("strip","idle")
    return result

class PipeTrigger(BaseModel):
    model: str; content_type: str; step: str

@app.post("/api/pipeline/trigger")
def trigger_pipeline(req: PipeTrigger):
    _, _, d = get_data()
    pipe = d.setdefault("pipeline", {})
    key = f"{req.model.lower()}_{req.content_type}"
    pipe.setdefault(key, {})[req.step] = "running"
    save_data(d)
    return {"ok":True,"status":"running"}

@app.post("/api/pipeline/update")
def update_pipeline(req: PipeTrigger):
    _, _, d = get_data()
    pipe = d.setdefault("pipeline", {})
    pipe.setdefault(f"{req.model.lower()}_{req.content_type}", {})[req.step] = req.step if req.step != "done" else "done"
    save_data(d); return {"ok":True}

# ── ACCOUNTS ──
@app.get("/api/accounts")
def get_accounts():
    _, _, d = get_data(); return d.get("accounts", [])

class AccountEntry(BaseModel):
    model: str; platform: str; username: Optional[str] = ""; status: Optional[str] = "uncreated"; warmup: Optional[int] = 0; followers: Optional[int] = 0

@app.post("/api/accounts/update")
def update_account(entry: AccountEntry):
    _, _, d = get_data()
    accts = d.setdefault("accounts", [])
    for i, a in enumerate(accts):
        if a.get("model") == entry.model and a.get("platform") == entry.platform:
            accts[i] = entry.dict(); save_data(d); return {"ok":True}
    accts.append(entry.dict()); save_data(d); return {"ok":True}

# ── HUB (ideas/reminders) ──
@app.get("/api/hub")
def get_hub():
    _, _, d = get_data()
    return {
        "reminders": d.get("reminders", [
            {"text":"Check accounts for bans/suspensions","done":False},
            {"text":"Post to X at least once per model","done":False},
            {"text":"Reply to DMs across all platforms","done":False},
            {"text":"Log any revenue from today","done":False},
            {"text":"Review daily ideas for posting","done":False},
        ]),
        "ideas": d.get("ideas", [
            {"model":"Annie","idea":"Dorm room mirror selfie - 'new fit what we think'","date":"Today"},
            {"model":"Yesha","idea":"Gym pump pic - 'leg day done right'","date":"Today"},
            {"model":"Jasmine","idea":"Tattoo reveal shot - 'inked and unbothered'","date":"Today"},
        ])
    }

@app.post("/api/hub/reminder/toggle")
def toggle_reminder(data: dict):
    _, _, d = get_data()
    reminders = d.setdefault("reminders", [])
    idx = data.get("index")
    if 0 <= idx < len(reminders):
        reminders[idx]["done"] = not reminders[idx].get("done",False)
        save_data(d)
    return {"ok":True}

# ── SETTINGS ──
@app.get("/api/settings")
def get_settings():
    return {"drive_status": "connected" if MEMORY.get("_drive") else "memory_only"}

# ── ROOT ──
@app.get("/", response_class=HTMLResponse)
def index():
    html = Path(__file__).parent / "dashboard.html"
    return html.read_text() if html.exists() else "<h1>Dashboard</h1>"

HERE = Path(__file__).parent

def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()