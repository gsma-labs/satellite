"""Test that banner size matches JuliaSet fractal dimensions.

These tests FAIL until the banner sizing bug is fixed.
The banner background should end where the fractal ends.

Bug description:
- The #title-grid banner has `height: auto` with `min-height: 8`
- The JuliaSet fractal has no explicit height constraint
- The #info Static text (6 lines) can force the grid taller than the fractal
- Result: banner background (#1E1F29) extends beyond the fractal area
"""

from unittest.mock import patch

import pytest

from satetoad.app import SatetoadApp
from satetoad.widgets.julia_set import JuliaSet


class TestBannerSizing:
    """Tests for banner and JuliaSet size consistency."""

    @pytest.mark.asyncio
    @patch.object(SatetoadApp, "_launch_inspect_view")
    async def test_banner_height_matches_julia_set_height(
        self, mock_launch: None
    ) -> None:
        """Banner height must equal JuliaSet height at all terminal sizes.

        FAILS while bug exists - banner and fractal have different heights.
        PASSES once fixed - banner ends where fractal ends.
        """
        test_sizes = [
            (60, 20),
            (80, 24),
            (100, 30),
            (120, 40),
        ]

        for width, height in test_sizes:
            app = SatetoadApp()
            async with app.run_test(size=(width, height)) as pilot:
                await pilot.pause()

                screen = app.screen
                title_grid = screen.query_one("#title-grid")
                julia_set = screen.query_one(JuliaSet)

                grid_h = title_grid.size.height
                julia_h = julia_set.size.height

                assert grid_h == julia_h, (
                    f"At terminal {width}x{height}: "
                    f"banner height ({grid_h}) != fractal height ({julia_h})"
                )

    @pytest.mark.asyncio
    @patch.object(SatetoadApp, "_launch_inspect_view")
    async def test_banner_has_fixed_height(self, mock_launch: None) -> None:
        """Banner must have fixed height regardless of terminal size.

        FAILS while bug exists - banner auto-expands with terminal.
        PASSES once fixed - banner stays constant height.
        """
        heights_at_sizes = []

        for width, height in [(80, 24), (80, 40), (80, 60)]:
            app = SatetoadApp()
            async with app.run_test(size=(width, height)) as pilot:
                await pilot.pause()

                screen = app.screen
                title_grid = screen.query_one("#title-grid")
                heights_at_sizes.append((height, title_grid.size.height))

        grid_heights = [h for _, h in heights_at_sizes]
        all_same = len(set(grid_heights)) == 1

        height_info = ", ".join(
            f"term_h={th}→grid_h={gh}" for th, gh in heights_at_sizes
        )
        assert all_same, f"Banner height varies with terminal size: {height_info}"
