from __future__ import annotations

from pathlib import Path
import plistlib
import subprocess

from bot_config import load_config, slot_to_hour_24


BASE_DIR = Path(__file__).resolve().parent
LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"


def build_booker_plist(cfg: dict) -> dict:
    intervals = []
    for slot in cfg["start_slots"]:
        intervals.append({"Hour": slot_to_hour_24(slot), "Minute": 0})
    return {
        "Label": "com.iveybot.booker",
        "ProgramArguments": [
            cfg["python_path"],
            str(BASE_DIR / "book_room.py"),
        ],
        "StartCalendarInterval": intervals,
        "StandardOutPath": str(BASE_DIR / "scheduler.log"),
        "StandardErrorPath": str(BASE_DIR / "scheduler.log"),
    }


def build_catchup_plist(cfg: dict) -> dict:
    # Hourly catchup from earliest configured hour through +3 hours.
    min_hour = min(slot_to_hour_24(s) for s in cfg["start_slots"])
    max_hour = max(slot_to_hour_24(s) for s in cfg["start_slots"]) + 3
    intervals = [{"Hour": h, "Minute": 5} for h in range(min_hour, max_hour + 1)]
    return {
        "Label": "com.iveybot.catchup",
        "ProgramArguments": [
            cfg["python_path"],
            str(BASE_DIR / "catchup.py"),
        ],
        "StartCalendarInterval": intervals,
        "StandardOutPath": str(BASE_DIR / "catchup.log"),
        "StandardErrorPath": str(BASE_DIR / "catchup.log"),
    }


def write_plist(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        plistlib.dump(data, f, sort_keys=False)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=False)


def main() -> None:
    cfg = load_config()
    booker = LAUNCH_AGENTS / "com.iveybot.booker.plist"
    catchup = LAUNCH_AGENTS / "com.iveybot.catchup.plist"

    write_plist(booker, build_booker_plist(cfg))
    write_plist(catchup, build_catchup_plist(cfg))

    run(["launchctl", "unload", str(booker)])
    run(["launchctl", "unload", str(catchup)])
    run(["launchctl", "load", str(booker)])
    run(["launchctl", "load", str(catchup)])

    print("Installed and loaded launchd jobs:")
    print(f" - {booker}")
    print(f" - {catchup}")


if __name__ == "__main__":
    main()

