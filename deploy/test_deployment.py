#!/usr/bin/env python3
"""Validate a live Satellite TUI deployment served via ttyd.

Connects to the deployment URL, waits for the ttyd terminal to render,
and verifies the Satellite TUI is visible (not a blank screen).

Usage:
    pip install playwright && playwright install chromium
    python deploy/test_deployment.py --url https://satellite-demo.fly.dev
"""

import argparse
import asyncio
import sys
from pathlib import Path

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
RENDER_TIMEOUT_MS = 30_000  # Max wait for TUI content to appear


async def validate(url: str) -> bool:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Install playwright: pip install playwright && playwright install chromium")
        sys.exit(1)

    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    ok = True

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        # --- Check 1: Page loads ---
        print(f"Connecting to {url} ...")
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        status = response.status if response else 0
        if status != 200:
            print(f"  FAIL: HTTP {status} (expected 200)")
            ok = False
        else:
            print(f"  OK: HTTP {status}")

        # --- Check 2: xterm.js terminal element appears ---
        print("Waiting for xterm terminal element ...")
        try:
            await page.wait_for_selector("div.xterm", timeout=RENDER_TIMEOUT_MS)
            print("  OK: xterm terminal element found")
        except Exception:
            print("  FAIL: xterm terminal element not found within timeout")
            ok = False

        # --- Check 3: Terminal contains visible text ---
        print("Waiting for TUI content to render ...")
        try:
            # ttyd renders terminal rows inside .xterm-rows; wait for
            # non-empty text content which indicates the TUI has painted.
            locator = page.locator(".xterm-rows")
            await locator.wait_for(state="visible", timeout=RENDER_TIMEOUT_MS)

            # Poll until the terminal has meaningful text content
            text = ""
            for _ in range(60):  # up to ~30s at 500ms intervals
                text = (await locator.inner_text()).strip()
                if len(text) > 10:
                    break
                await page.wait_for_timeout(500)

            if len(text) > 10:
                preview = text[:120].replace("\n", " ")
                print(f"  OK: Terminal has content ({len(text)} chars): {preview}...")
            else:
                print(f"  FAIL: Terminal appears blank (only {len(text)} chars)")
                ok = False
        except Exception as exc:
            print(f"  FAIL: Could not read terminal content: {exc}")
            ok = False

        # --- Screenshot ---
        shot = SCREENSHOTS_DIR / "deployment_validation.png"
        await page.screenshot(path=str(shot))
        print(f"  Screenshot saved: {shot}")

        await browser.close()

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Satellite TUI deployment")
    parser.add_argument(
        "--url",
        default="https://satellite-demo.fly.dev",
        help="Deployment URL to validate",
    )
    args = parser.parse_args()

    success = asyncio.run(validate(args.url))
    if success:
        print("\nVALIDATION PASSED")
        sys.exit(0)
    else:
        print("\nVALIDATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
