#!/usr/bin/env python3
"""Capture screenshots of satellite screens and widgets.

This script runs Textual apps in headless mode and captures SVG screenshots,
then converts them to PNG format for documentation.

Usage:
    uv run python scripts/capture_screenshots.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Static

# Import satellite components
from satellite.app import SatelliteApp
from satellite.screens.main import MainScreen
from satellite.screens.trajectories import TrajectoriesScreen
from satellite.widgets.eval_box import EvalBox
from satellite.widgets.eval_list import EvalList, EvalListItem


# Output directory
DOCS_DIR = Path(__file__).parent.parent / "docs"
WIDGETS_DIR = DOCS_DIR / "widgets"


def svg_to_png(svg_path: Path, png_path: Path, scale: int = 2) -> bool:
    """Convert SVG to PNG using available converters.

    Tries in order:
    1. cairosvg (requires libcairo native library)
    2. svglib + reportlab (pure Python)
    3. Fallback to keeping SVG
    """
    # Try cairosvg first (fastest, best quality)
    try:
        import cairosvg
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), scale=scale)
        svg_path.unlink()
        return True
    except ImportError:
        pass
    except OSError as e:
        if "no library called" in str(e):
            print("  Note: cairosvg requires libcairo. Install with: brew install cairo")
        else:
            raise

    # Try svglib + reportlab (pure Python fallback)
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM

        drawing = svg2rlg(str(svg_path))
        if drawing:
            renderPM.drawToFile(drawing, str(png_path), fmt="PNG")
            svg_path.unlink()
            return True
    except ImportError:
        pass
    except Exception as e:
        print(f"  svglib conversion failed: {e}")

    # Keep SVG as fallback
    print(f"  SVG saved: {svg_path.name}")
    print("  Convert to PNG with: inkscape --export-type=png {svg_path}")
    return False


class WidgetShowcase(App):
    """Generic app for showcasing a single widget."""

    CSS = """
    Screen {
        align: center middle;
        background: #1a1a2e;
    }
    #showcase-container {
        width: auto;
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, widget_factory, css_override: str = ""):
        super().__init__()
        self._widget_factory = widget_factory
        if css_override:
            self.CSS = self.CSS + css_override

    def compose(self) -> ComposeResult:
        with Container(id="showcase-container"):
            yield self._widget_factory()


async def capture_screenshot(
    app: App,
    output_name: str,
    size: tuple[int, int] = (100, 30),
    press_keys: list[str] | None = None,
) -> Path:
    """Run an app in test mode and capture a screenshot."""
    svg_path = DOCS_DIR / f"{output_name}.svg"
    png_path = DOCS_DIR / f"{output_name}.png"

    async with app.run_test(size=size) as pilot:
        # Simulate key presses if needed
        if press_keys:
            for key in press_keys:
                await pilot.press(key)
                await pilot.pause()

        # Give app time to render
        await pilot.pause()

        # Export screenshot - Textual's export_screenshot returns SVG string
        svg_content = app.export_screenshot()

        # Write SVG to file
        svg_path.write_text(svg_content)
        print(f"  Captured: {svg_path.name}")

        # Convert to PNG
        if svg_to_png(svg_path, png_path):
            print(f"  Converted: {png_path.name}")
            return png_path
        return svg_path


async def capture_widget(
    widget_factory,
    output_name: str,
    size: tuple[int, int] = (50, 20),
    css_override: str = "",
) -> Path:
    """Capture a single widget in isolation."""
    app = WidgetShowcase(widget_factory, css_override)
    output_path = WIDGETS_DIR / output_name

    # Adjust paths for widget screenshots
    svg_path = WIDGETS_DIR / f"{output_name}.svg"
    png_path = WIDGETS_DIR / f"{output_name}.png"

    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        svg_content = app.export_screenshot()
        svg_path.write_text(svg_content)
        print(f"  Captured: widgets/{svg_path.name}")

        if svg_to_png(svg_path, png_path):
            print(f"  Converted: widgets/{png_path.name}")
            return png_path
        return svg_path


async def main():
    """Capture all screenshots."""
    print("=" * 50)
    print("Satellite Screenshot Capture")
    print("=" * 50)

    # Ensure directories exist
    DOCS_DIR.mkdir(exist_ok=True)
    WIDGETS_DIR.mkdir(exist_ok=True)

    # 1. Main Screen (default view with boxes)
    print("\n[1/3] Capturing MainScreen (boxes view)...")
    await capture_screenshot(
        SatelliteApp(),
        "main-screen",
        size=(100, 35),
    )

    # 2. Main Screen with Run Evals panel
    print("\n[2/3] Capturing MainScreen (evals panel)...")
    await capture_screenshot(
        SatelliteApp(),
        "main-screen-evals-panel",
        size=(100, 35),
        press_keys=["2"],  # Press 2 to go to Run Evals
    )

    # 3. Main Screen with Leaderboard panel
    print("\n[3/3] Capturing MainScreen (leaderboard panel)...")
    await capture_screenshot(
        SatelliteApp(),
        "main-screen-leaderboard",
        size=(100, 35),
        press_keys=["3"],  # Press 3 to go to Leaderboard
    )

    print("\n" + "=" * 50)
    print("Screenshot capture complete!")
    print(f"Output directory: {DOCS_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
