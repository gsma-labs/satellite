# Option 2: Evals Container with Job Progress Tracking

This document describes the implementation of the "Evals" feature in Satellite, which transforms the simple "Run Evals" box into a full job management system with persistent storage and a **unified tabbed interface**.

## Overview

The "Evals" box now opens a **single tabbed modal** with browser-style tabs:
1. **Run Evals** tab - Select and run benchmarks (creates a job)
2. **View Progress** tab - Monitor running/completed jobs
3. **Dynamic Job Detail tabs** - Opens when selecting a job (closable)

Jobs are persisted to disk and survive app restarts.

---

## Architecture

### Design Decision: Tabbed Modal Approach

We chose a **single tabbed modal** over sequential modals because:
- **Single interaction point** - All evals functionality in one place
- **Instant switching** - No modal stack to navigate
- **State preservation** - Selected benchmarks persist when switching tabs
- **Browser-familiar UX** - Tabs work like Chrome tabs (closable job detail tabs)

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  [*Run Evals*] │ [View Progress] │ [job_1] [x] │            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Content area changes based on selected tab                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Per-tab buttons (Cancel/Run Selected OR Close)             │
└─────────────────────────────────────────────────────────────┘
```

### Tab 1: Run Evals (selected)
```
┌─────────────────────────────────────────────────────────────┐
│  [*Run Evals*] │ [View Progress]                            │
├─────────────────────────────────────────────────────────────┤
│  Model: openai/gpt-4o                                       │
│                                                             │
│  Select benchmarks to run:                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ ► ● TeleQnA                                         │    │
│  │   ○ TeleTables                                      │    │
│  │   ● TeleLogs                                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  [Select All] [Clear All]                                   │
├─────────────────────────────────────────────────────────────┤
│              [Cancel]  [Run Selected]                       │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
                Creates Job
                    ▼
            ┌──────────────┐
            │ JobManager   │
            │ Persists to  │
            │ disk         │
            └──────────────┘
```

### Tab 2: View Progress (selected)
```
┌─────────────────────────────────────────────────────────────┐
│  [Run Evals] │ [*View Progress*]                            │
├─────────────────────────────────────────────────────────────┤
│  ● job_1   TeleQnA, TeleLogs          Completed             │
│  ○ job_2   TeleMath                   Pending               │
│  ✕ job_3   3GPP                       Failed                │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                        [Close]                              │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼ (click job)
            Opens dynamic tab
```

### Tab 3+: Job Detail (dynamic, closable)
```
┌─────────────────────────────────────────────────────────────┐
│  [Run Evals] │ [View Progress] │ [*job_1*] [x]              │
├─────────────────────────────────────────────────────────────┤
│  Status: ● Completed                                        │
│  Created: 2026-02-03 14:30:52                               │
│  Model: openai/gpt-4o                                       │
│                                                             │
│  Benchmarks:                                                │
│  • TeleQnA                                                  │
│  • TeleLogs                                                 │
│                                                             │
│  Results:                                                   │
│  • TeleQnA: 0.85                                            │
│  • TeleLogs: 0.78                                           │
├─────────────────────────────────────────────────────────────┤
│                     [Close Tab]                             │
└─────────────────────────────────────────────────────────────┘
```

---

## New Files Created

### Tab Widgets

#### `src/satellite/widgets/tab_item.py`
Single clickable tab in the header row, following the `EvalsOptionItem` pattern.

```python
class TabItem(HorizontalGroup):
    """Single clickable tab in the header row."""

    class Activated(Message):
        """Posted when this tab is clicked/activated."""
        def __init__(self, tab_id: str) -> None:
            self.tab_id = tab_id

    class CloseRequested(Message):
        """Posted when close button is clicked on a closable tab."""
        def __init__(self, tab_id: str) -> None:
            self.tab_id = tab_id

    active: reactive[bool] = reactive(False)

    def __init__(self, label: str, tab_id: str, closable: bool = False):
        ...
```

**Features:**
- Label + optional close button (for dynamic tabs)
- `active` reactive property for styling
- Click posts `Activated` message
- Close button posts `CloseRequested` message
- Keyboard: Enter activates, Delete/Backspace closes

**CSS Classes:**
- `-active` - Currently selected tab (purple border, highlighted background)
- `-closable` - Shows close button

#### `src/satellite/widgets/tab_header.py`
Horizontal container managing multiple TabItem widgets with keyboard navigation.

```python
class TabHeader(Horizontal):
    """Horizontal container holding TabItem widgets."""

    class TabChanged(Message):
        """Posted when active tab changes."""
        def __init__(self, old_tab_id: str | None, new_tab_id: str) -> None:
            ...

    class TabClosed(Message):
        """Posted when a closable tab is closed."""
        def __init__(self, tab_id: str) -> None:
            ...

    active_tab: reactive[str | None] = reactive(None)

    def add_tab(self, tab_id: str, label: str, closable: bool = False, activate: bool = True) -> TabItem:
        ...

    def remove_tab(self, tab_id: str) -> bool:
        ...

    def activate_tab(self, tab_id: str) -> bool:
        ...
```

**Keyboard Bindings:**
- `Left/Right` arrows - Navigate between tabs
- `1/2/3` number keys - Jump to tab by index

---

### Tabbed Modal

#### `src/satellite/modals/tabbed_evals_modal.py`
Unified modal combining all evals functionality.

```python
class TabbedEvalsModal(ModalScreen[Job | None]):
    """Unified tabbed modal for evaluation workflows."""

    active_tab: reactive[str] = reactive("run-evals")

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        job_manager: JobManager | None = None,
    ) -> None:
        ...
```

**Structure:**
```
TabbedEvalsModal
├── TabHeader (tab navigation)
│   ├── TabItem ("Run Evals", static)
│   ├── TabItem ("View Progress", static)
│   └── TabItem ("job_X", dynamic, closable)
├── #tab-content (Vertical container)
│   ├── RunEvalsContent (.tab-pane, shown when active)
│   ├── JobListContent (.tab-pane, hidden)
│   └── JobDetailContent (dynamic, hidden)
└── Button rows (visibility controlled by CSS)
    ├── #run-evals-buttons
    ├── #view-progress-buttons
    └── #job-detail-buttons
```

**Content Widgets (extracted from original modals):**

| Widget | Source | Purpose | Message |
|--------|--------|---------|---------|
| `RunEvalsContent` | `run_evals_modal.py` | Benchmark selection | `RunRequested(benchmarks)` |
| `JobListContent` | `job_list_modal.py` | Job list with navigation | `JobSelected(job_id)` |
| `JobDetailContent` | `job_detail_modal.py` | Job details display | (display only) |

**State Management:**
```python
# Preserved across tab switches
_run_evals_selected: set[str] | None = None  # Selected benchmarks
_open_job_tabs: dict[str, str] = {}          # job_id → tab_id mapping
```

**Tab Switching Logic:**
1. Save current tab state before switching
2. Update CSS classes on modal for button visibility
3. Toggle `-active` class on tab panes
4. Restore target tab state

---

### Models (unchanged)

#### `src/satellite/models/job.py`
Job dataclass with:
- `id`: Unique identifier (e.g., "job_1")
- `benchmarks`: List of benchmark IDs
- `model_provider`, `model_name`: Model configuration
- `status`: JobStatus enum (PENDING, RUNNING, COMPLETED, FAILED)
- `created_at`, `completed_at`: Timestamps
- `results`: Dict of benchmark_id → score
- `error`: Error message if failed

---

### Services (unchanged)

#### `src/satellite/services/job_manager.py`
Manages job persistence using XDG-compliant directories:

**Storage Location:**
- macOS: `~/Library/Application Support/satellite/jobs/`
- Linux: `~/.local/share/satellite/jobs/`
- Windows: `C:/Users/<user>/AppData/Local/satellite/jobs/`

**Methods:**
- `create_job(benchmarks, model_provider, model_name)` → Job
- `get_job(job_id)` → Job | None
- `list_jobs(limit)` → list[Job]
- `mark_job_running(job_id)` → Job
- `mark_job_completed(job_id, results)` → Job
- `mark_job_failed(job_id, error)` → Job

---

## Modified Files

### `src/satellite/screens/main.py`

**Simplified flow** - now just pushes TabbedEvalsModal:

```python
from satellite.modals.tabbed_evals_modal import TabbedEvalsModal

def _show_evals_modal(self) -> None:
    """Push the TabbedEvalsModal for running evals and viewing progress."""
    self.app.push_screen(
        TabbedEvalsModal(
            model_config=self._current_config,
            job_manager=self._job_manager,
        ),
        callback=self._on_evals_completed,
    )

def _on_evals_completed(self, job: Job | None) -> None:
    """Handle the result from TabbedEvalsModal."""
    if job is not None:
        self.notify(f"Job {job.display_name} created...")
        self._simulate_job_completion(job)
```

**Removed intermediate methods:**
- `_on_evals_option_selected()` - no longer needed
- `_show_run_evals_modal()` - integrated into TabbedEvalsModal
- `_show_job_list_modal()` - integrated into TabbedEvalsModal
- `_on_job_selected()` - handled internally
- `_show_job_detail_modal()` - handled internally

### `src/satellite/main.tcss`

**Added TabbedEvalsModal styles:**

```css
/* Tab content visibility */
TabbedEvalsModal .tab-pane {
    display: none;
}
TabbedEvalsModal .tab-pane.-active {
    display: block;
}

/* Per-tab button rows */
TabbedEvalsModal .button-row {
    display: none;
}
TabbedEvalsModal.-tab-run-evals #run-evals-buttons {
    display: block;
}
TabbedEvalsModal.-tab-view-progress #view-progress-buttons {
    display: block;
}
TabbedEvalsModal.-tab-job-detail #job-detail-buttons {
    display: block;
}
```

**Tab styling (Dracula theme):**
```css
TabHeader {
    border-bottom: solid #BD93F9 30%;
    background: #282A36;
}

TabItem {
    color: #6272A4;
}
TabItem.-active {
    background: #44475A;
    color: #F8F8F2;
    border-bottom: solid #BD93F9;
}
TabItem.-closable #close-btn:hover {
    color: #FF5555;
}
```

### `src/satellite/widgets/__init__.py`

**Added exports:**
```python
from satellite.widgets.tab_item import TabItem
from satellite.widgets.tab_header import TabHeader
```

### `src/satellite/modals/__init__.py`

**Added export:**
```python
from .tabbed_evals_modal import TabbedEvalsModal
```

---

## Keyboard Navigation

| Context | Keys | Action |
|---------|------|--------|
| TabHeader | `Left/Right` | Switch between tabs |
| TabHeader | `1/2/3` | Jump to tab by number |
| Run Evals content | `Up/Down/j/k` | Navigate benchmark list |
| Run Evals content | `Space` | Toggle benchmark selection |
| Run Evals content | `r` | Run selected benchmarks |
| View Progress content | `Up/Down/j/k` | Navigate job list |
| View Progress content | `Enter/Space` | Open job detail tab |
| Any | `Escape` | Close dynamic tab or dismiss modal |

---

## Testing

### Manual Testing Steps

1. **Run the app:**
   ```bash
   cd satellite && python -m satellite
   ```

2. **Test tabbed modal:**
   - Press `2` or navigate to "Evals" and press Enter
   - Modal should appear with two tabs at top
   - Use `Left/Right` arrows to switch tabs
   - Verify content changes when switching

3. **Test Run Evals tab:**
   - Select benchmarks using arrow keys + Space
   - Click "Run Selected" or press `r`
   - Should see "Evaluation Started" notification
   - After 2 seconds, "Evaluation Complete" notification

4. **Test View Progress tab:**
   - Switch to View Progress tab
   - Should see created jobs with status
   - Press Enter on a job to open detail tab

5. **Test dynamic job tabs:**
   - Job detail opens as new tab (closable)
   - Click [x] or press Escape to close
   - Returns to View Progress tab

6. **Test state preservation:**
   - Select some benchmarks in Run Evals
   - Switch to View Progress
   - Switch back to Run Evals
   - Benchmarks should still be selected

### Verify persistence:
```bash
ls ~/Library/Application\ Support/satellite/jobs/
cat ~/Library/Application\ Support/satellite/jobs/job_1/metadata.json
```

---

## Files Summary

### New Files Created

| File | Description |
|------|-------------|
| `src/satellite/widgets/tab_item.py` | Single clickable tab widget |
| `src/satellite/widgets/tab_header.py` | Tab container with navigation |
| `src/satellite/modals/tabbed_evals_modal.py` | Unified tabbed modal |

### Files Modified

| File | Change |
|------|--------|
| `src/satellite/screens/main.py` | Uses TabbedEvalsModal instead of EvalsModal |
| `src/satellite/main.tcss` | Added TabbedEvalsModal, TabHeader, TabItem styles |
| `src/satellite/widgets/__init__.py` | Exports TabItem, TabHeader |
| `src/satellite/modals/__init__.py` | Exports TabbedEvalsModal |

### Files Kept for Reference (not deleted)

| File | Reason |
|------|--------|
| `src/satellite/modals/evals_modal.py` | Original option picker pattern |
| `src/satellite/modals/run_evals_modal.py` | Standalone modal version |
| `src/satellite/modals/job_list_modal.py` | Standalone modal version |
| `src/satellite/modals/job_detail_modal.py` | Standalone modal version |

---

## Color Scheme (Dracula)

| Element | Color | Hex |
|---------|-------|-----|
| Background | Dark grey | #282A36 |
| Foreground | White | #F8F8F2 |
| Primary/Active | Purple | #BD93F9 |
| Comment/Muted | Blue-grey | #6272A4 |
| Hover | Light grey | #44475A |
| Pending status | Orange | #FFB86C |
| Running status | Cyan | #8BE9FD |
| Completed status | Green | #50FA7B |
| Failed status | Red | #FF5555 |

---

## Summary

| Feature | Status |
|---------|--------|
| Tabbed modal interface | ✅ |
| Run Evals tab | ✅ |
| View Progress tab | ✅ |
| Dynamic job detail tabs | ✅ |
| Tab keyboard navigation | ✅ |
| State preservation between tabs | ✅ |
| Per-tab button rows | ✅ |
| Job creation | ✅ |
| Job persistence (XDG) | ✅ |
| Mock async completion | ✅ |
| Dracula theme styling | ✅ |
