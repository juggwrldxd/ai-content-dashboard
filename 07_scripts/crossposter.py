#!/usr/bin/env python3
"""Post an image + caption to multiple Telegram channels via Bot API.

Usage:
    python crossposter.py --image photo.jpg --caption "Hello!" --channels @channel1,@channel2

Config:
    A config.yaml in the same directory (or specified via --config) must contain:
        bot_token: "YOUR_BOT_TOKEN"

    Or set the TELEGRAM_BOT_TOKEN environment variable.
"""

import argparse
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests is required. Install with: pip install requests")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

BOT_TOKEN_SOURCES = ["config.yaml", "TELEGRAM_BOT_TOKEN env var"]
DEFAULT_DELAY = 30  # seconds between channels
API_URL = "https://api.telegram.org/bot{token}/{method}"


def load_config(config_path: str | None) -> dict:
    """Load config from YAML file. Returns empty dict if not found."""
    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    # Try default locations
    for candidate in [
        Path(__file__).parent / "config.yaml",
        Path.cwd() / "config.yaml",
        Path.home() / ".hermes" / "config.yaml",
    ]:
        if candidate.exists():
            with open(candidate, "r") as f:
                return yaml.safe_load(f) or {}
    return {}


def get_bot_token(config: dict) -> str:
    """Resolve bot token from config or environment."""
    token = config.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print(
            "Error: No bot token found. Provide it in config.yaml "
            "or set the TELEGRAM_BOT_TOKEN environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def send_photo(token: str, chat_id: str, image_path: str, caption: str) -> tuple[bool, str]:
    """Send a photo to a single chat. Returns (success, message)."""
    url = API_URL.format(token=token, method="sendPhoto")
    files = None
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

    if not Path(image_path).is_file():
        return False, f"Image not found: {image_path}"

    try:
        with open(image_path, "rb") as f:
            files = {"photo": f}
            resp = requests.post(url, data=data, files=files, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        if result.get("ok"):
            return True, "Posted successfully"
        else:
            description = result.get("description", "Unknown API error")
            return False, f"API error: {description}"
    except requests.exceptions.Timeout:
        return False, "Request timed out (60s)"
    except requests.exceptions.RequestException as exc:
        return False, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-post an image + caption to multiple Telegram channels."
    )
    parser.add_argument("--image", type=str, required=True, help="Path to the image file")
    parser.add_argument("--caption", type=str, default="", help="Caption text (HTML supported)")
    parser.add_argument(
        "--channels",
        type=str,
        required=True,
        help="Comma-separated list of @channel usernames or numeric chat IDs",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=DEFAULT_DELAY,
        help=f"Delay in seconds between channels (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml (default: auto-detect)",
    )
    args = parser.parse_args()

    # Load config and token
    config = load_config(args.config)
    token = get_bot_token(config)

    # Parse channels
    channels = [ch.strip() for ch in args.channels.split(",") if ch.strip()]
    if not channels:
        print("Error: No channels specified.", file=sys.stderr)
        sys.exit(1)

    print(f"Cross-posting to {len(channels)} channel(s)...")
    print(f"Image: {args.image}")
    if args.caption:
        print(f"Caption: {args.caption[:80]}{'...' if len(args.caption) > 80 else ''}")
    print()

    success_count = 0
    fail_count = 0

    for i, channel in enumerate(channels):
        if i > 0 and args.delay > 0:
            print(f"Waiting {args.delay}s before next channel...")
            time.sleep(args.delay)

        print(f"[{i + 1}/{len(channels)}] Posting to {channel}...", end=" ", flush=True)
        ok, msg = send_photo(token, channel, args.image, args.caption)

        if ok:
            print("✅ Success")
            success_count += 1
        else:
            print(f"❌ Failed: {msg}")
            fail_count += 1

    print(f"\n{'=' * 40}")
    print(f"Summary: {success_count} succeeded, {fail_count} failed out of {len(channels)} channels")


if __name__ == "__main__":
    main()