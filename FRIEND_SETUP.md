## Friend setup (Mac, non-technical)

### What this bot does
- Books Ivey breakout rooms on Canvas (`learn.ivey.ca`) **14 days ahead**.
- Each time slot opens **exactly 14 days ahead by the hour**.
- The bot runs at your chosen hours (example: 3pm + 4pm) and tries to book:
  - Your preferred rooms first (in order)
  - Otherwise any available room

### 1) Download the folder
- Download the repo as a ZIP from GitHub and unzip it, or receive the folder from a friend.

### 2) Pick your booking times + room preferences
Open `config.json` and edit:
- `start_slots`: the hours you want to book (examples: `["3pm", "4pm"]`, `["5pm", "6pm"]`)
- `room_rankings`: your preferred room numbers (top = highest priority)

Tip: If you were sent a preset, just double-click the matching preset setup:
- `setup_friend_3pm_4pm.command`
- `setup_friend_5pm_6pm.command`

### 3) Run the one-time setup
Double-click:
- `setup_for_friend.command`

It will:
- install Python dependencies
- install Playwright’s Chromium browser
- open a browser so you can log into Canvas once (this creates `session.json`)
- install the scheduled jobs automatically

### 4) Verify it’s installed
Open Terminal and run:

```bash
launchctl list | grep -E "com\\.iveybot\\.(booker|catchup)"
```

You should see both:
- `com.iveybot.booker`
- `com.iveybot.catchup`

### If something breaks
- **Session expired / login issues**: run `python3 save_session.py` again, then `python3 install_scheduler.py`.
- **Not booking**: check logs in the folder:
  - `scheduler.log`
  - `catchup.log`
  - `log.txt`

