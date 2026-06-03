#!/usr/bin/env python3
"""
daily_inspection.py — Daily inspection of accounts, revenue, and system health.

Reads:
  - 04_revenue/customer_database.json
  - 04_revenue/nowpayments_logs.json
  - 08_dashboard/data/analytics_daily.json

Prints a summary report with:
  - Total VIP members
  - Revenue today / this week
  - New members (today)
  - Flagged accounts (suspicious activity)
  - Payment summary
  - Analytics snapshot

Output: 05_inspection/daily/{YYYY-MM-DD}_inspection.json

Cron-ready: runs standalone with no args, uses datetime for date stamp.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path.home() / "ai_content_business"

# ─── Paths ───
CUSTOMER_DB = BASE / "04_revenue" / "customer_database.json"
NOWPAYMENTS_LOG = BASE / "04_revenue" / "nowpayments_logs.json"
ANALYTICS_DAILY = BASE / "08_dashboard" / "data" / "analytics_daily.json"
OUTPUT_DIR = BASE / "05_inspection" / "daily"


def load_json(path, default=None):
    """Safely load a JSON file, returning default on any failure."""
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠️  Could not read {path.name}: {e}")
        return default


def parse_payment_date(payment):
    """Extract a datetime from a payment entry. Handles multiple formats."""
    raw = payment.get("timestamp") or payment.get("created_at") or payment.get("date", "")
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue
    return None


def get_today_and_week():
    """Get today's date and start of current week (Monday) as date objects."""
    now = datetime.now(timezone.utc)
    today = now.date()
    # Monday of current week
    week_start = today - timedelta(days=today.weekday())
    return today, week_start


def inspect_customers(data):
    """Analyze customer database."""
    vip_members = data.get("vip_members", [])
    vip_history = data.get("vip_history", [])

    today, week_start = get_today_and_week()
    flagged = []
    new_today = []

    # Check VIP members
    for member in vip_members:
        flags = []
        # Flag if missing required fields
        if not member.get("name", "").strip() and not member.get("username", "").strip():
            flags.append("missing_name")
        if not member.get("telegram_id") and not member.get("contact"):
            flags.append("missing_contact")
        # Flag if negative score or suspicious
        score = member.get("trust_score", 1.0)
        if score is not None and score < 0.5:
            flags.append("low_trust_score")
        # Flag if payment not confirmed
        if member.get("status") == "pending":
            flags.append("pending_payment")

        if flags:
            flagged.append({
                "id": member.get("id", "unknown"),
                "username": member.get("username", "N/A"),
                "flags": flags,
            })

    # Count new members today
    for entry in vip_history:
        joined_raw = entry.get("joined_at") or entry.get("date", "")
        if joined_raw:
            try:
                joined_date = datetime.strptime(joined_raw[:10], "%Y-%m-%d").date()
                if joined_date == today:
                    new_today.append(entry)
            except ValueError:
                continue

    return {
        "total_vip_members": len(vip_members),
        "vip_history_count": len(vip_history),
        "new_members_today": len(new_today),
        "flagged_accounts": len(flagged),
        "flagged_details": flagged,
    }


def inspect_revenue(data):
    """Analyze NowPayments logs for today and this week."""
    payments = data.get("payments", [])
    today, week_start = get_today_and_week()

    revenue_today = 0.0
    revenue_week = 0.0
    payments_today = 0
    payments_week = 0
    payment_details_today = []
    payment_details_week = []

    for payment in payments:
        dt = parse_payment_date(payment)
        if dt is None:
            continue
        p_date = dt.date()
        amount = float(payment.get("price_amount") or payment.get("amount") or payment.get("fiat_amount", 0))

        if p_date == today:
            revenue_today += amount
            payments_today += 1
            payment_details_today.append({
                "payment_id": payment.get("payment_id") or payment.get("id", "N/A"),
                "amount": amount,
                "currency": payment.get("price_currency", "USD"),
                "status": payment.get("payment_status", "unknown"),
                "timestamp": dt.isoformat(),
            })

        if week_start <= p_date <= today:
            revenue_week += amount
            payments_week += 1
            payment_details_week.append({
                "payment_id": payment.get("payment_id") or payment.get("id", "N/A"),
                "amount": amount,
                "currency": payment.get("price_currency", "USD"),
                "status": payment.get("payment_status", "unknown"),
                "timestamp": dt.isoformat(),
            })

    return {
        "revenue_today": round(revenue_today, 2),
        "revenue_week": round(revenue_week, 2),
        "payments_today": payments_today,
        "payments_week": payments_week,
        "payments_today_details": payment_details_today,
        "payments_week_details": payment_details_week,
    }


def inspect_analytics(data):
    """Read analytics daily snapshot."""
    return {
        "followers": data.get("followers", 0),
        "revenue_today_analytics": data.get("revenue_today", 0),
        "revenue_week_analytics": data.get("revenue_week", 0),
        "posts_today": data.get("posts_today", 0),
        "vip_members_analytics": data.get("vip_members", 0),
        "last_updated": data.get("last_updated", "never"),
    }


def print_report(inspection):
    """Print a clean human-readable summary to stdout."""
    c = inspection["customers"]
    r = inspection["revenue"]
    a = inspection["analytics"]
    date = inspection["date"]

    print(f"\n{'=' * 55}")
    print(f"📋 DAILY INSPECTION REPORT — {date}")
    print(f"{'=' * 55}")

    # ── CUSTOMERS ──
    print(f"\n👥 CUSTOMERS")
    print(f"   Total VIP members:     {c['total_vip_members']}")
    print(f"   New members today:     {c['new_members_today']}")
    print(f"   Flagged accounts:      {c['flagged_accounts']}")
    if c['flagged_details']:
        print(f"   ── Flagged Details ──")
        for flag in c['flagged_details']:
            print(f"      • {flag['username'] or flag['id']}: {', '.join(flag['flags'])}")

    # ── REVENUE ──
    print(f"\n💰 REVENUE")
    print(f"   Today:                 ${r['revenue_today']:.2f}  ({r['payments_today']} payments)")
    print(f"   This week:             ${r['revenue_week']:.2f}  ({r['payments_week']} payments)")
    if r['payments_today_details']:
        print(f"   ── Today's Payments ──")
        for p in r['payments_today_details']:
            print(f"      • {p['payment_id']}: ${p['amount']:.2f} {p['currency']} [{p['status']}] @ {p['timestamp']}")

    # ── ANALYTICS ──
    print(f"\n📊 ANALYTICS SNAPSHOT")
    print(f"   Followers:             {a['followers']}")
    print(f"   Posts today:           {a['posts_today']}")
    print(f"   Revenue (analytics):   ${a['revenue_today_analytics']}")
    print(f"   Last updated:          {a['last_updated']}")

    # ── STATUS ──
    errors = []
    warnings = []

    if c['flagged_accounts'] > 0:
        warnings.append(f"{c['flagged_accounts']} flagged account(s)")
    if not a.get('followers') and not a.get('revenue_today_analytics'):
        warnings.append("Analytics appear empty — run update_dashboard.py first")

    # Derive status
    status = "✅ ALL GOOD"
    if warnings:
        status = "⚠️  WARNINGS"
    if errors:
        status = "❌ ISSUES FOUND"

    print(f"\n🚦 STATUS: {status}")
    for w in warnings:
        print(f"      ⚠️  {w}")
    for e in errors:
        print(f"      ❌ {e}")
    print()


def save_report(inspection):
    """Save the full inspection data to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{inspection['date']}_inspection.json"
    with open(output_path, "w") as f:
        json.dump(inspection, f, indent=2, default=str)
    print(f"💾 Report saved: {output_path.relative_to(BASE)}")
    return output_path


def main():
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"🔍 Daily Inspection — {date_str}")
    print("=" * 55)

    # Load all data sources
    customers = load_json(CUSTOMER_DB, {"vip_members": [], "vip_history": []})
    payments = load_json(NOWPAYMENTS_LOG, {"payments": [], "webhooks": []})
    analytics = load_json(ANALYTICS_DAILY, {})

    # Check which files are missing (info only)
    for path, label in [
        (CUSTOMER_DB, "customer_database.json"),
        (NOWPAYMENTS_LOG, "nowpayments_logs.json"),
        (ANALYTICS_DAILY, "analytics_daily.json"),
    ]:
        if not path.exists():
            print(f"  📄 {label} — not found (will create on first run of setup_infra.py)")

    # Run inspection modules
    customer_report = inspect_customers(customers)
    revenue_report = inspect_revenue(payments)
    analytics_report = inspect_analytics(analytics)

    # Build full inspection record
    inspection = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "customers": customer_report,
        "revenue": revenue_report,
        "analytics": analytics_report,
        "summary": {
            "total_vip_members": customer_report["total_vip_members"],
            "new_members_today": customer_report["new_members_today"],
            "flagged_accounts": customer_report["flagged_accounts"],
            "revenue_today_usd": revenue_report["revenue_today"],
            "revenue_week_usd": revenue_report["revenue_week"],
            "payments_today": revenue_report["payments_today"],
        },
    }

    # Print human-readable report
    print_report(inspection)

    # Save JSON report
    save_report(inspection)

    return 0


if __name__ == "__main__":
    sys.exit(main())