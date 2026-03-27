from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import argparse
import time
BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "session.json"


def looks_logged_in(page) -> bool:
    """
    Best-effort detection of "login is complete" for Canvas.
    In practice, Canvas URL paths/queries can still contain "login" even
    after authentication finishes, so we primarily rely on the presence
    (or absence) of password fields and that we ended up back on
    `learn.ivey.ca` (not still on the Microsoft SSO login page).
    """
    # If a password field is present, user is almost certainly still logging in.
    if page.query_selector('input[type="password"]') is not None:
        return False
    url = (page.url or "").lower()
    if "microsoftonline.com" in url:
        return False
    if "learn.ivey.ca" not in url:
        return False

    # Canvas logged-in pages typically show "Log out"/"Logout".
    # This is a heuristic, but it's much safer than just "no password field".
    content = ""
    try:
        content = page.content().lower()
    except Exception:
        content = ""

    if ("log out" not in content) and ("logout" not in content):
        return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect when login is complete and save session.json.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="Max seconds to wait in --auto mode.",
    )
    args = parser.parse_args()

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Saving authenticated session to: {SESSION_FILE}")

    with sync_playwright() as p:
        # Disable Chrome crash reporter to avoid sandbox xattr permission issues.
        browser = p.chromium.launch(
            headless=False, args=["--disable-crash-reporter"]
        )
        context = browser.new_context()
        page = context.new_page()

        print("Opening Canvas login page...")
        page.goto("https://learn.ivey.ca/")

        if args.auto:
            print(
                "Please log in manually in the browser window. "
                f"Auto-saving when login looks complete (timeout {args.timeout_seconds}s)...",
                flush=True,
            )
            deadline = time.time() + args.timeout_seconds
            last_log = 0.0
            while time.time() < deadline:
                try:
                    if looks_logged_in(page):
                        break
                except Exception:
                    # Ignore transient navigation/DOM issues; we'll check again.
                    pass
                now = time.time()
                if now - last_log > 10:
                    try:
                        print(f"[save_session] Waiting... current url: {page.url}", flush=True)
                    except Exception:
                        pass
                    last_log = now
                time.sleep(2)
            else:
                raise TimeoutError(
                    f"Timed out waiting for login to complete after {args.timeout_seconds}s"
                )
        else:
            print("Please log in manually in the browser window.")
            print(
                "Once you are fully logged in and can see your Canvas dashboard, come back here and press Enter."
            )
            input()

        context.storage_state(path=str(SESSION_FILE))
        print(f"Session saved to {SESSION_FILE}")
        browser.close()


if __name__ == "__main__":
    main()

