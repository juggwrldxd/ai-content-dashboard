#!/usr/bin/env python3
"""Railway app — Upgraded dashboard with Pipeline, LoRA Management, Validation."""
import json, os, datetime, io, random, hashlib
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

DRIVE_FOLDER = "ai_content_business_data"
# Railway Volume path (persistent storage for images/files)
DATA_DIR = Path("/data/ai_content_business")
ALT_DATA_DIR = Path.home() / "ai_content_business_data"
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    pass
ALT_DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_data_dir():
    """Return Railway Volume path if mounted, else local fallback."""
    if DATA_DIR.exists() and DATA_DIR.is_dir():
        # Quick check: can we write to it?
        try:
            (DATA_DIR / ".write_test").touch()
            (DATA_DIR / ".write_test").unlink()
            return DATA_DIR
        except:
            pass
    return ALT_DATA_DIR

def volume_path(*parts):
    return get_data_dir().joinpath(*parts)

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
    """Load data from Volume, fall back to Drive, then defaults."""
    data = get_data_file("dashboard_db.json", None)
    if data is not None:
        MEMORY.clear()
        MEMORY.update(data)
        return None, None, MEMORY
    # Fall back to Drive
    try:
        svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
        d = read_drive_json(svc, fid, "data.json", {})
        MEMORY.clear(); MEMORY.update(d); MEMORY["_drive"] = True
        save_data_file("dashboard_db.json", {k:v for k,v in MEMORY.items() if not k.startswith("_")})
        return svc, fid, MEMORY
    except:
        MEMORY.setdefault("models", DEFAULT_MODELS)
        save_data_file("dashboard_db.json", MEMORY)
        return None, None, MEMORY

def save_data(data):
    """Save to Volume always, Drive as backup."""
    save_data_file("dashboard_db.json", {k:v for k,v in data.items() if not k.startswith("_")})
    if data.get("_drive"):
        try:
            svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
            write_drive_json(svc, fid, "data.json", {k:v for k,v in data.items() if not k.startswith("_")})
        except: pass

def get_data_file(name, default):
    """Get data from Volume first, fall back to Drive."""
    # Primary: Volume path
    vol_path = volume_path(name)
    if vol_path.exists():
        try:
            with open(vol_path) as f:
                return json.load(f)
        except: pass
    # Secondary: Drive
    try:
        svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
        d = read_drive_json(svc, fid, name, default)
        # Cache to Volume for faster next read
        if d != default:
            try:
                with open(vol_path, "w") as f:
                    json.dump(d, f)
            except: pass
        return d
    except: pass
    return default

def save_data_file(name, data):
    """Save to Volume always. Try Drive as backup."""
    # Primary: Volume
    vol_path = volume_path(name)
    try:
        with open(vol_path, "w") as f:
            json.dump(data, f)
    except: pass
    # Secondary: Drive (best effort)
    try:
        svc = get_drive(); fid = get_or_create_folder(svc, DRIVE_FOLDER)
        write_drive_json(svc, fid, name, data)
    except: pass

app = FastAPI()
# No-cache headers for all responses
from fastapi.responses import Response
@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/static/", "/")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

# Serve static files (CSS, JS)
HERE = Path(__file__).parent
static_dir = HERE / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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
    model_id: str; version: Optional[int] = 1; type: str; source: Optional[str] = "uploaded"
    file_path: Optional[str] = ""; trigger_word: Optional[str] = ""
    images_trained: Optional[int] = 0; loss: Optional[float] = 0.0
    base_model: Optional[str] = "sd_xl"; steps: Optional[int] = 1500; lr: Optional[float] = 0.0001
    custom_name: Optional[str] = ""; dataset_image_ids: Optional[list] = []

@app.post("/api/lora/versions/add")
def add_lora_version(entry: LoraEntry):
    loras = get_data_file("lora_versions.json", [])
    new = entry.dict()
    name = entry.custom_name if entry.custom_name else f"{entry.model_id.lower()}_v{entry.version or 1}"
    new["id"] = f"lora_{name}_{int(datetime.datetime.utcnow().timestamp())}"
    new["display_name"] = entry.custom_name or f"v{entry.version or 1} {entry.type}"
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
    model: str; lora_id: str; prompt: str; nsfw_level: str; count: int = 4
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
        "storage": {"drive_folder":"ai_content_business_data","backup_enabled":False},
        "runpod": {"enabled":False,"api_key":"","endpoint_id":"","gen_endpoint_id":"",
        "sfw_checkpoint":"RealVisXL_v5.0","nsfw_checkpoint":"biglust_v5","template":"sdxl_comfyui",
        "sfw_repeat":12,"sfw_network_dim":48,"sfw_lr":0.0001,"sfw_steps":1500,
        "nsfw_repeat":15,"nsfw_network_dim":64,"nsfw_lr":0.00008,"nsfw_steps":2000,
        "default_cfg":7.0,"use_adetailer":True,"use_upscale":True,"storage_volume_id":""}
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

# ══════════════════ DATASET API ══════════════════
@app.get("/api/dataset/images")
def get_dataset_images(model: Optional[str] = None, type: Optional[str] = None):
    images = get_data_file("dataset_images.json", [])
    if model: images = [i for i in images if i.get("model","").lower() == model.lower()]
    if type: images = [i for i in images if i.get("type","").lower() == type.lower()]
    return images

class DatasetImage(BaseModel):
    model: str; type: str; filename: str; caption: Optional[str] = ""
    status: Optional[str] = "new"  # new, used, rejected

@app.post("/api/dataset/images/add")
def add_dataset_image(entry: DatasetImage):
    images = get_data_file("dataset_images.json", [])
    new = entry.dict()
    new["id"] = f"img_{int(datetime.datetime.utcnow().timestamp() * 1000)}"
    new["uploaded_at"] = datetime.datetime.utcnow().isoformat()
    new["drive_path"] = f"photos_raw/{entry.model.lower()}/{entry.type.lower()}/{entry.filename}"
    images.append(new)
    save_data_file("dataset_images.json", images)
    return {"ok":True, "id": new["id"]}

@app.post("/api/dataset/images/batch_add")
def batch_add_images(data: dict):
    """data = {model, type, files: [{filename, caption?}]}"""
    images = get_data_file("dataset_images.json", [])
    added = []
    for f in data.get("files", []):
        new = {
            "id": f"img_{int(datetime.datetime.utcnow().timestamp() * 1000)}_{len(added)}",
            "model": data["model"],
            "type": data.get("type","sfw"),
            "filename": f.get("filename",""),
            "caption": f.get("caption",""),
            "status": "new",
            "uploaded_at": datetime.datetime.utcnow().isoformat(),
            "drive_path": f"photos_raw/{data['model'].lower()}/{data.get('type','sfw').lower()}/{f.get('filename','')}"
        }
        images.append(new)
        added.append(new["id"])
    save_data_file("dataset_images.json", images)
    return {"ok":True, "count": len(added), "ids": added}

# ── NAMED DATASETS ──
@app.get("/api/dataset/list")
def list_datasets():
    return get_data_file("datasets.json", [])

@app.post("/api/dataset/create")
def create_dataset(data: dict):
    datasets = get_data_file("datasets.json", [])
    new = {
        "id": f"ds_{int(datetime.datetime.utcnow().timestamp())}",
        "name": data.get("name",""),
        "model": data.get("model",""),
        "type": data.get("type","sfw"),
        "notes": data.get("notes",""),
        "created_at": datetime.datetime.utcnow().isoformat(),
        "image_count": 0
    }
    datasets.append(new)
    save_data_file("datasets.json", datasets)
    return {"ok":True, "id": new["id"]}

# ── FILE UPLOAD (stores images on Railway Volume) ──
from fastapi import UploadFile, File, Form

@app.post("/api/dataset/upload/files")
async def upload_dataset_files(
    files: list[UploadFile] = File(...),
    model: str = Form(""),
    type: str = Form("sfw"),
    dataset_id: str = Form("")
):
    """Upload actual image files to the volume and create dataset entries."""
    if not model: return {"ok":False, "error":"Model required"}
    model_dir = volume_path("datasets", model.lower(), type.lower())
    model_dir.mkdir(parents=True, exist_ok=True)
    
    saved = []
    for f in files:
        ext = Path(f.filename).suffix if f.filename else ".jpg"
        safe_name = f"img_{int(datetime.datetime.utcnow().timestamp() * 1000)}_{len(saved)}{ext}"
        content = await f.read()
        filepath = model_dir / safe_name
        with open(filepath, "wb") as out:
            out.write(content)
        saved.append({"filename": safe_name, "original": f.filename, "size": len(content)})
    
    # Also create JSON entries with dataset_id
    images = get_data_file("dataset_images.json", [])
    for s in saved:
        entry = {
            "id": f"img_{int(datetime.datetime.utcnow().timestamp() * 1000)}_{len(images)}",
            "model": model,
            "type": type.lower(),
            "filename": s["filename"],
            "original_name": s["original"],
            "file_size": s["size"],
            "caption": "",
            "keywords": [],
            "status": "new",
            "uploaded_at": datetime.datetime.utcnow().isoformat(),
            "file_path": f"datasets/{model.lower()}/{type.lower()}/{s['filename']}"
        }
        if dataset_id:
            entry["dataset_id"] = dataset_id
        images.append(entry)
    save_data_file("dataset_images.json", images)
    
    # Update dataset image count
    if dataset_id:
        datasets = get_data_file("datasets.json", [])
        for ds in datasets:
            if ds.get("id") == dataset_id:
                ds["image_count"] = len([i for i in images if i.get("dataset_id") == dataset_id])
                break
        save_data_file("datasets.json", datasets)
    
    return {"ok":True, "saved": len(saved)}

@app.get("/api/dataset/file/{model}/{type}/{filename}")
def serve_dataset_file(model: str, type: str, filename: str):
    """Serve an uploaded dataset image for preview."""
    from fastapi.responses import FileResponse
    filepath = volume_path("datasets", model.lower(), type.lower(), filename)
    if filepath.exists():
        return FileResponse(str(filepath))
    return JSONResponse({"error":"not found"}, status_code=404)

# ── DATASET CAPTIONS ──
class DatasetCaption(BaseModel):
    image_id: str; caption: str; keywords: Optional[list] = []

@app.post("/api/dataset/images/caption")
def set_dataset_caption(entry: DatasetCaption):
    images = get_data_file("dataset_images.json", [])
    for i, img in enumerate(images):
        if img.get("id") == entry.image_id:
            images[i]["caption"] = entry.caption
            if entry.keywords:
                images[i]["keywords"] = entry.keywords
            save_data_file("dataset_images.json", images)
            return {"ok":True}
    return {"ok":False}

@app.post("/api/dataset/images/auto_caption")
def auto_caption_images(data: dict):
    """Generate captions for images using model persona."""
    images = get_data_file("dataset_images.json", [])
    _, _, d = get_data()
    models = d.get("models", DEFAULT_MODELS)
    ids = data.get("ids", [])
    count = 0
    for i, img in enumerate(images):
        if img.get("id") in ids:
            model_info = next((m for m in models if m["name"].lower() == img["model"].lower()), {})
            persona = model_info.get("persona", "person")
            img_type = img.get("type", "sfw")
            # Generate a realistic caption based on persona
            templates = [
                f"{persona.split(',')[0] if ',' in persona else persona} portrait, natural lighting, casual pose",
                f"Candid shot of {persona.split(',')[0] if ',' in persona else persona}, soft lighting, genuine smile",
                f"{persona.split(',')[0] if ',' in persona else persona} in {random.choice(['casual wear', 'outdoor setting', 'natural pose'])}",
            ]
            images[i]["caption"] = random.choice(templates)
            images[i]["keywords"] = ["portrait", img_type, img["model"].lower()]
            count += 1
    save_data_file("dataset_images.json", images)
    return {"ok":True, "count": count}

# ── EXPORT TRAINING PACKAGE ──
@app.post("/api/dataset/export/training")
def export_training_package(data: dict):
    """Export selected dataset images as a training package zip."""
    import zipfile
    ids = data.get("ids", [])
    model = data.get("model", "")
    base_model = data.get("base_model", "RealVisXL_v5.0")
    repeat = data.get("repeat", 12)
    network_dim = data.get("network_dim", 48)
    lr = data.get("lr", 0.0001)
    trigger = data.get("trigger_word", "")
    
    images = get_data_file("dataset_images.json", [])
    selected = [i for i in images if i.get("id") in ids]
    if not selected: return {"ok":False, "error":"No images selected"}
    
    export_dir = volume_path("exports")
    export_dir.mkdir(exist_ok=True)
    zip_name = f"training_{model.lower()}_{int(datetime.datetime.utcnow().timestamp())}.zip"
    zip_path = export_dir / zip_name
    
    with zipfile.ZipFile(zip_path, "w") as zf:
        # Add images
        for img in selected:
            fpath = volume_path(img.get("file_path", ""))
            if fpath.exists():
                zf.write(fpath, f"images/{img['filename']}")
        
        # Add caption file
        captions = {img["filename"]: img.get("caption", "") for img in selected}
        zf.writestr("captions.json", json.dumps(captions, indent=2))
        
        # Add training config
        config = {
            "model": model,
            "base_model": base_model,
            "lora_name": data.get("lora_name", f"{model.lower()}_lora"),
            "trigger_word": trigger,
            "training_params": {
                "repeat": repeat,
                "learning_rate": lr,
                "network_dim": network_dim,
                "resolution": 1024,
                "optimizer": "AdamW",
                "scheduler": "cosine",
                "steps": data.get("steps", 1500)
            },
            "images_count": len(selected),
            "exported_at": datetime.datetime.utcnow().isoformat()
        }
        zf.writestr("training_config.json", json.dumps(config, indent=2))
        
        # Add README
        readme = f"""# Training Package: {model}
Created: {datetime.datetime.utcnow().isoformat()}

## Steps:
1. Upload images/ folder to RunPod storage
2. Load training_config.json in Kohya GUI or your training script
3. Set base model: {base_model}
4. Train with params from training_config.json
5. Output .safetensors should be named {data.get("lora_name", f"{model.lower()}_lora")}.safetensors

## Prompt Tags:
Use trigger word: {trigger or model.lower()}
"""
        zf.writestr("README.txt", readme)
    
    return {"ok":True, "zip_file": zip_name, "size_bytes": zip_path.stat().st_size, "images": len(selected)}

# ── EXPORT GENERATION PACKAGE ──
@app.post("/api/generate/export")
def export_generation_package(data: dict):
    """Export a generation workflow package for RunPod."""
    import zipfile
    model = data.get("model", "")
    lora_name = data.get("lora_name", "")
    prompt = data.get("prompt", "")
    neg_prompt = data.get("neg_prompt", "")
    count = data.get("count", 4)
    steps = data.get("steps", 30)
    cfg = data.get("cfg", 7.0)
    use_adetailer = data.get("use_adetailer", True)
    use_upscale = data.get("use_upscale", True)
    
    export_dir = volume_path("exports")
    export_dir.mkdir(exist_ok=True)
    zip_name = f"gen_{model.lower()}_{int(datetime.datetime.utcnow().timestamp())}.zip"
    zip_path = export_dir / zip_name
    
    workflow = {
        "comfyui_workflow": "sdxl_generation",
        "lora": lora_name,
        "base_model": data.get("base_model", "RealVisXL_v5.0"),
        "prompt": prompt,
        "negative_prompt": neg_prompt,
        "batch_size": 1,
        "batch_count": count,
        "steps": steps,
        "cfg": cfg,
        "sampler": "euler",
        "scheduler": "normal",
        "adetailer": use_adetailer,
        "upscale": use_upscale,
        "upscale_to": 2048 if use_upscale else 1024,
        "seed": data.get("seed", -1),
        "varied_prompts": data.get("varied_prompts", True)
    }
    
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("generation_workflow.json", json.dumps(workflow, indent=2))
        zf.writestr("README.txt", f"""# Generation Package: {model}

## Steps:
1. Upload this workflow to RunPod ComfyUI
2. Make sure LoRA file "{lora_name}" is available
3. Load generation_workflow.json
4. Run
5. Output: {count} images

## Settings:
- ADetailer: {'ON' if use_adetailer else 'OFF'}
- Upscale to 2048: {'ON' if use_upscale else 'OFF'}
- Varied prompts: {'ON' if workflow['varied_prompts'] else 'OFF'}
""")
    
    return {"ok":True, "zip_file": zip_name, "size_bytes": zip_path.stat().st_size}

# ── MODEL PFP UPLOAD ──
@app.post("/api/models/{name}/pfp")
async def upload_model_pfp(name: str, file: UploadFile = File(...)):
    pfp_dir = volume_path("pfps")
    pfp_dir.mkdir(exist_ok=True)
    ext = Path(file.filename).suffix if file.filename else ".png"
    filename = f"{name.lower()}_pfp{ext}"
    content = await file.read()
    with open(pfp_dir / filename, "wb") as f:
        f.write(content)
    return {"ok":True, "path": f"/api/pfp/{filename}"}

@app.get("/api/pfp/{filename}")
def serve_pfp(filename: str):
    from fastapi.responses import FileResponse
    fpath = volume_path("pfps", filename)
    if fpath.exists():
        return FileResponse(str(fpath))
    return JSONResponse({"error":"not found"}, status_code=404)

# ── DOWNLOAD EXPORTED FILES ──
@app.get("/api/exports/download/{filename}")
def download_export(filename: str):
    from fastapi.responses import FileResponse
    filepath = volume_path("exports", filename)
    if filepath.exists():
        return FileResponse(str(filepath), media_type="application/zip", filename=filename)
    return JSONResponse({"error":"not found"}, status_code=404)

@app.post("/api/dataset/images/update")
def update_dataset_image(data: dict):
    images = get_data_file("dataset_images.json", [])
    for i, img in enumerate(images):
        if img.get("id") == data.get("id"):
            images[i].update({k:v for k,v in data.items() if k != "id"})
            save_data_file("dataset_images.json", images)
            return {"ok":True}
    return {"ok":False}

@app.post("/api/dataset/images/batch_tag")
def batch_tag_images(data: dict):
    """data = {ids: [...], status: 'used'|'rejected'|'new'}"""
    images = get_data_file("dataset_images.json", [])
    ids = data.get("ids", [])
    status = data.get("status", "used")
    count = 0
    for i, img in enumerate(images):
        if img.get("id") in ids:
            images[i]["status"] = status
            count += 1
    save_data_file("dataset_images.json", images)
    return {"ok":True, "updated": count}

@app.post("/api/dataset/images/delete")
def delete_dataset_image(data: dict):
    images = get_data_file("dataset_images.json", [])
    images = [i for i in images if i.get("id") != data.get("id")]
    save_data_file("dataset_images.json", images)
    return {"ok":True}

# ── ACCOUNTS VAULT (credentials store) ──
@app.get("/api/accounts/vault")
def get_accounts_vault():
    return get_data_file("vault.json", [])

class VaultEntry(BaseModel):
    email: str; password: str; model: str; used_at: Optional[str] = ""
    notes: Optional[str] = ""; status: Optional[str] = "active"

@app.post("/api/accounts/vault/add")
def add_vault_entry(entry: VaultEntry):
    vault = get_data_file("vault.json", [])
    new = entry.dict()
    new["id"] = f"vault_{int(datetime.datetime.utcnow().timestamp())}"
    vault.append(new)
    save_data_file("vault.json", vault)
    return {"ok":True, "id": new["id"]}

@app.post("/api/accounts/vault/delete")
def delete_vault_entry(data: dict):
    vault = get_data_file("vault.json", [])
    vault = [v for v in vault if v.get("id") != data.get("id")]
    save_data_file("vault.json", vault)
    return {"ok":True}

# ── ACCOUNTS SOCIAL (monitored accounts) ──
@app.get("/api/accounts/social")
def get_accounts_social():
    return get_data_file("social_monitor.json", [])

class SocialEntry(BaseModel):
    handle: str; platform: str; model: str; followers: Optional[int] = 0
    posts: Optional[int] = 0; engagement: Optional[float] = 0.0

@app.post("/api/accounts/social/add")
def add_social_entry(entry: SocialEntry):
    social = get_data_file("social_monitor.json", [])
    new = entry.dict()
    new["id"] = f"social_{int(datetime.datetime.utcnow().timestamp())}"
    new["last_checked"] = datetime.datetime.utcnow().isoformat()
    social.append(new)
    save_data_file("social_monitor.json", social)
    return {"ok":True, "id": new["id"]}

@app.post("/api/accounts/social/update")
def update_social_entry(data: dict):
    social = get_data_file("social_monitor.json", [])
    for i, s in enumerate(social):
        if s.get("id") == data.get("id"):
            data["last_checked"] = datetime.datetime.utcnow().isoformat()
            social[i].update({k:v for k,v in data.items() if k != "id"})
            save_data_file("social_monitor.json", social)
            return {"ok":True}
    return {"ok":False}

@app.post("/api/accounts/social/delete")
def delete_social_entry(data: dict):
    social = get_data_file("social_monitor.json", [])
    social = [s for s in social if s.get("id") != data.get("id")]
    save_data_file("social_monitor.json", social)
    return {"ok":True}

# ── RUNPOD API ──
@app.post("/api/runpod/test")
def test_runpod(data: dict):
    """Test RunPod connection with provided API key."""
    api_key = data.get("api_key", "")
    if not api_key: return {"ok":False, "error":"No API key"}
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.runpod.ai/v2/endpoints",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        ep_data = json.loads(resp.read())
        return {"ok":True, "endpoints": ep_data}
    except Exception as e:
        return {"ok":False, "error": str(e)}

@app.post("/api/runpod/train")
def runpod_train(data: dict):
    """Trigger training on RunPod. data = {lora_id, model, dataset_images_ids, params...}"""
    settings = get_data_file("settings.json", {})
    rp = settings.get("runpod", {})
    api_key = rp.get("api_key", "")
    endpoint_id = rp.get("endpoint_id", "")
    if not api_key or not endpoint_id:
        return {"ok":False, "error":"RunPod not configured. Go to Settings → RunPod"}
    
    lora_name = data.get("lora_name", f"{data['model'].lower()}_lora")
    trigger = data.get("trigger_word", "")
    steps = data.get("steps", 1500)
    lr = data.get("lr", 0.0001)
    
    # Build the RunPod serverless request
    payload = {
        "input": {
            "workflow_type": "lora_training",
            "lora_name": lora_name,
            "trigger_word": trigger,
            "steps": steps,
            "learning_rate": lr,
            "model_id": data.get("model", ""),
            "dataset_images": data.get("dataset_images_ids", []),
        }
    }
    
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        resp = urllib.request.urlopen(req, timeout=300)
        result = json.loads(resp.read())
        return {"ok":True, "runpod_job_id": result.get("id",""), "status": result.get("status","")}
    except Exception as e:
        return {"ok":False, "error": str(e)}

@app.post("/api/runpod/generate")
def runpod_generate(data: dict):
    """Trigger generation on RunPod. data = {model, lora_id, prompt, neg_prompt, count, steps, cfg}"""
    settings = get_data_file("settings.json", {})
    rp = settings.get("runpod", {})
    api_key = rp.get("api_key", "")
    endpoint_id = rp.get("gen_endpoint_id", rp.get("endpoint_id", ""))
    if not api_key or not endpoint_id:
        return {"ok":False, "error":"RunPod not configured"}
    
    payload = {
        "input": {
            "workflow_type": "generation",
            "lora_id": data.get("lora_id", ""),
            "prompt": data.get("prompt", ""),
            "negative_prompt": data.get("neg_prompt", ""),
            "count": data.get("count", 4),
            "steps": data.get("steps", 30),
            "cfg": data.get("cfg", 7.0),
            "seed": data.get("seed", -1),
        }
    }
    
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        resp = urllib.request.urlopen(req, timeout=600)
        result = json.loads(resp.read())
        return {"ok":True, "runpod_job_id": result.get("id",""), "status": result.get("status","")}
    except Exception as e:
        return {"ok":False, "error": str(e)}

@app.get("/api/runpod/status/{job_id}")
def runpod_status(job_id: str):
    settings = get_data_file("settings.json", {})
    rp = settings.get("runpod", {})
    api_key = rp.get("api_key", "")
    if not api_key: return {"ok":False, "error":"Not configured"}
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.runpod.ai/v2/{job_id}/status",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return {"ok":True, "status": json.loads(resp.read())}
    except Exception as e:
        return {"ok":False, "error": str(e)}

# ── STATUS ──
@app.get("/api/status")
def get_status():
    return {"ok":True,"version":"2.0","uptime":"live"}

# ── ROOT ──
@app.get("/", response_class=HTMLResponse)
def index():
    from fastapi.responses import Response
    html = Path(__file__).parent / "dashboard.html"
    content = html.read_text() if html.exists() else "<h1>Dashboard not built</h1>"
    return Response(content=content, media_type="text/html",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})

HERE = Path(__file__).parent

def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
