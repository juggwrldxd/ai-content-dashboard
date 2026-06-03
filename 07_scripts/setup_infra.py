#!/usr/bin/env python3
"""
setup_infra.py — One-time infrastructure setup.
Creates folder structure, empty JSON databases, and validates config.
"""
import json, os, shutil, sys
from pathlib import Path

BASE = Path.home() / "ai_content_business"

# Folders to create (already done, this verifies + creates missing)
FOLDERS = [
    "00_inputs/photos_raw",
    "00_inputs/target_accounts",
    "01_processing/base_models",
    "01_processing/lora_models",
    "01_processing/bulk_generation",
    "01_processing/image_validation/validated",
    "01_processing/image_validation/ready",
    "01_processing/image_validation/rejected",
    "02_content/captions",
    "02_content/daily_ideas",
    "02_content/posting_tracker",
    "03_accounts/x_accounts",
    "03_accounts/telegram_vip",
    "03_accounts/telegram_teaser",
    "03_accounts/reddit_accounts",
    "03_accounts/email_list",
    "04_revenue",
    "05_inspection/daily",
    "05_inspection/weekly",
    "05_inspection/monthly",
    "06_backup",
    "07_scripts",
    "08_dashboard/data",
]

# Empty JSON databases to create
DATABASES = {
    "04_revenue/nowpayments_logs.json": {"payments": [], "webhooks": []},
    "04_revenue/manual_payments.log": [],
    "04_revenue/customer_database.json": {"vip_members": [], "vip_history": []},
    "04_revenue/model_payouts.json": {},
    "03_accounts/credentials.json": {"accounts": [], "proxies": []},
    "00_inputs/target_accounts/target_accounts.json": {"accounts": [], "last_scraped": None},
    "00_inputs/target_accounts/scraped_data.json": {"engagement_data": [], "hashtags": [], "captions": []},
    "02_content/posting_tracker/posting_log.json": {"posts": []},
    "08_dashboard/data/analytics_daily.json": {"followers": 0, "revenue_today": 0, "revenue_week": 0, "posts_today": 0, "vip_members": 0, "last_updated": None},
}


def setup():
    print("🏢 AI Content Business — Infrastructure Setup\n")

    # Create folders
    for folder in FOLDERS:
        path = BASE / folder
        path.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {folder}/")

    # Create database files
    for path_str, default in DATABASES.items():
        path = BASE / path_str
        if not path.exists():
            with open(path, "w") as f:
                json.dump(default, f, indent=2)
            print(f"  ✅ {path_str}")
        else:
            print(f"  ⏭️  {path_str} (exists)")

    # Check config.yaml
    config_path = BASE / "config.yaml"
    if config_path.exists():
        print(f"\n  ✅ config.yaml found")
    else:
        print(f"\n  ⚠️  config.yaml missing — create from template")

    print(f"\n✅ Setup complete. {len(FOLDERS)} folders, {len(DATABASES)} databases.")
    return True


if __name__ == "__main__":
    setup()
