"""Julia set widget - interactive fractal display.

PATTERN DEMONSTRATED: Custom Rendering with render_line()

Key concepts:
- render_line() for line-by-line rendering
- Mouse click/hold for zooming
- Strip/Segment for low-level rendering
"""

from typing import NamedTuple

from rich.color import Color as RichColor
from rich.segment import Segment
from rich.style import Style as RichStyle

from textual import events
from textual.color import Color
from textual.geometry import Offset
from textual.reactive import reactive, var
from textual.strip import Strip
from textual.timer import Timer
from textual.widget import Widget


# Color gradient for Julia set (cool/electric theme - distinct from Mandelbrot)
# TODO: Customize this gradient to your preference!
# Consider: cool blues/greens, electric neons, or smooth earth tones
JULIA_COLORS: list[tuple[int, int, int]] = [
    # Default cool/electric gradient - feel free to replace!
    Color.parse(color).rgb
    for color in [
        "#0d0221",  # Deep purple/black
        "#0a4363",  # Dark blue
        "#0d7377",  # Teal
        "#14a087",  # Sea green
        "#32d697",  # Bright green
        "#7cf57c",  # Light green
        "#d4f77e",  # Yellow-green
        "#f5d962",  # Yellow
        "#f5a962",  # Orange
        "#f57962",  # Coral
        "#e94560",  # Pink-red
        "#9a0572",  # Magenta
    ]
]


class JuliaRegion(NamedTuple):
    """Defines the visible region of the Julia set (z-plane)."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def zoom(self, focal_x: float, focal_y: float, zoom_factor: float) -> "JuliaRegion":
        """Zoom in/out around a focal point."""
        width = self.x_max - self.x_min
        height = self.y_max - self.y_min

        new_width = width / zoom_factor
        new_height = height / zoom_factor

        fx = (focal_x - self.x_min) / width
        fy = (focal_y - self.y_min) / height

        new_x_min = focal_x - fx * new_width
        new_x_max = focal_x + (1 - fx) * new_width
        new_y_min = focal_y - fy * new_height
        new_y_max = focal_y + (1 - fy) * new_height

        return JuliaRegion(new_x_min, new_x_max, new_y_min, new_y_max)


class JuliaSet(Widget):
    """Interactive Julia set fractal widget.

    PATTERN: Custom line rendering

    The Julia set uses the same iteration as Mandelbrot (z = z² + c), but:
    - z starts at each pixel's coordinates
    - c is a fixed constant (dense spiral pattern)

    Click to zoom in, Ctrl+click to zoom out!
    """

    ALLOW_SELECT = False
    DEFAULT_CSS = """
    JuliaSet {
        text-wrap: nowrap;
        text-overflow: clip;
        overflow: hidden;
    }
    """

    # Reactive properties trigger re-render when changed
    set_region = reactive(JuliaRegion(-1.0, 1.0, -1.0, 1.0), init=False)
    c_parameter = reactive(complex(-0.4, 0.6), init=False)  # Dense spiral Julia set
    max_iterations = var(64)
    zoom_position = var(Offset(0, 0))
    zoom_timer: var[Timer | None] = var(None)
    zoom_scale = var(0.99)

    # Braille characters for high-resolution rendering (2x4 sub-pixels per cell)
    BRAILLE_CHARACTERS = [chr(0x2800 + i) for i in range(256)]

    # Bit positions for braille dots
    PATCH_COORDS = [
        (1, 0, 0),
        (2, 0, 1),
        (4, 0, 2),
        (8, 1, 0),
        (16, 1, 1),
        (32, 1, 2),
        (64, 0, 3),
        (128, 1, 3),
    ]

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self._strip_cache: dict[int, Strip] = {}
        super().__init__(name=name, id=id, classes=classes)

    @staticmethod
    def julia(z_real: float, z_imag: float, c_real: float, c_imag: float, max_iterations: int) -> int:
        """Calculate iterations for a point in the Julia set.

        Unlike Mandelbrot where z=0 and c=pixel:
        - z starts at pixel position
        - c is a fixed constant
        """
        for i in range(max_iterations):
            z_real_new = z_real * z_real - z_imag * z_imag + c_real
            z_imag_new = 2 * z_real * z_imag + c_imag
            z_real = z_real_new
            z_imag = z_imag_new
            if z_real * z_real + z_imag * z_imag > 4:
                return i
        return max_iterations

    def on_mount(self) -> None:
        """Refresh after mounting."""
        self.call_after_refresh(self.refresh)

    def on_resize(self) -> None:
        """Clear cache when resized."""
        self._strip_cache.clear()

    def on_mouse_down(self, event: events.Click) -> None:
        """Start zooming on mouse down.

        PATTERN: Mouse capture for smooth zooming
        - capture_mouse() to receive events outside widget
        """
        if self.zoom_timer:
            self.zoom_timer.stop()
        self.zoom_position = event.offset
        # Ctrl+click zooms out, regular click zooms in
        self.zoom_scale = 0.95 if event.ctrl else 1.05
        self.zoom_timer = self.set_interval(1 / 20, self.zoom)
        self.capture_mouse()

    def on_mouse_up(self, event: events.Click) -> None:
        """Stop zooming on mouse up."""
        self.release_mouse()
        if self.zoom_timer:
            self.zoom_timer.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Track mouse position for zoom center."""
        self.zoom_position = event.offset

    def zoom(self) -> None:
        """Perform one zoom step."""
        zoom_x, zoom_y = self.zoom_position
        width, height = self.content_size
        x_min, x_max, y_min, y_max = self.set_region

        set_width = x_max - x_min
        set_height = y_max - y_min

        x = x_min + (zoom_x / width) * set_width
        y = y_min + (zoom_y / height) * set_height

        self.set_region = self.set_region.zoom(x, y, self.zoom_scale)

    def watch_set_region(self) -> None:
        """Clear cache when region changes."""
        self._strip_cache.clear()
        self.refresh()

    def watch_c_parameter(self) -> None:
        """Clear cache when c parameter changes."""
        self._strip_cache.clear()
        self.refresh()

    def render_line(self, y: int) -> Strip:
        """Render a single line of the fractal.

        PATTERN: Custom line rendering with caching
        - Returns a Strip containing Segments
        - Uses braille characters for 2x4 resolution
        - Colors based on iteration count
        """
        if (cached_line := self._strip_cache.get(y)) is not None:
            return cached_line

        width, height = self.content_size
        x_min, x_max, y_min, y_max = self.set_region
        julia_width = x_max - x_min
        julia_height = y_max - y_min

        julia = self.julia
        max_iterations = self.max_iterations
        c_real = self.c_parameter.real
        c_imag = self.c_parameter.imag
        set_width = width * 2
        set_height = height * 4
        max_color = len(JULIA_COLORS) - 1

        row = y * 4
        colors: list[tuple[int, int, int]] = []
        segments: list[Segment] = []
        base_style = self.rich_style

        for column in range(0, width * 2, 2):
            braille_key = 0
            for bit, dot_x, dot_y in self.PATCH_COORDS:
                patch_x = column + dot_x
                patch_y = row + dot_y
                # z starts at pixel position (unlike Mandelbrot where z=0)
                z_real = x_min + julia_width * patch_x / set_width
                z_imag = y_min + julia_height * patch_y / set_height
                iterations = julia(z_real, z_imag, c_real, c_imag, max_iterations)
                if iterations < max_iterations:
                    braille_key |= bit
                    colors.append(JULIA_COLORS[round((iterations / max_iterations) * max_color)])

            if not colors:
                segments.append(Segment(" ", base_style))
                continue

            patch_red = sum(c[0] for c in colors) // len(colors)
            patch_green = sum(c[1] for c in colors) // len(colors)
            patch_blue = sum(c[2] for c in colors) // len(colors)
            patch_color = RichColor.from_rgb(patch_red, patch_green, patch_blue)
            segments.append(
                Segment(
                    self.BRAILLE_CHARACTERS[braille_key],
                    base_style + RichStyle.from_color(patch_color),
                )
            )
            colors.clear()

        strip = Strip(segments, cell_length=width)
        self._strip_cache[y] = strip
        return strip


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    class JuliaSetApp(App):
        """Standalone app for testing JuliaSet widget."""

        CSS = """
        Screen {
            align: center middle;
            background: $surface;
        }
        JuliaSet {
            width: 60;
            height: 20;
        }
        """

        def compose(self) -> ComposeResult:
            yield JuliaSet()

    JuliaSetApp().run()
