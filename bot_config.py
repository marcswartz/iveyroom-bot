from __future__ import annotations

from pathlib import Path
import json
import re


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"

SLOT_ORDER = ["1pm", "2pm", "3pm", "4pm", "5pm", "6pm", "7pm", "8pm", "9pm", "10pm"]

DEFAULT_ROOM_RANKINGS = [
    "1325",
    "1323",
    "2104",
    "3104",
    "1321",
    "1381",
    "1383",
    "1387",
    "1239",
    "1237",
    "1231",
    "1334",
    "1384",
    "2106",
    "2108",
]

DEFAULT_CONFIG = {
    "start_slots": ["1pm", "2pm"],
    "room_rankings": DEFAULT_ROOM_RANKINGS,
    "python_path": "/usr/local/bin/python3",
}


def normalize_slot(slot: str) -> str | None:
    slot = (slot or "").strip().lower()
    m = re.match(r"^([1-9]|10)\s*pm$", slot)
    if not m:
        return None
    norm = f"{int(m.group(1))}pm"
    return norm if norm in SLOT_ORDER else None


def slot_to_hour_24(slot: str) -> int:
    norm = normalize_slot(slot)
    if not norm:
        raise ValueError(f"Invalid slot label: {slot!r}")
    hour = int(norm[:-2])
    return 12 + hour if hour < 12 else 12


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg.update(raw)
        except Exception:
            pass

    # Sanitize start slots
    start_slots = []
    for s in cfg.get("start_slots", []):
        if not isinstance(s, str):
            continue
        norm = normalize_slot(s)
        if norm and norm not in start_slots:
            start_slots.append(norm)
    if not start_slots:
        start_slots = list(DEFAULT_CONFIG["start_slots"])
    start_slots.sort(key=SLOT_ORDER.index)
    cfg["start_slots"] = start_slots

    # Sanitize room rankings
    rooms = []
    for r in cfg.get("room_rankings", []):
        if isinstance(r, str):
            rr = r.strip()
            if rr:
                rooms.append(rr)
    if not rooms:
        rooms = list(DEFAULT_ROOM_RANKINGS)
    cfg["room_rankings"] = rooms

    py = cfg.get("python_path")
    cfg["python_path"] = py if isinstance(py, str) and py.strip() else DEFAULT_CONFIG["python_path"]
    return cfg

