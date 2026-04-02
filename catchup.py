import subprocess
from datetime import datetime
from pathlib import Path
import fcntl
import sys
from bot_config import load_config, slot_to_hour_24


BASE_DIR = Path(__file__).resolve().parent
LOCK_FILE = BASE_DIR / "bot.lock"
LOG_FILE = BASE_DIR / "log.txt"
BOOKING_SCRIPT = BASE_DIR / "book_room.py"


def already_ran_today(slot_label: str) -> bool:
    if not LOG_FILE.exists():
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if today in line and "SUCCESS" in line and slot_label in line:
                return True
    return False


def is_bot_running() -> bool:
    """True if book_room (or another process) holds bot.lock.

    Must not keep the lock open: catchup spawns book_room.py, which needs to
    acquire the same lock. Holding the lock here caused every catchup child to
    exit with 'Bot already running'.
    """
    try:
        lock = open(str(LOCK_FILE), "w", encoding="utf-8")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
        return False
    except IOError:
        return True


def main() -> None:
    now = datetime.now()
    config = load_config()
    if is_bot_running():
        print(f"[{now}] Bot already running — skipping catchup")
        return

    for slot in config["start_slots"]:
        if now.hour >= slot_to_hour_24(slot) and not already_ran_today(slot):
            print(f"[{now}] Missed {slot} booking — running catchup...")
            subprocess.run([sys.executable, str(BOOKING_SCRIPT), "--start-slot", slot])


if __name__ == "__main__":
    main()

