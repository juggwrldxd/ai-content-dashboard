#!/usr/bin/env python3
"""Batch generation script for RunPod ComfyUI endpoint.

Generates images in bulk via a ComfyUI workflow hosted on RunPod.

Requirements:
    - A RunPod serverless or pod endpoint running ComfyUI with API access
    - requests library (pip install requests)
    - ComfyUI workflow JSON that accepts a "seed" node override

Usage:
    # Normal generation
    python generate_bulk.py --model sdxl-base --batch-num 1 --count 30

    # NSFW mode (uses BigLust checkpoint or similar)
    python generate_bulk.py --model biglust --batch-num 1 --count 50 --nsfw

Output directory:
    01_processing/bulk_generation/{model}_nsfw_batch_{num}/raw/
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests is required. Install with: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration — edit these for your RunPod / ComfyUI setup
# ---------------------------------------------------------------------------

RUNPOD_ENDPOINT_ID = os.environ.get(
    "RUNPOD_ENDPOINT_ID", "your-endpoint-id-here"
)
RUNPOD_API_KEY = os.environ.get(
    "RUNPOD_API_KEY", "your-runpod-api-key-here"
)
COMFYUI_WORKFLOW_PATH = os.environ.get(
    "COMFYUI_WORKFLOW_PATH",
    str(Path(__file__).parent / "workflows" / "default_generation.json"),
)

# Polling configuration
POLL_INTERVAL = 3       # seconds between status checks
MAX_POLL_TIME = 600     # max seconds to wait per job

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

BASE_DIR = Path.home() / "ai_content_business" / "01_processing" / "bulk_generation"


def build_output_dir(model: str, batch_num: int, nsfw: bool) -> Path:
    """Create and return the output directory for this batch."""
    suffix = "nsfw" if nsfw else "sfw"
    dir_name = f"{model}_{suffix}_batch_{batch_num}"
    out_dir = BASE_DIR / dir_name / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def load_workflow(model: str, nsfw: bool) -> dict:
    """Load the ComfyUI workflow JSON and apply model/NSFW tweaks.

    Override this function to customise prompt templates, model node IDs,
    or checkpoint names for your specific workflow.
    """
    path = Path(COMFYUI_WORKFLOW_PATH)
    if not path.exists():
        print(f"Warning: Workflow file not found at {path}")
        print("Creating a minimal placeholder workflow...")
        workflow = create_placeholder_workflow(model, nsfw)
    else:
        with open(path) as f:
            workflow = json.load(f)

    # ── Common overrides ──────────────────────────────────────────────
    # If your workflow JSON has a node with class_type "CheckpointLoaderSimple",
    # set its checkpoint_name here. Adjust node IDs to match your workflow.
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "CheckpointLoaderSimple":
            node["inputs"]["ckpt_name"] = model

    return workflow


def create_placeholder_workflow(model: str, nsfw: bool) -> dict:
    """Minimal ComfyUI workflow dict for reference/documentation.

    Replace with your actual workflow JSON exported from ComfyUI.
    """
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": model},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "masterpiece, best quality, detailed"
                if not nsfw
                else "nsfw, explicit, big lust, masterpiece",
                "clip": ["4", 1],
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "worst quality, low quality, blurry",
                "clip": ["4", 1],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "ComfyUI"},
            "_inputs": {"images": ["8", 0]},
        },
    }
    return workflow


def submit_runpod_job(endpoint_id: str, api_key: str, workflow: dict) -> str | None:
    """Submit a workflow to RunPod serverless endpoint. Returns job ID."""
    url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"input": {"workflow": workflow}}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("id")
    except requests.exceptions.RequestException as exc:
        print(f"  Submit failed: {exc}", file=sys.stderr)
        return None


def poll_runpod_job(
    endpoint_id: str, api_key: str, job_id: str
) -> dict | None:
    """Poll a RunPod job until complete. Returns output dict or None."""
    url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync/{job_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.time() + MAX_POLL_TIME

    while time.time() < deadline:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "COMPLETED":
                return data.get("output")
            elif status in ("FAILED", "CANCELLED"):
                error = data.get("error", "Unknown error")
                print(f"  Job {job_id} {status}: {error}", file=sys.stderr)
                return None
            # Still running
            time.sleep(POLL_INTERVAL)
        except requests.exceptions.RequestException as exc:
            print(f"  Poll error: {exc}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)
    print(f"  Timed out after {MAX_POLL_TIME}s for job {job_id}", file=sys.stderr)
    return None


def save_output(output: dict | list, output_dir: Path, index: int) -> bool:
    """Save generated image(s) from RunPod output to disk.

    RunPod may return images as base64 strings or URLs.
    Adjust based on your endpoint's return format.
    """
    if not output:
        return False

    # If output is a list, iterate items
    items = output if isinstance(output, list) else [output]

    saved = 0
    for item in items:
        # Try extracting image data (tailor to your endpoint's response shape)
        image_data = None
        if isinstance(item, dict):
            image_data = item.get("image") or item.get("images") or item.get("output")
        elif isinstance(item, str):
            image_data = item

        if not image_data:
            continue

        # If it's a base64 string
        if isinstance(image_data, str) and len(image_data) > 100:
            import base64

            try:
                raw = base64.b64decode(image_data)
                ext = "png"
                fname = f"gen_{index:04d}_{uuid.uuid4().hex[:8]}.{ext}"
                out_path = output_dir / fname
                with open(out_path, "wb") as f:
                    f.write(raw)
                saved += 1
            except Exception as exc:
                print(f"  Failed to decode/save image: {exc}", file=sys.stderr)
        # If it's a URL, download it
        elif isinstance(image_data, str) and image_data.startswith("http"):
            try:
                resp = requests.get(image_data, timeout=60)
                resp.raise_for_status()
                ext = image_data.rsplit(".", 1)[-1].split("?")[0] or "png"
                fname = f"gen_{index:04d}_{uuid.uuid4().hex[:8]}.{ext}"
                out_path = output_dir / fname
                with open(out_path, "wb") as f:
                    f.write(resp.content)
                saved += 1
            except Exception as exc:
                print(f"  Failed to download image: {exc}", file=sys.stderr)

    return saved > 0


def run_batch(
    model: str, batch_num: int, count: int, nsfw: bool
) -> int:
    """Generate `count` images. Returns number successfully generated."""
    output_dir = build_output_dir(model, batch_num, nsfw)
    print(f"Output directory: {output_dir}")
    print(f"Model: {model}  |  NSFW: {nsfw}  |  Count: {count}")
    print()

    if RUNPOD_ENDPOINT_ID == "your-endpoint-id-here":
        print("=" * 60)
        print("SETUP REQUIRED — RunPod endpoint not configured.")
        print()
        show_setup_instructions(model, nsfw)
        print("=" * 60)
        return 0

    successful = 0
    for i in range(count):
        print(f"Generating image {i + 1}/{count}...", end=" ", flush=True)

        # Load fresh workflow with a random seed per generation
        workflow = load_workflow(model, nsfw)
        inject_seed(workflow, seed=random_seed())

        job_id = submit_runpod_job(RUNPOD_ENDPOINT_ID, RUNPOD_API_KEY, workflow)
        if not job_id:
            print("❌ Failed to submit job")
            continue

        output = poll_runpod_job(RUNPOD_ENDPOINT_ID, RUNPOD_API_KEY, job_id)
        if output and save_output(output, output_dir, i):
            print("✅")
            successful += 1
        else:
            print("⚠️  No output saved")

    return successful


def inject_seed(workflow: dict, seed: int) -> None:
    """Inject a seed value into the KSampler node of the workflow."""
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "KSampler":
            node["inputs"]["seed"] = seed


def random_seed() -> int:
    """Return a random seed suitable for ComfyUI."""
    import random
    return random.randint(0, 2**32 - 1)


def show_setup_instructions(model: str, nsfw: bool) -> None:
    """Print instructions for setting up ComfyUI on RunPod."""
    print(
        """
SETUP INSTRUCTIONS — ComfyUI on RunPod
=======================================

1. DEPLOY A RUNPOD POD
   - Go to https://www.runpod.io/console/gpu/cloud
   - Search for "comfyui" in the template selector
   - Choose a GPU (e.g. RTX 4090 for SDXL, A100 for SD3/FLUX)
   - Deploy the pod (Community Cloud is cheaper)

2. INSTALL CUSTOM NODES (via ComfyUI Manager)
   - Open the ComfyUI web UI (RunPod provides the URL)
   - Install any custom nodes your workflow needs

3. ADD YOUR CHECKPOINT ({model})
   - Upload your checkpoint/model to:
       /workspace/ComfyUI/models/checkpoints/
   - Or use a popular one from HuggingFace:
       wget -O /workspace/ComfyUI/models/checkpoints/{model}.safetensors <url>

4. EXPORT YOUR WORKFLOW
   - In ComfyUI: Settings → "Enable Dev Mode" → "Save (API Format)"
   - Save as a .json file
   - Place it at: {COMFYUI_WORKFLOW_PATH}
""".rstrip()
    )

    if nsfw:
        print(
            """
5. NSFW MODE — BigLust / Adult Models
   - Download a NSFW-focused checkpoint like BigLust, PonyXL, or similar
   - Place it in /workspace/ComfyUI/models/checkpoints/
   - Update the --model argument to match the checkpoint filename

   Recommended NSFW checkpoints:
   - BigLust (SD 1.5 based)
   - PonyXL (SDXL based)
   - Juggernaut XL NSFW
"""
        )

    print(
        """
6. CONNECT THE SCRIPT
   - Set these environment variables (or edit this script):
       export RUNPOD_ENDPOINT_ID="your-endpoint-id"
       export RUNPOD_API_KEY="your-runpod-api-key"

   - Or pass them inline:
       RUNPOD_ENDPOINT_ID=abc123 RUNPOD_API_KEY=xyz \\
       python generate_bulk.py --model {model} --batch-num 1 --count 10

7. RUN GENERATION
   python generate_bulk.py --model {model} --batch-num 1 --count 50 {'--nsfw' if nsfw else ''}

Output lands in: {BASE_DIR / f'{model}_{"nsfw" if nsfw else "sfw"}_batch_1' / 'raw'}
""".rstrip()
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch image generation via RunPod ComfyUI endpoint."
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model/checkpoint name (e.g. sdxl-base, biglust, juggernaut-xl)",
    )
    parser.add_argument(
        "--batch-num",
        type=int,
        required=True,
        help="Batch number for output directory naming",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of images to generate (default: 50)",
    )
    parser.add_argument(
        "--nsfw",
        action="store_true",
        help="Enable NSFW mode (uses BigLust/adult checkpoint prompt)",
    )
    args = parser.parse_args()

    if args.count < 1:
        print("Error: --count must be >= 1", file=sys.stderr)
        sys.exit(1)

    successful = run_batch(
        model=args.model,
        batch_num=args.batch_num,
        count=args.count,
        nsfw=args.nsfw,
    )

    print(f"\n{'=' * 40}")
    print(f"Batch complete: {successful}/{args.count} images generated")
    print(
        f"Output: {BASE_DIR / args.model + ('_nsfw' if args.nsfw else '_sfw') + '_batch_' + str(args.batch_num) / 'raw'}"
    )


if __name__ == "__main__":
    main()