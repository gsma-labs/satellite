#!/usr/bin/env python3
"""Automated screenshot capture for Satellite TUI running in ttyd.

Connects to ttyd at localhost:8080, navigates via keyboard,
and captures screenshots to deploy/screenshots/.

Usage:
    pip install playwright && playwright install chromium
    python deploy/test_screenshots.py

Requires the Docker container to be running:
    docker run -p 8080:8080 -p 7575:7575 -e SATELLITE_VIEW_HOST=0.0.0.0 satellite-demo
"""

import asyncio
import sys
from pathlib import Path

TTYD_URL = "http://localhost:8080"
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
LOAD_WAIT_MS = 6000  # Wait for TUI to fully render after ttyd connects
KEY_DELAY_MS = 1500  # Pause between keystrokes for rendering


async def main() -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Install playwright: pip install playwright && playwright install chromium")
        sys.exit(1)

    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        print(f"Connecting to {TTYD_URL}...")
        await page.goto(TTYD_URL)
        await page.wait_for_timeout(LOAD_WAIT_MS)

        # 1. Main dashboard
        path = SCREENSHOTS_DIR / "01_main_dashboard.png"
        await page.screenshot(path=str(path))
        print(f"  Captured: {path.name}")

        # 2. Open Evals modal (press 1)
        await page.keyboard.press("1")
        await page.wait_for_timeout(KEY_DELAY_MS)
        path = SCREENSHOTS_DIR / "02_evals_modal.png"
        await page.screenshot(path=str(path))
        print(f"  Captured: {path.name}")

        # 3. Navigate to first job (down arrow + enter)
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(KEY_DELAY_MS)
        path = SCREENSHOTS_DIR / "03_job_detail.png"
        await page.screenshot(path=str(path))
        print(f"  Captured: {path.name}")

        # 4. Press 't' to trigger Check Traces
        await page.keyboard.press("t")
        await page.wait_for_timeout(KEY_DELAY_MS)
        path = SCREENSHOTS_DIR / "04_check_traces.png"
        await page.screenshot(path=str(path))
        print(f"  Captured: {path.name}")

        # 5. Close modals back to main screen (Escape x2)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(KEY_DELAY_MS)
        path = SCREENSHOTS_DIR / "05_back_to_main.png"
        await page.screenshot(path=str(path))
        print(f"  Captured: {path.name}")

        await browser.close()

    print(f"\nAll screenshots saved to {SCREENSHOTS_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
