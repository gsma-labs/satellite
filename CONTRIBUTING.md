# Contributing to Satellite

Thank you for your interest in contributing to Satellite! This guide covers everything you need to get started.

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package manager)

### Setup

```bash
git clone https://github.com/gsma-labs/satellite.git
cd satellite
make setup
```

### Run the app

```bash
uv run satellite
```

## Development Workflow

| Command          | Description               |
|------------------|---------------------------|
| `make test`      | Run all tests             |
| `make lint`      | Lint with Ruff            |
| `make format`    | Auto-format with Ruff     |
| `make check`     | Verify core imports work  |
| `make run`       | Launch the TUI            |

Always use `uv` to run Python commands:

```bash
uv run python -m satellite    # Not: python -m satellite
uv add package               # Not: pip install package
```

## Project Structure

```
src/satellite/
├── app.py              # Entry point (SatelliteApp class)
├── main.tcss           # All CSS styles
├── screens/            # Screen implementations (MainScreen)
├── widgets/            # Reusable widget components
├── modals/             # Modal dialog implementations
├── examples/           # Mock data and sample data
└── docs/               # Architecture and pattern documentation
```

- New widgets go in `widgets/`, modals in `modals/`
- Keep mock data in `examples/`
- Use TCSS for styling (not inline styles)
- Read `src/satellite/docs/WIDGET_PATTERNS.md` before creating new widgets

## Code Style

### No `else` Statements

Use early returns, guard clauses, or pattern matching instead:

```python
# Good
def process(value):
    if value is None:
        return default
    return transform(value)
```

### Clean at the Source

Functions should return clean, ready-to-use values. Never force consumers to strip prefixes, decode formats, or work around dirty data.

```python
# Good - clean at the source
def extract_accuracy(log) -> tuple[str, str, float]:
    task_id = log.eval.task.rsplit("/", 1)[-1]
    return (log.eval.model, task_id, accuracy)
```

### Naming Conventions

- Variable names should answer "what is this?" at a glance
- Max two words (one underscore), natural English order
- Name the content, not the container
- Use `ALL_CAPS` for constants
- Use `get_default_*` for default factory functions

### Expand Clever One-Liners

Each concept gets its own scannable line. Named intermediates serve as inline documentation:

```python
# Good
def score_rank(entry):
    no_score = entry.tci is None
    descending = -(entry.tci or 0)
    return (no_score, descending)
```

### Extract Predicate Helpers

When an `if` condition inspects widget/object properties, extract it into a named `_is_*` method:

```python
def _is_close_button(self, widget) -> bool:
    return getattr(widget, "id", None) == "close-x"
```

### One Concept per Method

When a method does two distinct things, split into focused helpers. The parent method becomes a readable outline.

### Comments

Prefer fewer comments. Comment **why**, not **what**. Before writing a comment, consider naming functions or variables more clearly instead.

### Error Handling

Fail fast. Only handle errors gracefully if you have a clear, justified reason. Avoid bare `except:` or `except Exception:`.

```python
# Good - fail fast
result = risky_operation()

# Acceptable - specific handling with good reason
try:
    config = load_config(path)
except FileNotFoundError:
    config = generate_default_config()
```

### Import Patterns

- Use absolute imports for run-anywhere execution
- No import-time side effects
- Handle optional dependencies gracefully

## Type Safety

- Type hints on all public functions and methods
- Docstrings on all public classes and methods
- Use `dict[key]` for required TypedDict keys (fail fast), `.get()` for truly optional fields
- Avoid redundant type annotations obvious from context

## Test Style

### Parameterize Similar Tests

Use `@pytest.mark.parametrize` with `pytest.param(..., id="descriptive_name")`:

```python
@pytest.mark.parametrize(
    ("input", "expected"),
    [
        pytest.param(0, "zero", id="zero_case"),
        pytest.param(-1, "negative", id="negative_case"),
    ],
)
def test_something(self, input: int, expected: str) -> None:
    assert func(input) == expected
```

### Test Critical Behaviors

Add unit tests for:
- Regex detection (including edge cases)
- Model fallback paths
- Loop/limit behavior (including no-limit scenarios)

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes following the style guidelines above
3. Ensure `make lint` and `make test` pass
4. Submit a PR with a clear description of the change and motivation
5. CI will run lint and tests automatically

## License

By contributing to Satellite, you agree that your contributions will be licensed under the [GPL-3.0-or-later](LICENSE) license.
