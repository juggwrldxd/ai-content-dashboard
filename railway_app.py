#!/usr/bin/env python3
"""Railway app — Upgraded dashboard with Pipeline, LoRA Management, Validation."""
import json, os, datetime, io, random, hashlib
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

DRIVE_FOLDER = "ai_content_business_data"
MEMORY = {"models":[],"payments":[],"accounts":[],"captions":[],"scraping":[],"gallery":[],"pipeline":{}}
DEFAULT_MODELS = [
    {"name":"Annie","age":"21","ethnicity":"Asian","location":"Los Angeles","persona":"College girl, soft dom, pet play","style":"SFW+","nsfw_level":"mild","kinks":"Pet play, Lingerie","status":"active","revenue":1420,"images":180,"followers":1200,"fans":520,"platforms":["IG","X","Reddit"]},
    {"name":"Yesha","age":"23","ethnicity":"Latina","location":"Florida","persona":"Insta baddie, confident","style":"NSFW","nsfw_level":"explicit","kinks":"BDSM, Roleplay","status":"active","revenue":980,"images":140,"followers":890,"fans":410,"platforms":["IG","X"]},
    {"name":"Jasmine","age":"20","ethnicity":"Ebony","location":"New York","persona":"Fit / Athletic, sweet","style":"SFW","nsfw_level":"none","kinks":"","status":"setup","revenue":840,"images":60,"followers":310,"fans":310,"platforms":["X"]},
]

# ── DRIVE HELPERS ──
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
    return service.files().create(body={"name":name,"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]

def read_drive_json(service, folder_id, filename, default=None):
    q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    r = service.files().list(q=q, pageSize=1, fields="files(id)").execute()
    files = r.get("files", [])
    if not files:
        if default is not None: return default
        return {}
    raw = service.files().get_media(fileId=files[0]["id"]).execute()
    return json.loads(raw)

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
    """Load data from Drive, fall back to memory."""
    try:
        svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
        d = read_drive_json(svc, fid, "data.json", {})
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

def get_data_file(name, default):
    """Get a dedicated JSON file from Drive."""
    try:
        svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
        return read_drive_json(svc, fid, name, default)
    except: return default

def save_data_file(name, data):
    try:
        svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
        write_drive_json(svc, fid, name, data)
    except: pass

app = FastAPI()

# ══════════════════ EXISTING ENDPOINTS (preserved) ══════════════════

# ── ANALYTICS ──
@app.get("/api/analytics")
def analytics():
    _, _, d = get_data()
    models = d.get("models", DEFAULT_MODELS)
    payments = d.get("payments", [])
    priorities = []
    for m in models:
        name = m["name"]
        if m.get("lora","missing") not in ("ready","trained"):
            priorities.append({"model":name,"action":"Train LoRA","priority":"high","detail":"No LoRA trained.","type":"nsfw"})
        if m.get("images",0) == 0:
            priorities.append({"model":name,"action":"Generate images","priority":"medium","detail":"No images generated yet.","type":"nsfw"})
        accts = d.get("accounts", [])
        model_accts = [a for a in accts if a.get("model") == name]
        if not model_accts:
            priorities.append({"model":name,"action":"Create accounts","priority":"high","detail":"No accounts set up.","type":"all"})
        caps = d.get("captions", [])
        model_caps = [c for c in caps if c.get("model") == name]
        if len(model_caps) < 3:
            priorities.append({"model":name,"action":"Write captions","priority":"low","detail":f"Only {len(model_caps)} captions.","type":"all"})
    total_rev = sum(p.get("a",0) for p in payments)
    total_imgs = sum(m.get("images",0) for m in models)
    total_lora = sum(1 for m in models if m.get("lora") in ("ready","trained"))
    return {
        "priorities": sorted(priorities, key=lambda p: {"high":0,"medium":1,"low":2}[p["priority"]]),
        "summary": {
            "models_total": len(models), "models_ready": total_lora,
            "images_total": total_imgs, "revenue_total": total_rev,
            "needs_attention": len(set(p["model"] for p in priorities if p["priority"]=="high"))
        }
    }

# ── MODELS ──
@app.get("/api/models")
def get_models():
    _, _, d = get_data()
    models = d.get("models", DEFAULT_MODELS)
    # Enrich with LoRA count
    loras = get_data_file("lora_versions.json", [])
    for m in models:
        m["lora_count"] = len([l for l in loras if l.get("model_id","").lower() == m["name"].lower()])
    return models

@app.post("/api/models/update")
def update_model(data: dict):
    _, _, d = get_data()
    models = d.setdefault("models", [])
    for i, m in enumerate(models):
        if m["name"] == data.get("name"):
            models[i].update({k:v for k,v in data.items() if k != "name"})
            save_data(d); return {"ok":True}
    models.append({"name":data["name"],"persona":"","age":"","ethnicity":"","location":"","style":"SFW","status":"setup","revenue":0,"images":0,"followers":0,"fans":0,"platforms":["X"]})
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
    entries = [{"date":p.get("d",""),"model":p.get("m",""),"amount":p.get("a",0),"source":p.get("s",""),"net":round(p.get("a",0)*0.85,2)} for p in payments]
    by_model = {}
    for e in entries:
        by_model[e["model"]] = by_model.get(e["model"],0) + e["amount"]
    return {"entries":entries,"total":sum(p.get("a",0) for p in payments),"by_model":by_model}

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
    if 0 <= idx < len(payments): payments.pop(idx); save_data(d)
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
    if 0 <= idx < len(caps): caps.pop(idx); save_data(d)
    return {"ok":True}

# ── ACCOUNTS ──
@app.get("/api/accounts")
def get_accounts():
    _, _, d = get_data(); return d.get("accounts", [])

class AccountEntry(BaseModel):
    model: str; platform: str; username: Optional[str] = ""; status: Optional[str] = "uncreated"; warmup: Optional[int] = 0; followers: Optional[int] = 0; type: Optional[str] = "main"

@app.post("/api/accounts/update")
def update_account(entry: AccountEntry):
    _, _, d = get_data()
    accts = d.setdefault("accounts", [])
    for i, a in enumerate(accts):
        if a.get("model") == entry.model and a.get("platform") == entry.platform:
            accts[i] = entry.dict(); save_data(d); return {"ok":True}
    accts.append(entry.dict()); save_data(d); return {"ok":True}

# ── HUB ──
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
    if 0 <= idx < len(reminders): reminders[idx]["done"] = not reminders[idx].get("done",False); save_data(d)
    return {"ok":True}

# ══════════════════ NEW ENDPOINTS ══════════════════

# ── DASHBOARD (consolidated stats) ──
@app.get("/api/dashboard")
def get_dashboard():
    _, _, d = get_data()
    models = d.get("models", DEFAULT_MODELS)
    payments = d.get("payments", [])
    loras = get_data_file("lora_versions.json", [])
    batches = get_data_file("content_batches.json", [])
    
    total_rev = sum(p.get("a",0) for p in payments)
    month_rev = sum(p.get("a",0) for p in payments if p.get("d","").startswith(datetime.date.today().strftime("%Y-%m")))
    total_fans = sum(m.get("fans",0) for m in models)
    total_subs = sum(m.get("vips",0) for m in models)
    
    # Count pending validation
    pending = sum(b.get("pending_count",0) for b in batches if b.get("status") == "pending")
    validated = sum(b.get("validated_count",0) for b in batches if b.get("status") == "pending")
    
    return {
        "total_revenue": total_rev,
        "month_revenue": month_rev,
        "total_fans": total_fans,
        "total_subs": total_subs,
        "models_count": len(models),
        "lora_count": len(loras),
        "pending_validation": pending,
        "validated_count": validated,
        "revenue_by_model": {m["name"]: sum(p.get("a",0) for p in payments if p.get("m","") == m["name"]) for m in models},
        "account_sync": {
            "last_sync": d.get("last_sync","N/A"),
            "next_sync": d.get("next_sync","auto 2h"),
            "status": d.get("sync_status","idle")
        }
    }

# ── LORA VERSIONS ──
@app.get("/api/lora/versions")
def get_lora_versions(model: Optional[str] = None):
    loras = get_data_file("lora_versions.json", [])
    if model: loras = [l for l in loras if l.get("model_id","").lower() == model.lower()]
    return loras

class LoraEntry(BaseModel):
    model_id: str; version: int; type: str; source: Optional[str] = "uploaded"
    file_path: Optional[str] = ""; trigger_word: Optional[str] = ""
    images_trained: Optional[int] = 0; loss: Optional[float] = 0.0
    base_model: Optional[str] = "sd_xl"; steps: Optional[int] = 1500; lr: Optional[float] = 0.0001

@app.post("/api/lora/versions/add")
def add_lora_version(entry: LoraEntry):
    loras = get_data_file("lora_versions.json", [])
    new = entry.dict()
    new["id"] = f"lora_{entry.model_id.lower()}_v{entry.version}"
    new["trained_at"] = datetime.datetime.utcnow().isoformat()
    loras.append(new)
    save_data_file("lora_versions.json", loras)
    return {"ok":True, "id": new["id"]}

@app.post("/api/lora/versions/delete")
def delete_lora_version(data: dict):
    loras = get_data_file("lora_versions.json", [])
    loras = [l for l in loras if l.get("id") != data.get("id")]
    save_data_file("lora_versions.json", loras)
    return {"ok":True}

# ── CONTENT BATCHES (pipeline) ──
@app.get("/api/content/batches")
def get_batches():
    batches = get_data_file("content_batches.json", [])
    return sorted(batches, key=lambda b: b.get("created_at",""), reverse=True)

class BatchCreate(BaseModel):
    model: str; lora_id: str; prompt: str; nsfw_level: str; count: int
    steps: Optional[int] = 30; cfg: Optional[float] = 7.0; seed: Optional[int] = -1

@app.post("/api/content/batches/create")
def create_batch(entry: BatchCreate):
    batches = get_data_file("content_batches.json", [])
    new = entry.dict()
    new["id"] = f"batch_{int(datetime.datetime.utcnow().timestamp())}"
    new["created_at"] = datetime.datetime.utcnow().isoformat()
    new["status"] = "pending"
    new["pending_count"] = entry.count
    new["validated_count"] = 0
    new["images"] = []
    # Auto-checks (simulated)
    import random
    for i in range(entry.count):
        score = random.randint(45, 100)
        new["images"].append({
            "id": f"{new['id']}_img_{i}",
            "index": i,
            "auto_score": score,
            "auto_blur": round(random.uniform(0.01, 0.5), 3),
            "auto_nsfw_conf": round(random.uniform(0.6, 1.0), 3),
            "flags": [] if score > 70 else (["blurry"] if score < 60 else []),
            "human_status": None  # None = pending, "approved", "rejected"
        })
    batches.insert(0, new)
    save_data_file("content_batches.json", batches)
    return {"ok":True, "id": new["id"], "images": len(new["images"])}

@app.post("/api/content/batch/{batch_id}/validate")
def validate_image(batch_id: str, data: dict):
    """Validate a single image. data = {image_id, status: 'approved'|'rejected'}"""
    batches = get_data_file("content_batches.json", [])
    for b in batches:
        if b.get("id") == batch_id:
            for img in b.get("images", []):
                if img.get("id") == data.get("image_id"):
                    img["human_status"] = data.get("status")
                    # Update counts
                    approved = sum(1 for i in b["images"] if i.get("human_status") == "approved")
                    rejected = sum(1 for i in b["images"] if i.get("human_status") == "rejected")
                    b["validated_count"] = approved
                    b["pending_count"] = len(b["images"]) - approved - rejected
                    if b["pending_count"] == 0:
                        b["status"] = "completed"
                    save_data_file("content_batches.json", batches)
                    return {"ok":True, "batch_status": b["status"]}
    return {"ok":False, "error":"not found"}

@app.post("/api/content/batch/{batch_id}/validate_all")
def validate_all(batch_id: str, data: dict):
    """Validate all remaining. status = 'approved' or 'rejected'"""
    status = data.get("status", "approved")
    batches = get_data_file("content_batches.json", [])
    for b in batches:
        if b.get("id") == batch_id:
            for img in b["images"]:
                if img.get("human_status") is None:
                    img["human_status"] = status
            approved = sum(1 for i in b["images"] if i.get("human_status") == "approved")
            b["validated_count"] = approved
            b["pending_count"] = 0
            b["status"] = "completed"
            save_data_file("content_batches.json", batches)
            # Also add to content library
            save_validated_to_library(b, status)
            return {"ok":True}
    return {"ok":False}

def save_validated_to_library(batch, status):
    """Copy validated images to content library."""
    library = get_data_file("content_library.json", [])
    for img in batch["images"]:
        if img.get("human_status") == "approved" or (status == "approved" and img.get("human_status") is None):
            if img.get("auto_score", 0) >= 60:  # quality threshold
                library.append({
                    "id": img["id"],
                    "batch_id": batch["id"],
                    "model": batch["model"],
                    "lora_id": batch["lora_id"],
                    "prompt": batch.get("prompt",""),
                    "nsfw_level": batch.get("nsfw_level","sfw"),
                    "auto_score": img.get("auto_score", 0),
                    "added_at": datetime.datetime.utcnow().isoformat(),
                    "captions": [],
                    "status": "draft"  # draft, approved, posted
                })
    save_data_file("content_library.json", library)

# ── CONTENT LIBRARY ──
@app.get("/api/content/library")
def get_content_library(model: Optional[str] = None, status: Optional[str] = None, nsfw: Optional[str] = None):
    library = get_data_file("content_library.json", [])
    if model: library = [c for c in library if c.get("model","").lower() == model.lower()]
    if status: library = [c for c in library if c.get("status") == status]
    if nsfw: library = [c for c in library if c.get("nsfw_level","").lower() == nsfw.lower()]
    return library

@app.post("/api/content/library/update")
def update_content_library(data: dict):
    library = get_data_file("content_library.json", [])
    for i, c in enumerate(library):
        if c.get("id") == data.get("id"):
            library[i].update({k:v for k,v in data.items() if k != "id"})
            save_data_file("content_library.json", library)
            return {"ok":True}
    return {"ok":False}

@app.post("/api/content/library/add_caption")
def add_content_caption(data: dict):
    library = get_data_file("content_library.json", [])
    for c in library:
        if c.get("id") == data.get("id"):
            c.setdefault("captions", []).append({"text":data.get("caption",""), "added_at":datetime.datetime.utcnow().isoformat()})
            save_data_file("content_library.json", library)
            return {"ok":True}
    return {"ok":False}

# ── TEXT GENERATION ──
class TextGenRequest(BaseModel):
    model: str; content_types: list; nsfw_level: Optional[str] = "sfw"
    context: Optional[str] = ""; variations: Optional[int] = 3

@app.post("/api/textgen/generate")
def generate_text(req: TextGenRequest):
    _, _, d = get_data()
    models = d.get("models", DEFAULT_MODELS)
    model_info = next((m for m in models if m["name"].lower() == req.model.lower()), {})
    persona = model_info.get("persona", "content creator")
    results = []
    
    templates = {
        "caption": [
            f"Feeling {random.choice(['amazing', 'gorgeous', 'confident', 'playful', 'fresh'])} in this {random.choice(['new look', 'fit', 'vibe', 'mood', 'energy'])} 💋",
            f"Can't decide if I love the {random.choice(['lighting', 'vibe', 'aesthetic', 'energy', 'mood'])} more... thoughts? ✨",
            f"{random.choice(['Monday', 'Friday night', 'Weekend', 'Sunny day', 'Late night'])} energy — who's feeling it? 🖤",
            f"Sometimes you just need to {random.choice(['unwind', 'glow up', 'reset', 'feel yourself', 'breathe'])}",
            f"{random.choice(['New', 'Fresh', 'Rare', 'Exclusive', 'Unseen'])} content loading... you ready? 🔥",
        ],
        "tweet": [
            f"Morning thoughts ☕ {random.choice(['who else is up?', 'coffee first', 'grind never stops', 'feeling blessed', 'new day new energy'])}",
            f"Currently {random.choice(['ignoring my DMs', 'recharging', 'curating', 'plotting', 'manifesting'])}... be back soon 💅",
            f"Hot take: {random.choice(['confidence is everything', 'energy is contagious', 'your vibe attracts your tribe', 'work smart not hard', 'authenticity wins'])}",
        ],
        "reddit": [
            f"Been thinking about {random.choice(['this for a while', 'what you all think', 'this lately', 'something different', 'trying something new'])}... what's your take?",
        ],
        "dm": [
            f"Hey! Thanks for reaching out 💕 What's up?",
            f"Hey! Saw your message. Let's chat 💋",
        ],
        "bio": [
            f"{persona.split(',')[0] if ',' in persona else persona} | {random.choice(['DM open', 'VIP exclusive', 'Content daily', 'Link in bio', 'Just for fun'])} 💜",
        ],
        "promo": [
            "Exclusive content dropping this week! 🎯 " + random.choice(['DM for details', 'link in bio', 'limited spots available', "don't miss out", 'first 5 get a surprise']),
        ]
    }
    
    for ct in req.content_types:
        if ct in templates:
            for i in range(min(req.variations, 3)):
                text = random.choice(templates[ct])
                if req.context:
                    text = f"{req.context.strip()} — {text}"
                results.append({"type": ct, "text": text, "variation": i+1})
    
    if not results:
        results = [{"type":"caption","text":"✨ New content loading... stay tuned 💋","variation":1}]
    
    return results

# ── SETTINGS ──
@app.get("/api/settings")
def get_settings():
    settings = get_data_file("settings.json", {
        "general": {"currency":"USD","timezone":"UTC+0","date_format":"YYYY-MM-DD","default_nsfw":"SFW","auto_approve_sfw":True,"manual_review_nsfw":True},
        "training": {"base_model":"sd_xl_base_1.0","default_steps":1500,"default_lr":0.0001,"default_dim":64,"default_alpha":64,"auto_save_lora":True},
        "accounts": {"cron_schedule":"every 2h","platforms":["X","Telegram","Reddit","IG"],"auto_relogin":False,"notify_on_sync":True},
        "content": {"nsfw_detector":"fal","confidence_threshold":0.85,"auto_captions":True,"include_emojis":True,"include_hashtags":True},
        "storage": {"drive_folder":"ai_content_business_data","backup_enabled":False}
    })
    settings["_drive_status"] = "connected" if MEMORY.get("_drive") else "memory_only"
    return settings

@app.post("/api/settings/update")
def update_settings(data: dict):
    settings = get_data_file("settings.json", {})
    for k, v in data.items():
        if k in ("general","training","accounts","content","storage"):
            settings[k] = {**settings.get(k,{}), **v}
    save_data_file("settings.json", settings)
    return {"ok":True}

# ── STATUS ──
@app.get("/api/status")
def get_status():
    return {"ok":True,"version":"2.0","uptime":"live"}

# ── ROOT ──
@app.get("/", response_class=HTMLResponse)
def index():
    html = Path(__file__).parent / "dashboard.html"
    return html.read_text() if html.exists() else "<h1>Dashboard not built</h1>"

HERE = Path(__file__).parent

def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
