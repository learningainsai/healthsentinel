"""Simulated MCP connectors (guardrails doc §2 — MCP Connector Security).

No real OAuth/HealthKit/Plaid/Calendar calls are made. Each function returns
deterministic synthetic data (seeded by user_id) and documents, in its
docstring, the exact scope/security posture the real MCP connector would need
to honor (minimal scopes, no write access, masked account numbers, etc).
"""
from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime

from .. import config


def _seeded_random(user_id: str, salt: str) -> random.Random:
    seed = int(hashlib.sha256(f"{user_id}:{salt}".encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def google_drive_medical_docs(user_id: str) -> dict:
    """Google Drive MCP (blood reports). Real posture: OAuth 2.0, read-only,
    minimal scope on a single 'medical' folder, refresh token expiring every 30 days.
    Here we just report which local sample docs are 'connected'."""
    return {
        "connected": True,
        "scope": "drive.readonly:medical_folder",
        "documents": ["medical_history.md", "blood_report_latest.md"],
    }


def iwatch_activity_log(user_id: str) -> dict:
    """iWatch MCP. Real posture: Apple HealthKit secure API, cache last 7 days
    locally only, encrypted sync, never reverse-sync modifications."""
    rng = _seeded_random(user_id, "iwatch")
    return {
        "avg_sleep_hours": round(rng.uniform(5.0, 8.0), 1),
        "avg_steps": rng.randint(3000, 11000),
        "exercise_minutes_this_week": rng.randint(20, 220),
        "resting_heart_rate": rng.randint(55, 85),
    }


_SMS_ROW_RE = re.compile(r"^\|(.+)\|\s*$")


def _parse_sms_markdown(path) -> list[dict]:
    """Parses a `| id | sender | time | body |` markdown table into message
    dicts, converting each HH:MM `time` cell into today's timestamp."""
    today = datetime.now()
    messages: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _SMS_ROW_RE.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) != 4:
            continue
        msg_id, sender, time_str, body = cells
        if msg_id.lower() == "id" or set(msg_id) <= {"-"}:
            continue  # header / separator row
        try:
            hour, minute = (int(p) for p in time_str.split(":"))
        except ValueError:
            continue
        ts = int(today.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp())
        messages.append({"id": msg_id, "sender": sender, "timestamp": ts, "body": body})
    return messages


def _generate_synthetic_sms(user_id: str) -> list[dict]:
    """Fallback SMS generator for any profile without a `data/sms/*.md` file
    (e.g. ad hoc eval user ids) — deterministic, seeded by user_id."""
    rng = _seeded_random(user_id, "sms")
    today = datetime.now()

    def _at(hour: int, minute: int = 0) -> int:
        return int(today.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp())

    restaurants = ["Zomato", "Swiggy", "McDonald's", "Starbucks", "Dominos"]
    gym_provider = rng.choice(["Cult.fit", "Gold's Gym", "Anytime Fitness"])
    gym_amount = rng.randint(999, 2999)
    pharmacy_amount = rng.randint(150, 900)

    return [
        {"id": "sms-1", "sender": "AX-SWGGY", "timestamp": _at(rng.randint(7, 9), rng.randint(0, 59)),
         "body": f"Your order from {rng.choice(restaurants)} has been delivered! "
                 f"Order #{rng.randint(1000, 9999)}. Enjoy your meal."},
        {"id": "sms-2", "sender": "AX-ZMATO", "timestamp": _at(rng.randint(12, 14), rng.randint(0, 59)),
         "body": f"Order delivered from {rng.choice(restaurants)}. Rate your experience. "
                 f"Order #{rng.randint(1000, 9999)}."},
        {"id": "sms-3", "sender": "AX-SWGGY", "timestamp": _at(rng.randint(19, 21), rng.randint(0, 59)),
         "body": f"Your order from {rng.choice(restaurants)} is out for delivery. ETA 20 mins."},
        {"id": "sms-4", "sender": "AX-HDFCBK", "timestamp": _at(9, 0),
         "body": f"Rs.{gym_amount} debited from A/c XX1234 for {gym_provider.upper()} MEMBERSHIP "
                 f"on {today.strftime('%d-%m-%y')}. Avl Bal Rs.24,530.10"},
        {"id": "sms-5", "sender": "AX-APOLLO", "timestamp": _at(11, 15),
         "body": f"Rs.{pharmacy_amount} debited for APOLLO PHARMACY purchase. Thank you for shopping with us."},
        {"id": "sms-6", "sender": "AX-PRACTO", "timestamp": _at(16, 0),
         "body": "Reminder: Your appointment with Dr. Mehta is confirmed for tomorrow 10:00 AM."},
        {"id": "sms-7", "sender": "AX-OTPBNK", "timestamp": _at(10, 5),
         "body": "123456 is your OTP for login. Do not share this with anyone."},
        {"id": "sms-8", "sender": "AX-PROMO", "timestamp": _at(13, 0),
         "body": "Flat 50% off on electronics this weekend only! Shop now at BigMart."},
    ]


def sms_inbox(user_id: str) -> list[dict]:
    """SMS MCP (simulated). Real posture: read-only SMS-retriever/inbox scope,
    on-device parsing only, message bodies never leave the device, no write
    access, PII redacted before any egress.

    For demo purposes, reads a fixed markdown inbox per profile from
    `data/sms/{user_id}.md` when one exists (same per-profile-markdown
    convention as `data/medical_docs/`, so the messages are easy to read/edit
    without touching code) — mixing food-delivery, yoga/gym-payment,
    health-related, and irrelevant messages. Falls back to a deterministic
    synthetic generator for any other user_id (e.g. ad hoc eval users)."""
    md_path = config.PATHS.sms_dir / f"{user_id}.md"
    if md_path.exists():
        return _parse_sms_markdown(md_path)
    return _generate_synthetic_sms(user_id)


def google_calendar_stress_signals(user_id: str) -> dict:
    """Google Calendar MCP. Real posture: read titles/times only, create
    read-only reminders, never modify existing events, never access attendee emails."""
    rng = _seeded_random(user_id, "calendar")
    meetings = rng.randint(2, 30)
    late_night = rng.randint(0, 5)
    stress = min(10.0, round((meetings / 4) + (late_night * 1.2), 1))
    return {
        "meetings_this_week": meetings,
        "late_night_events": late_night,
        "stress_indicator": stress,
    }
