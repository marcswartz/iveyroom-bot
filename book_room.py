from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import fcntl
import json
import os
import re
from bot_config import SLOT_ORDER, load_config, slot_to_hour_24


BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "session.json"
LOG_FILE = BASE_DIR / "log.txt"
STATE_FILE = BASE_DIR / "state.json"
LOCK_FILE = BASE_DIR / "bot.lock"

BOOKING_URL = "https://learn.ivey.ca/accounts/1/external_tools/735?launch_type=global_navigation"

def log(message: str) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(date_str: str, slot: str, room: str) -> None:
    state = load_state()
    state.setdefault(date_str, {})[slot] = room
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


DEBUG_LOGS = False


def book_room(start_slot: str, max_bookings: int = 1) -> None:
    config = load_config()
    room_rankings = config["room_rankings"]

    target_date = datetime.now() + timedelta(days=14)
    target_day = str(target_date.day)
    target_month_label = target_date.strftime("%B %Y")
    target_year = target_date.year

    target_date_str = target_date.strftime("%Y-%m-%d")
    log(f"Starting booking for {target_date.strftime('%B %-d, %Y')}")

    if not SESSION_FILE.exists():
        log(
            "ERROR: session.json not found. Run `python3 save_session.py` first "
            "to create an authenticated Playwright session."
        )
        return

    state = load_state()
    already_booked = set(state.get(target_date_str, {}).keys())
    if already_booked:
        log(f"Already booked for {target_date_str}: {sorted(already_booked)}")

    with sync_playwright() as p:
        def debug_log(message: str) -> None:
            if DEBUG_LOGS:
                log(message)

        # In Cursor's sandbox, Chrome's Crashpad can fail due to restricted filesystem
        # xattr access. Disable the crash reporter so the browser can launch reliably.
        browser = p.chromium.launch(
            headless=False, args=["--disable-crash-reporter"]
        )
        context = browser.new_context(storage_state=str(SESSION_FILE))
        page = context.new_page()

        log("Loading booking page...")
        try:
            page.goto(BOOKING_URL, timeout=45000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
        except PlaywrightTimeoutError:
            current_url = ""
            try:
                current_url = page.url or ""
            except Exception:
                current_url = ""
            if "microsoftonline.com" in current_url or "login" in current_url.lower():
                log(
                    "ERROR: SESSION EXPIRED (or auth redirect timed out). "
                    "Please run `python3 save_session.py` to refresh session.json."
                )
            else:
                log(
                    "ERROR: Timed out loading booking page. "
                    "Check internet/VPN and try again."
                )
            try:
                page.screenshot(path=str(BASE_DIR / "debug_goto_timeout.png"))
            except Exception:
                pass
            browser.close()
            return

        # The booking UI is inside an iframe that may not appear immediately.
        booking_frame = None
        for _ in range(20):
            for frame in page.frames:
                if "apps2.ivey.ca" in frame.url:
                    booking_frame = frame
                    log("Found booking frame")
                    break
            if booking_frame:
                break
            page.wait_for_timeout(500)

        if not booking_frame:
            log("ERROR: Could not find booking iframe (giving up)")
            try:
                frame_urls = [getattr(frame, "url", "") for frame in page.frames]
                frame_urls = [u for u in frame_urls if u]
                log(f"Frame URLs seen: {frame_urls[:10]}")
            except Exception:
                pass
            try:
                page.screenshot(path=str(BASE_DIR / "debug_iframe.png"))
            except Exception:
                pass
            browser.close()
            return

        # Navigate to correct month
        clicked = False

        def normalize_ws(s: str) -> str:
            return " ".join((s or "").replace("\u00a0", " ").split())

        def current_month_label() -> str:
            try:
                title = booking_frame.locator(".ui-datepicker-title").first
                return normalize_ws((title.inner_text() or "").strip())
            except Exception:
                return ""

        def try_click_target_day_in_current_month() -> bool:
            """Click day link within the currently displayed month."""
            try:
                # Be tolerant of minor markup differences; prefer jQuery UI calendar selectors.
                links = booking_frame.query_selector_all(
                    ".ui-datepicker-calendar td a, td a[data-handler='selectDay']"
                )
                if not links:
                    log("Calendar day links not found via selector")
                for link in links:
                    parent_td = None
                    try:
                        parent_td = link.evaluate_handle("el => el.closest('td')")
                    except Exception:
                        parent_td = None

                    td_class = ""
                    try:
                        if parent_td:
                            td_class = (parent_td.evaluate("el => el.className") or "").strip()
                    except Exception:
                        td_class = ""

                    # Skip out-of-month or disabled/unselectable cells.
                    if any(
                        bad in td_class
                        for bad in ["ui-datepicker-other-month", "ui-datepicker-unselectable"]
                    ):
                        continue

                    txt = ""
                    try:
                        txt = (link.inner_text() or "").strip()
                    except Exception:
                        pass
                    if not txt:
                        try:
                            txt = (link.text_content() or "").strip()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    if txt == target_day:
                        link.click()
                        booking_frame.wait_for_timeout(2000)
                        log(f"Clicked day {target_day} in month {target_month_label}")
                        return True
            except Exception as e:
                log(f"Error clicking day in current month: {e}")
            return False

        # Navigate until the datepicker header matches the target month, then click the day.
        for _ in range(0, 12):
            shown = current_month_label()
            if shown == normalize_ws(target_month_label):
                if try_click_target_day_in_current_month():
                    clicked = True
                break

            # The "next" control is sometimes covered by the datepicker header which
            # can intercept pointer events. Use a forced click via locator/JS.
            try:
                next_loc = booking_frame.locator("a.ui-datepicker-next")
                if next_loc.count() == 0:
                    break
                next_loc.click(timeout=5000, force=True)
                booking_frame.wait_for_timeout(500)
            except Exception as e:
                log(f"Calendar navigation (next month) click failed: {e}")
                try:
                    booking_frame.evaluate(
                        "(() => { const el = document.querySelector('a.ui-datepicker-next'); if (el) el.click(); })()"
                    )
                    booking_frame.wait_for_timeout(500)
                except Exception:
                    break

        if not clicked:
            log(
                f"ERROR: Could not find target day {target_day} "
                f"(target_month={target_month_label}, year={target_year}, shown_month={current_month_label()})"
            )
            try:
                page.screenshot(path=str(BASE_DIR / "debug_calendar_day.png"))
            except Exception:
                pass
            browser.close()
            return

        def parse_room_from_title(title: str) -> str | None:
            # Expected formats include: "Room 1325 @ 1pm"
            title = title or ""
            if not title.startswith("Room "):
                return None
            try:
                rest = title[len("Room ") :]
                room = rest.split("@", 1)[0].strip()
                return room if room else None
            except Exception:
                return None

        def canonicalize_slot_label(raw: str) -> str | None:
            raw = (raw or "").strip().lower()
            raw = raw.replace("\u00a0", " ")

            # examples: "1pm", "1 pm", "1:00pm", "1:00 pm"
            m = re.match(r"^(\d{1,2})(?::00)?\s*([ap])m$", raw)
            if m:
                h = int(m.group(1))
                ap = m.group(2)
                if h == 0:
                    h = 12
                if h > 12:
                    h = h - 12
                slot = f"{h}{ap}m"
                return slot if slot in SLOT_ORDER else None

            # examples: "13:00", "14:00" (24h)
            m24 = re.match(r"^(\d{1,2}):(\d{2})$", raw)
            if m24:
                hour24 = int(m24.group(1))
                minute = int(m24.group(2))
                if minute != 0:
                    return None
                if hour24 == 0:
                    h12 = 12
                    ap = "am"
                elif hour24 < 12:
                    h12 = hour24
                    ap = "am"
                elif hour24 == 12:
                    h12 = 12
                    ap = "pm"
                else:
                    h12 = hour24 - 12
                    ap = "pm"
                slot = f"{h12}{ap}"
                return slot if slot in SLOT_ORDER else None

            return None

        def parse_title_cell(cell):
            title = (cell.get_attribute("title") or "").strip()
            if not title.startswith("Room ") or "@" not in title:
                return None, None, title
            room = parse_room_from_title(title)
            time_part = title.split("@", 1)[1].strip()
            slot = canonicalize_slot_label(time_part)
            return room, slot, title

        def cells_for_slot(slot: str):
            results = []
            cells = booking_frame.query_selector_all('td[title^="Room "]')
            for cell in cells:
                room, parsed_slot, title = parse_title_cell(cell)
                if not room or parsed_slot != slot:
                    continue
                results.append((room, cell, title))
            return results

        def is_cell_bookable(cell) -> bool:
            if not cell:
                return False
            classes = (cell.get_attribute("class") or "").strip()
            return ("bookableRoom" in classes) and ("unavailable" not in classes)

        def dump_slot_debug(slot: str, limit: int = 30) -> None:
            if not DEBUG_LOGS:
                return
            try:
                cells = cells_for_slot(slot)
                if not cells:
                    log(f"[debug] No cells found for slot {slot} after title parsing")
                    return
                log(f"[debug] Sample cells for {slot} (showing up to {limit}):")
                for room, cell, title in cells[:limit]:
                    cls = (cell.get_attribute("class") or "").strip()
                    log(f"[debug] {slot} cell room={room!r} title={title!r} class={cls!r}")
            except Exception as e:
                log(f"[debug] Failed dumping slot {slot}: {e}")

        def dump_grid_structure(limit: int = 60) -> None:
            if not DEBUG_LOGS:
                return
            """
            Broad dump to adapt to markup changes:
            - sample td[title] values (to see how the grid is keyed)
            - sample column headers (time labels)
            - sample left-hand labels (room labels)
            """
            try:
                titles = booking_frame.query_selector_all("td[title]")
                log(f"[debug] td[title] count: {len(titles)}")
                # Also collect a sample of distinct time labels from titles.
                times = set()
                for td in titles[:limit]:
                    t = (td.get_attribute("title") or "").strip()
                    c = (td.get_attribute("class") or "").strip()
                    if t:
                        log(f"[debug] td title={t!r} class={c!r}")
                        if "@ " in t:
                            times.add(t.split("@ ", 1)[1].strip())
                if times:
                    log(f"[debug] time labels (sampled): {sorted(times)[:30]}")
            except Exception as e:
                log(f"[debug] Failed dumping td[title]: {e}")

            try:
                # Time headers often appear as th elements in the table.
                headers = booking_frame.query_selector_all("table th")
                hdr_text = []
                for h in headers[:limit]:
                    txt = ""
                    try:
                        txt = (h.inner_text() or "").strip()
                    except Exception:
                        pass
                    if txt:
                        hdr_text.append(txt)
                log(f"[debug] table th sample: {hdr_text[:30]}")
            except Exception as e:
                log(f"[debug] Failed dumping headers: {e}")

            try:
                # Room labels commonly appear in first column; grab some row header-ish text.
                room_like = booking_frame.query_selector_all("table td:first-child, table th:first-child")
                room_text = []
                for el in room_like[:limit]:
                    txt = ""
                    try:
                        txt = (el.inner_text() or "").strip()
                    except Exception:
                        pass
                    if txt and txt not in room_text:
                        room_text.append(txt)
                log(f"[debug] first-column sample: {room_text[:30]}")
            except Exception as e:
                log(f"[debug] Failed dumping first-column labels: {e}")

        def book_cell(room: str, slot: str, cell) -> bool:
            if not cell:
                return False
            cell.click()
            booking_frame.wait_for_timeout(1500)
            log(f"Booked: Room {room} at {slot}")
            log(f"SUCCESS: Booked Room {room} at {slot}")
            save_state(target_date_str, slot, room)
            return True

        def find_any_bookable_cell(slot: str):
            for room, cell, _title in cells_for_slot(slot):
                if not is_cell_bookable(cell):
                    continue
                return room, cell
            return None, None

        def attempt_book_slot(slot: str) -> bool:
            if slot in already_booked:
                log(f"Skipping {slot} — already booked")
                return True

            # Prefer ranked rooms first.
            for room in room_rankings:
                for parsed_room, cell, _title in cells_for_slot(slot):
                    if parsed_room != room:
                        continue
                    if is_cell_bookable(cell):
                        log(f"Booking ranked room {room} at {slot}")
                        return book_cell(room, slot, cell)
                    break

            # Otherwise take any available room.
            any_room, any_cell = find_any_bookable_cell(slot)
            if any_room and any_cell:
                log(f"Booking fallback room {any_room} at {slot}")
                return book_cell(any_room, slot, any_cell)

            log(f"No rooms available at {slot}")
            return False

        def first_available_slot(start_slot: str) -> str | None:
            if start_slot not in SLOT_ORDER:
                return None
            start_idx = SLOT_ORDER.index(start_slot)
            for slot in SLOT_ORDER[start_idx:]:
                if slot in already_booked:
                    continue
                # Quick availability check: see if any ranked room or any room is bookable.
                for room in room_rankings:
                    for parsed_room, cell, _title in cells_for_slot(slot):
                        if parsed_room == room and is_cell_bookable(cell):
                            return slot
                any_room, any_cell = find_any_bookable_cell(slot)
                if any_room and any_cell:
                    return slot
            return None

        # Run-specific booking window:
        # - 1pm run starts at 1pm
        # - 2pm run starts at 2pm
        if start_slot not in SLOT_ORDER:
            log(f"ERROR: Invalid start slot {start_slot!r}")
            browser.close()
            return
        base_idx = SLOT_ORDER.index(start_slot)
        targets = SLOT_ORDER[base_idx:]
        log(f"Timing window start: {start_slot}; booking up to {max_bookings} slot(s)")

        booked_now = 0
        # If we fail to find any availability, dump a small sample so we can tune selectors.
        debug_dumped = False
        for desired_start in targets:
            if booked_now >= max_bookings:
                break
            if desired_start in already_booked:
                continue
            slot_to_try = first_available_slot(desired_start)
            if not slot_to_try:
                log(f"FAILED: Could not find any availability starting from {desired_start}")
                if not debug_dumped:
                    dump_slot_debug(desired_start)
                    dump_grid_structure()
                    debug_dumped = True
                continue
            if attempt_book_slot(slot_to_try):
                booked_now += 1

        if booked_now == 0:
            log("FAILED: No bookings made for today")
        else:
            log(f"SUCCESS: Made {booked_now} booking(s) for {target_date_str}")

        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start-slot",
        choices=SLOT_ORDER,
        help="Force run window start slot (used by catchup/scheduler).",
    )
    args = parser.parse_args()
    config = load_config()

    # Prevent two instances running at once
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    lock = open(str(LOCK_FILE), "w", encoding="utf-8")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("Bot already running — exiting")
        return

    try:
        if args.start_slot:
            log(f"Forced run window: {args.start_slot}")
            book_room(start_slot=args.start_slot, max_bookings=1)
        else:
            # launchd runs the same command at each StartCalendarInterval hour.
            # We must pick the slot that matches *this* run's hour (1pm run → 1pm slot, etc.).
            now_h = datetime.now().hour
            chosen = None
            for slot in config["start_slots"]:
                try:
                    if slot_to_hour_24(slot) == now_h:
                        chosen = slot
                        break
                except ValueError:
                    continue
            if chosen is None:
                chosen = config["start_slots"][0]
                log(
                    f"Scheduler run at hour {now_h}: no start_slot matches; "
                    f"fallback to first configured slot: {chosen}"
                )
            else:
                log(f"Scheduler run at hour {now_h}: booking window {chosen}")
            book_room(start_slot=chosen, max_bookings=1)
    finally:
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
        except Exception:
            pass
        lock.close()
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass


if __name__ == "__main__":
    main()

