# Satetoad

**Minimal TUI Widget Learning Framework**

A simplified version of the [Toad AI interface](https://github.com/batrachianai/toad) focusing on **visual widgets only** with minimal stub implementations. Perfect for learning Textual TUI patterns.

## Purpose

- Learn Textual widget patterns through clear, documented code
- Understand how a TUI app is structured (App → Screen → Widgets)
- Experiment with widgets without complex agent/protocol dependencies

## Quick Start

```bash
cd satetoad

# Install dependencies with uv
uv sync

# Run the app
make run
# or
uv run python -m satetoad
```

## Structure

```
src/satetoad/
├── app.py              # Main Textual App
├── main.tcss           # CSS styles
├── screens/main.py     # The ONE screen
├── widgets/            # All widget stubs
├── docs/               # Pattern documentation
└── examples/           # Mock data
```

## What's Inside

| Widget | Pattern Demonstrated |
|--------|---------------------|
| `conversation.py` | Composition, reactive vars |
| `prompt.py` | TextArea, Select dropdown |
| `sidebar.py` | Collapsible panels |
| `throbber.py` | Custom Visual render |
| `flash.py` | Timer-based visibility |

## Learning Path

1. Read `docs/ARCHITECTURE.md` - Understand the structure
2. Read `docs/WIDGET_PATTERNS.md` - Learn the patterns
3. Explore `widgets/` - See patterns in action
4. Read `docs/EXTENDING.md` - Add real functionality

## Relationship to Toad

This is a **teaching subset** of toad-reference. No ACP protocol, no agent communication - just the visual layer.

See `toad-reference/` for the full implementation.
