# How to Make a Video Demo of Satellite

Record scripted terminal demos using [VHS by Charmbracelet](https://github.com/charmbracelet/vhs). VHS reads a `.tape` file that declares terminal interactions, then renders them into GIF, MP4, or WebM.

## Prerequisites

```bash
brew install vhs
```

This installs VHS along with its dependencies (`ffmpeg`, `ttyd`).

Verify the installation:

```bash
vhs --version
which ffmpeg
which ttyd
```

## Quick Start

```bash
vhs scripts/demo.tape
```

This generates:
- `docs/demo.gif` (1400x850, for README/GitHub)
- `docs/demo.mp4` (higher quality, for sharing)

## How VHS Works

VHS launches a headless virtual terminal (`ttyd`), executes your scripted commands, captures every frame, and encodes the output with `ffmpeg`. No window pops up during recording — it runs entirely in the background.

```
demo.tape  →  VHS  →  ttyd (virtual terminal)  →  ffmpeg  →  demo.gif / demo.mp4
```

## Tape File Structure

The tape file lives at `scripts/demo.tape`. It has three sections:

### 1. Output and Appearance

```tape
Output docs/demo.gif
Output docs/demo.mp4

Set Shell "zsh"
Set FontSize 14
Set FontFamily "JetBrains Mono"
Set Width 1400
Set Height 850
Set Framerate 24
Set PlaybackSpeed 0.8
Set TypingSpeed 60ms
Set Padding 12
Set WindowBar Colorful
Set WindowBarSize 40
Set Theme "Dracula"
```

| Setting | What It Controls | Our Value |
|---------|-----------------|-----------|
| `Output` | Output file path and format (multiple allowed) | GIF + MP4 |
| `Set Shell` | Shell used in virtual terminal | `zsh` |
| `Set FontSize` | Font size in pixels | `14` |
| `Set FontFamily` | Font face (must be installed on system) | `JetBrains Mono` |
| `Set Width` / `Set Height` | Virtual terminal dimensions in pixels | `1400 x 850` |
| `Set Framerate` | Frames per second | `24` |
| `Set PlaybackSpeed` | Playback multiplier (0.5 = half speed) | `0.8` |
| `Set TypingSpeed` | Default delay between keystrokes | `60ms` |
| `Set Padding` | Padding around terminal content | `12` |
| `Set WindowBar` | Window chrome style (`Colorful`, `Rings`, `None`) | `Colorful` |
| `Set Theme` | Terminal color theme | `Dracula` |

### 2. Setup (Hidden)

Use `Hide` / `Show` to run setup commands without showing them in the recording:

```tape
Hide
Type "cd /path/to/satellite"
Enter
Sleep 500ms
Show
```

### 3. Scripted Interactions

```tape
Type "uv run python -m satellite"
Enter
Sleep 4s

Type "1"
Sleep 2s

Down
Sleep 500ms
Space
Sleep 1s

Escape
Sleep 2s
```

## Tape Command Reference

### Typing

| Command | Description | Example |
|---------|-------------|---------|
| `Type "text"` | Type text at default speed | `Type "hello"` |
| `Type@100ms "text"` | Type text at custom speed | `Type@100ms "GPT-4o"` |

### Keys

| Command | Description |
|---------|-------------|
| `Enter` | Press Enter |
| `Escape` | Press Escape |
| `Space` | Press Space |
| `Tab` | Press Tab |
| `Up` / `Down` / `Left` / `Right` | Arrow keys |
| `Backspace` | Press Backspace |
| `Ctrl+C` | Ctrl key combinations |

### Timing

| Command | Description | Example |
|---------|-------------|---------|
| `Sleep 2s` | Pause for duration | `Sleep 500ms`, `Sleep 3s` |

### Visibility

| Command | Description |
|---------|-------------|
| `Hide` | Stop recording frames (commands still execute) |
| `Show` | Resume recording frames |
| `Screenshot` | Capture a single PNG frame |

### Utilities

| Command | Description | Example |
|---------|-------------|---------|
| `Require` | Assert a binary exists before running | `Require uv` |
| `Env KEY value` | Set environment variable | `Env TERM xterm-256color` |
| `Source file.tape` | Include another tape file | `Source setup.tape` |

## Editing the Demo

### Adjusting Timing

If modals appear too fast or slow in the recording, change the `Sleep` after opening them:

```tape
# Too fast — viewer can't read the modal
Type "1"
Sleep 1s

# Better — give 2-3 seconds for complex modals
Type "1"
Sleep 3s
```

### Adding a New Section

To demo a new feature, add a block between existing sections:

```tape
# ─── Your new section ────────────────────────
Type "5"          # Open Cloud APIs modal
Sleep 2s

Tab               # Navigate form
Sleep 500ms
Type@100ms "aws-bedrock/claude-3"
Sleep 2s

Escape            # Close modal
Sleep 2s
```

### Changing Output Format

Add or remove `Output` lines at the top:

```tape
Output docs/demo.gif          # Animated GIF
Output docs/demo.mp4          # MP4 video
Output docs/demo.webm         # WebM video
```

### Changing Terminal Size

Match the terminal size to your app's layout. If content gets clipped or has too much whitespace:

```tape
Set Width 1200    # Narrower
Set Height 700    # Shorter
```

## Publishing and Sharing

### Embed in README

```markdown
![Satellite Demo](docs/demo.gif)
```

### Upload to vhs.charm.sh

```bash
vhs publish docs/demo.gif
```

Returns a shareable URL hosted by Charmbracelet.

### Convert to Other Formats

```bash
# GIF to optimized GIF (smaller file)
ffmpeg -i docs/demo.gif -vf "fps=15,scale=800:-1,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" docs/demo-small.gif

# MP4 to WebM
ffmpeg -i docs/demo.mp4 -c:v libvpx-vp9 -crf 30 docs/demo.webm
```

## Limitations

VHS runs in a virtual terminal, which means:

- **No mouse support** — only keyboard interactions can be scripted
- **Rendering differences** — the virtual terminal may render slightly differently from your actual terminal emulator (font rendering, spacing)
- **No audio** — VHS captures video only
- **Timing is approximate** — Textual modals may load faster or slower in the virtual terminal vs real usage; tune `Sleep` durations after a test run

## Alternatives for Mouse-Driven Demos

If you need to show mouse clicks, hover effects, or scrolling:

| Tool | Install | Output | Notes |
|------|---------|--------|-------|
| **Cmd+Shift+5** | Built-in macOS | MOV | Zero setup, captures everything |
| **Kap** | `brew install --cask kap` | GIF/MP4/WebM | Lightweight, direct GIF export |
| **OBS Studio** | `brew install --cask obs` | MKV/MP4 | Professional, webcam overlay |

Convert screen recordings to GIF:

```bash
ffmpeg -i recording.mov -vf "fps=15,scale=800:-1,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" output.gif
```
