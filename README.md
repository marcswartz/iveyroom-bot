# Ivey Breakout Rooms Booking Bot

This project automates booking study rooms on `learn.ivey.ca` using Playwright.

## Files
- `book_room.py`: books 14-days-ahead slots using your room ranking.
- `catchup.py`: retries missed slots based on logs.
- `save_session.py`: one-time login that creates `session.json`.
- `install_scheduler.py`: installs/loads launchd schedules from `config.json`.
- `setup_for_friend.command`: one-click setup flow for non-technical users.
- `config.json`: customize slots + room ranking + python path.
- `log.txt`, `state.json`, `scheduler.log`, `catchup.log`: runtime output/state.

## Friend Setup (Mac)
1. Share this folder.
2. Open `config.json` and set:
   - `start_slots` (example: `["3pm", "4pm"]`)
   - `room_rankings` (room preference order)
3. Double-click `setup_for_friend.command`.
   - This installs dependencies + browser
   - Opens login once to create `session.json`
   - Installs scheduler jobs automatically
4. Optional: follow `FRIEND_SETUP.md` for a step-by-step checklist.

### Preset setups (one-click)
- `setup_friend_3pm_4pm.command` → applies `3pm/4pm` preset, then runs setup.
- `setup_friend_5pm_6pm.command` → applies `5pm/6pm` preset, then runs setup.

## Running
- Manual run by slot:
  - `python3 book_room.py --start-slot 1pm`
  - `python3 book_room.py --start-slot 2pm`
- Catchup run:
  - `python3 catchup.py`

## Updating schedule after config changes
If `config.json` changes, run:
`python3 install_scheduler.py`

## Scheduler behavior (important)
`install_scheduler.py` registers **one** launchd job that runs at **each** hour in `start_slots` (e.g. 1pm and 2pm), at **one minute past** that hour (`13:01`, `14:01`, …) so the grid is usually unlocked. Each run must book **that** hour’s slot. The bot picks the slot by matching the **current clock hour** to your configured `start_slots` (so the 2pm run books `2pm`, not `1pm` again).

**Catchup** runs at **:05** past every hour from the **earliest** configured slot through **11:05 PM** the same day. If the Mac was asleep through 1:01 / 2:01, the next catchup while you’re awake can still run `book_room.py --start-slot …` for any slot that has not already logged `SUCCESS` today.
