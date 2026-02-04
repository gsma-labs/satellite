# Satetoad Project Guidelines

## Project Overview

**Satetoad** is a Minimal TUI Widget Learning Framework - a simplified version of the Toad AI interface focused on visual widgets and UI/UX patterns. It serves dual purposes:

1. **Educational**: Teaching Textual widget patterns through clear, documented code
2. **Practical**: Open Telco Evaluation Suite for benchmarking LLMs on telecom tasks (TeleQnA, TeleTables, TeleLogs, TeleMath, 3GPP)

## Technology Stack

- **Python**: 3.13+
- **TUI Framework**: Textual 7.0.0+
- **Package Manager**: uv (always use uv, never raw python/pip)
- **Build System**: Hatchling
- **Linting/Formatting**: Ruff

## Directory Structure

```
src/satetoad/
├── app.py              # Entry point (SatetoadApp class)
├── main.tcss           # All CSS styles
├── screens/            # Screen implementations (MainScreen)
├── widgets/            # Reusable widget components
├── modals/             # Modal dialog implementations
├── examples/           # Mock data and sample data
└── docs/               # Architecture and pattern documentation
```

## Code Patterns

- **Single screen architecture**: Only MainScreen - simplifies learning
- **Modal-first interaction**: All options open as overlays
- **CSS-driven visibility**: Use CSS classes for state management
- **Hierarchical widget composition**: Mirrors Toad's architecture
- **Type-safe modal returns**: Use dataclasses (ModelConfig, SubmitData)
- **Mock backend**: No real API calls - focus on UI patterns

## Commands

```bash
uv sync              # Install dependencies
uv run make run      # Run the app
uv run make lint     # Lint code
uv run make format   # Format code
```

## Key Files

- `src/satetoad/app.py` - Main app entry point
- `src/satetoad/main.tcss` - All CSS styles
- `src/satetoad/docs/WIDGET_PATTERNS.md` - Pattern documentation (read before creating widgets)
- `src/satetoad/examples/eval_data.py` - Mock data

---

## Claude Behavior Rules

### Ask Questions First
Always ask multiple questions to clarify ambiguity before proceeding with implementation. Do not make assumptions.

### Use uv
Always use `uv` to run Python commands:
```bash
uv run python -m satetoad    # Not: python -m satetoad
uv add package               # Not: pip install package
```

### No Else Statements
Never use `else` statements. Use instead:
- Early returns
- Guard clauses
- Pattern matching (`match`/`case`)

```python
# Bad
def process(value):
    if value is None:
        return default
    else:
        return transform(value)

# Good
def process(value):
    if value is None:
        return default
    return transform(value)
```

### Leverage Subagents
Use subagents (Explore, Plan) to research codebase context. This preserves the context window and provides better results.

### Simplicity First
Prioritize clean, simple code over clever or complex solutions. Readability matters more than brevity.

### PEP Compliance
Follow PEP guidelines as top priority:
- PEP 8 (style)
- PEP 257 (docstrings)
- PEP 484 (type hints)

### Post-Change Cleanup
**Use the code-simplifier subagent** (from Anthropic's native Claude Code library) after making changes to ensure code quality. This agent simplifies and refines code for clarity, consistency, and maintainability while preserving functionality.

When to invoke:
- After completing a feature or bug fix
- After refactoring
- When code feels overly complex

```bash
# Invoke via Task tool with subagent_type="code-simplifier:code-simplifier"
```

### Constants & Naming Conventions
- **Avoid magic values**: Use framework constants instead of hardcoded values
- **ALL_CAPS for constants**: Use uppercase with underscores for constant names
- **Default factory naming**: Use `get_default_*` function names for default factories (e.g., `get_default_judge_prompt(game)`, `get_default_periodic_message(game)`)
- **Extract magic numbers**: Extract to named constants if they appear 3+ times OR if their meaning is unclear from context. Inline magic numbers in function defaults are acceptable if used once and obvious (e.g., `max_turns: int = 5`)

```python
# Good - clear constant
MAX_RETRY_ATTEMPTS = 3

# Good - default factory
def get_default_judge_prompt(game: str) -> str:
    return JUDGE_PROMPTS[game]

# Acceptable - obvious inline default
def run_game(max_turns: int = 5) -> None:
    ...
```

### Import Patterns
- **Use absolute imports**: Prefer absolute package imports for run-anywhere execution (e.g., `from inspect_evals.your_eval.dataset import get_dataset` instead of `from .dataset import get_dataset`). This ensures modules/tests run from IDEs and plugins executing from arbitrary working directories.
- **Exception**: Relative imports are fine for code that runs only in sandbox containers.
- **No import-time side effects**: Avoid code that executes on import
- **Handle optional dependencies gracefully**: Don't let missing optional dependencies crash imports

### Default Arguments
Require a good reason for having default values:
- **Appropriate for**: Top-level, user-facing code
- **Inappropriate for**: Lower-level helpers
- **Placement**: Defaults should live high in the call stack, not buried in implementation details

```python
# Good - default at top-level API
def run_evaluation(model: str, max_samples: int = 100) -> Report:
    return _run_evaluation_impl(model, max_samples)

# Bad - default buried in helper
def _run_evaluation_impl(model: str, max_samples: int = 100) -> Report:
    ...
```

### Code Hygiene
- **Remove dead code early**: Delete unused functions, classes, and members immediately rather than leaving them for "later cleanup"
- **No commented-out code**: Delete it; version control preserves history

### Error Handling
**Fail fast**: Only handle errors gracefully if you have a clear, justified reason. Otherwise, let them raise and crash. Failing fast is better than silently running broken code.

- Do not write try-catch blocks unless absolutely necessary
- Avoid swallowing exceptions with bare `except:` or `except Exception:`
- If catching, handle specifically and re-raise or log appropriately

```python
# Bad - hiding bugs
try:
    result = risky_operation()
except Exception:
    result = default_value  # Silent failure

# Good - fail fast
result = risky_operation()  # Let it crash if broken

# Acceptable - specific handling with good reason
try:
    config = load_config(path)
except FileNotFoundError:
    config = generate_default_config()  # Clear fallback behavior
```

### Comments
**Prefer fewer comments**. Comment **why** you're doing something, not **what** you're doing.

Before writing a comment describing *what* code does, consider:
- Naming functions more clearly
- Naming variables more clearly
- Separating logic into a well-named function
- Extracting an inline computation into a meaningfully named variable

**Avoid narrating changes**: Base comments on the code's current state, not the changes being made.

```python
# Bad - narrativising comments
# the function now does x instead of y
# changed x because of reason y

# Bad - describing what
# Loop through users and check if active
for user in users:
    if user.is_active:
        ...

# Good - explaining why
# Skip inactive users to avoid sending emails to closed accounts
for user in users:
    if not user.is_active:
        continue
    send_notification(user)
```

---

## Development Guidelines

1. Read `src/satetoad/docs/WIDGET_PATTERNS.md` before creating new widgets
2. New widgets go in `widgets/`, modals in `modals/`
3. Keep mock data in `examples/`
4. Follow existing patterns for consistency
5. Use TCSS for styling (not inline styles)
6. Type hints on all public functions and methods
7. Docstrings on all public classes and methods

---

## Type Safety

This project uses TypedDicts for structured data.

**Direct dict access for required keys**: Use `dict[key]` instead of `dict.get(key, fallback)` for keys marked as `Required` in TypedDicts. This ensures malformed data causes immediate failures rather than silent bugs.

```python
# Good - fails fast on malformed data
content = msg["content"]  # MessageDict.content is Required

# Bad - hides bugs with silent fallback
content = msg.get("content", "")
```

Reserve `.get()` for truly optional fields (those without `Required` in the TypedDict).

**Avoid redundant type annotations**: Don't add type annotations outside of function arguments when they're redundant and obvious from context.

```python
# Bad - redundant annotation
def do_something(age: int) -> str:
    name: str = "Foo"  # Type is obvious from the literal
    return f"{name} (age: {age})"

# Good - no redundant annotation
def do_something(age: int) -> str:
    name = "Foo"
    return f"{name} (age: {age})"
```

---

## Test Style

**Parameterize similar tests**: Always use `@pytest.mark.parametrize` with `pytest.param(..., id="descriptive_name")` when testing multiple inputs with the same logic. Extract shared setup into fixtures to reduce duplication.

```python
# Good - parameterized
@pytest.mark.parametrize(
    ("input", "expected"),
    [
        pytest.param(0, "zero", id="zero_case"),
        pytest.param(-1, "negative", id="negative_case"),
    ],
)
def test_something(self, input: int, expected: str) -> None:
    assert func(input) == expected

# Bad - duplicated test functions
def test_something_zero(self) -> None:
    assert func(0) == "zero"

def test_something_negative(self) -> None:
    assert func(-1) == "negative"
```

**Test critical behaviors**: Add unit tests for:
- Regex detection (including edge cases)
- Model fallback paths
- Loop/limit behavior (including no-limit scenarios)
