#!/usr/bin/env python3
"""
train_nsfw_lora.py — Train NSFW LoRA on RunPod using BigLust v5.

Usage:
  python train_nsfw_lora.py <model_name> [--photos-dir <path>]

Example:
  python train_nsfw_lora.py annie
  python train_nsfw_lora.py annie --photos-dir ~/ai_content_business/00_inputs/photos_raw/annie_nsfw

Requires:
  - RunPod API key in config.yaml
  - 10-20 NSFW photos in 00_inputs/photos_raw/{model}_nsfw/
"""
import json, os, sys, time, zipfile, io, argparse
from pathlib import Path
import urllib.request, urllib.error

BASE = Path.home() / "ai_content_business"

def load_config():
    import yaml
    with open(BASE / "config.yaml") as f:
        return yaml.safe_load(f)

def get_runpod_auth(config):
    return config.get("runpod", {}).get("api_key", "")

def train_lora(model_name, photos_dir=None):
    config = load_config()
    api_key = get_runpod_auth(config)
    
    if not api_key:
        print("❌ RunPod API key not set in config.yaml")
        return False
    
    # Determine photos directory
    if not photos_dir:
        photos_dir = BASE / "00_inputs" / "photos_raw" / f"{model_name}_nsfw"
    else:
        photos_dir = Path(photos_dir)
    
    if not photos_dir.exists():
        print(f"❌ Photos directory not found: {photos_dir}")
        print(f"   Place 10-20 NSFW photos for '{model_name}' here")
        return False
    
    # Count photos
    photos = sorted(photos_dir.glob("*.[jJ][pP][gG]")) + \
             sorted(photos_dir.glob("*.[pP][nN][gG]")) + \
             sorted(photos_dir.glob("*.[jJ][pP][eE][gG]"))
    
    if len(photos) < 5:
        print(f"❌ Need at least 10-20 photos. Found {len(photos)} in {photos_dir}")
        return False
    
    print(f"\n📸 Found {len(photos)} photos for '{model_name}'")
    print(f"🎯 Base model: SDXL BigLust v5 (NSFW-optimized)")
    print(f"💰 Cost: ~$0.07 (15 min on RTX 4090 spot)")
    print()
    
    # For now, show the instructions since RunPod endpoint setup varies
    print("=" * 55)
    print("  RUNPOD TRAINING — Follow these steps:")
    print("=" * 55)
    print(f"""
1. Go to https://www.runpod.io → Serverless → Endpoints
2. Create endpoint using "Kohya SS SDXL" template
3. Set GPU type: RTX 4090, spot pricing: YES
4. Copy your RunPod API key into config.yaml
5. Zip your photos:
   cd {photos_dir}
   zip -j ../{model_name}_photos.zip *.jpg *.png
6. Upload zip via RunPod API:
   curl -X POST https://api.runpod.io/v2/{{endpoint_id}}/runsync \\
     -H "Authorization: Bearer $RUNPOD_API_KEY" \\
     -H "Content-Type: application/json" \\
     -d '{{
       "input": {{
         "images_zip": "data:application/zip;base64,...",
         "base_model": "sd_xl_biglust_v5",
         "model_name": "{model_name}_nsfw",
         "resolution": 1024,
         "network_dim": 64,
         "lr": 1e-4,
         "repeat": 12
       }}
     }}'
7. Download LoRA to:
   {BASE / '01_processing' / 'lora_models' / f'{model_name}_nsfw_lora.safetensors'}
""")
    
    # Create output path placeholder
    lora_path = BASE / "01_processing" / "lora_models" / f"{model_name}_nsfw_lora.safetensors"
    print(f"📁 Output will be saved to: {lora_path}")
    print(f"\n✅ Ready to train '{model_name}' once RunPod endpoint is set up.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train NSFW LoRA on RunPod")
    parser.add_argument("model_name", help="Model name (annie, yesha, jasmine)")
    parser.add_argument("--photos-dir", help="Path to NSFW photos (optional)")
    args = parser.parse_args()
    
    train_lora(args.model_name, args.photos_dir)