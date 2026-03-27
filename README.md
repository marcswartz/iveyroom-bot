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
