"""Open the deployed dashboard in a headless browser so the host sees real traffic.

Streamlit Community Cloud only counts a live browser session (websocket) as
activity, and an already-sleeping app needs its wake button clicked. A plain
HTTP request is not enough there, which is why this uses Playwright.

Usage: APP_URL=https://your-app.example python scripts/keepalive.py
"""

import os
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "").strip()
if not URL:
    sys.exit("APP_URL is not set. Add it as a repository variable named APP_URL.")

# Wake buttons used by the common free hosts.
WAKE_BUTTONS = [
    "Yes, get this app back up!",  # Streamlit Community Cloud
    "Restart this Space",          # Hugging Face Spaces
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
    except PlaywrightTimeout:
        print("Page was slow to respond (host may be cold-starting); continuing.")

    woke = False
    for label in WAKE_BUTTONS:
        button = page.get_by_role("button", name=label)
        if button.count():
            button.first.click()
            print(f"App was asleep: clicked '{label}'.")
            woke = True
            break

    # Keep the session open long enough to register as a visit
    # (or, after a wake click, long enough for the app to boot).
    page.wait_for_timeout(120_000 if woke else 30_000)
    if not woke:
        print("App is awake.")
    browser.close()
