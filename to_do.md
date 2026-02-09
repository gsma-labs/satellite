Executive Summary
This plan describes the TUI features missing from satellite to achieve feature parity with satellite. All backend functionality will be mocked. The focus is purely on user interface and user experience.

Current State Analysis
What Satellite Has
Main screen with 4 EvalBox cards in a 2x2 grid (GridSelect)
Panel-based navigation using CSS visibility toggling
Basic SetModelPanel with provider dropdown and API key input
Basic RunEvalsPanel with benchmark list (EvalList)
Placeholder LeaderboardPanel with static table
Placeholder SubmitPanel with form fields
Visual widgets: Satellite, TowerNetwork, Mandelbrot
Utility widgets: Flash (notifications), Throbber (loading)
What Satellite Has (That Satellite Lacks)
Model input field with provider/model format
9 providers (vs satellite's 4)
API key validation with visual feedback
Pre-flight connectivity check with animated status
Benchmark selection modal
Per-benchmark progress tracking during evaluation
Real-time score display during/after evaluation
Dynamic leaderboard with loading state and data fetching
Row highlighting for user's model in leaderboard
Missing TUI Components
1. ChecklistItem Widget
Purpose: Display a step with status indicator and optional animation.

Visual States:


○  Pending task          [gray, dim]
◐  Running task...       [blue, animated dots]
●  Completed task        [green]
✕  Failed task           [red]
Properties:

Property	Type	Description
label	str	Main text displayed
status	Literal["pending", "running", "done", "failed"]	Current state
detail	str | None	Optional sub-text (e.g., "Score: 0.78")
Behavior:

When status is "running", animate ellipsis: ... → . → .. → ...
Use set_interval() for animation timer
Emit StatusChanged message when status changes
CSS Classes:

.-pending, .-running, .-done, .-failed for styling
2. BenchmarkSelectModal Widget
Purpose: Modal overlay for selecting which benchmarks to run.

Layout:


┌─────────────────────────────────────┐
│  Select Benchmarks                  │
├─────────────────────────────────────┤
│  [✓] TeleQnA    - Q&A benchmark     │
│  [✓] TeleLogs   - Log analysis      │
│  [✓] TeleMath   - Math problems     │
│  [✓] TeleTables - Table parsing     │
│  [ ] 3GPP-TSG   - Standards docs    │
├─────────────────────────────────────┤
│  [Select All]  [None]               │
│                                     │
│        [Cancel]    [Confirm]        │
└─────────────────────────────────────┘
Properties:

Property	Type	Description
benchmarks	list[dict]	Available benchmarks with id, name, description
selected	set[str]	Currently selected benchmark IDs
Behavior:

Toggle selection on click or Enter
"Select All" selects all benchmarks
"None" clears selection
"Confirm" dismisses modal and returns selected IDs
"Cancel" dismisses modal and returns None
Keyboard: arrow keys to navigate, space to toggle, escape to cancel
Messages:

BenchmarkSelectModal.Confirmed(selected: list[str])
BenchmarkSelectModal.Cancelled()
Panel Enhancements
3. SetModelPanel Enhancements
Current State: Provider dropdown + API key input + Save button

Missing UI Elements:

Element	Description
Model input field	Text input for full model string (e.g., openai/gpt-4o)
More providers	Expand from 4 to 9 providers
Validation indicator	Show spinner → checkmark/X next to API key
Auto-prefix	When provider changes, update model input prefix
New Layout:


┌─────────────────────────────────────┐
│  ← Back       Set Model             │
├─────────────────────────────────────┤
│  Provider:    [OpenAI          ▼]   │
│                                     │
│  API Key:     [••••••••••••••] [◐]  │
│                                     │
│  Model:       [openai/gpt-4o     ]  │
│                                     │
│              [Save Configuration]   │
└─────────────────────────────────────┘
Validation Indicator States:

Empty: no indicator
Typing: no indicator
After blur/save: ◐ spinning (checking)
Valid: ✓ green
Invalid: ✕ red
Provider List (9 total):

OpenAI
Anthropic
Google (Gemini)
Mistral
OpenRouter
Groq
xAI (Grok)
DeepSeek
Perplexity
4. RunEvalsPanel Enhancements
Current State: List of benchmarks with checkboxes, Run button

Missing UI Elements:

Element	Description
Pre-run checklist	ChecklistItem showing connectivity check
Benchmark selection modal	BenchmarkSelectModal for choosing tasks
Progress view	Per-benchmark ChecklistItem with scores
Results summary	Final scores table
Cancel button	Abort running evaluation
UI Stages:

Stage A: Idle


┌─────────────────────────────────────┐
│  ← Back       Run Evaluations       │
├─────────────────────────────────────┤
│                                     │
│  Ready to run evaluations.          │
│                                     │
│  Model: openai/gpt-4o               │
│                                     │
│           [Start Evaluation]        │
│                                     │
└─────────────────────────────────────┘
Stage B: Pre-run Check


┌─────────────────────────────────────┐
│  ← Back       Run Evaluations       │
├─────────────────────────────────────┤
│                                     │
│  Pre-flight Check                   │
│                                     │
│  ◐  Checking model connectivity...  │
│                                     │
│              [Cancel]               │
│                                     │
└─────────────────────────────────────┘
Stage C: Benchmark Selection


[BenchmarkSelectModal appears as overlay]
Stage D: Running


┌─────────────────────────────────────┐
│  ← Back       Run Evaluations       │
├─────────────────────────────────────┤
│                                     │
│  Running Evaluations                │
│                                     │
│  ●  TeleQnA      Score: 0.78        │
│  ◐  TeleLogs...                     │
│  ○  TeleMath                        │
│  ○  TeleTables                      │
│                                     │
│              [Cancel]               │
│                                     │
└─────────────────────────────────────┘
Stage E: Complete


┌─────────────────────────────────────┐
│  ← Back       Run Evaluations       │
├─────────────────────────────────────┤
│                                     │
│  Evaluation Complete!               │
│                                     │
│  ┌────────────┬─────────┐           │
│  │ Benchmark  │ Score   │           │
│  ├────────────┼─────────┤           │
│  │ TeleQnA    │ 0.78    │           │
│  │ TeleLogs   │ 0.65    │           │
│  │ TeleMath   │ 0.72    │           │
│  │ TeleTables │ 0.81    │           │
│  └────────────┴─────────┘           │
│                                     │
│           [Run Again]               │
│                                     │
└─────────────────────────────────────┘
State Machine:


     ┌──────────────────────────────────────┐
     │                                      │
     ▼                                      │
   IDLE ──[Start]──► CHECKING ──[Pass]──► SELECTING
     ▲                  │                   │
     │                  │[Fail]             │[Confirm]
     │                  ▼                   ▼
     │               FAILED              RUNNING ──[Done]──► COMPLETE
     │                  │                   │                   │
     │                  │                   │[Cancel]           │
     └──────────────────┴───────────────────┴───────────────────┘
5. LeaderboardPanel Enhancements
Current State: Static placeholder table

Missing UI Elements:

Element	Description
Loading state	Throbber while "fetching" data
Proper columns	Rank, Model, Provider, TCI, per-benchmark scores
Row highlighting	Highlight user's model row
Refresh button	Re-fetch leaderboard data
Error state	Show error message if fetch fails
Layout:

Loading State:


┌─────────────────────────────────────┐
│  ← Back       Leaderboard           │
├─────────────────────────────────────┤
│                                     │
│         [═══════════════]           │
│         Loading leaderboard...      │
│                                     │
└─────────────────────────────────────┘
Loaded State:


┌──────────────────────────────────────────────────────────────────┐
│  ← Back       Leaderboard                          [↻ Refresh]   │
├──────────────────────────────────────────────────────────────────┤
│  Rank │ Model           │ Provider  │ TCI   │ QnA  │ Logs │ ... │
│  ─────┼─────────────────┼───────────┼───────┼──────┼──────┼─────│
│  1    │ gpt-4o          │ OpenAI    │ 0.847 │ 0.89 │ 0.82 │     │
│  2    │ claude-3-opus   │ Anthropic │ 0.832 │ 0.87 │ 0.80 │     │
│  3    │ gemini-1.5-pro  │ Google    │ 0.815 │ 0.84 │ 0.79 │     │
│ [4]   │ [YOUR MODEL]    │ [OpenAI]  │[0.798]│[0.82]│[0.77]│     │  ← Highlighted
│  5    │ mistral-large   │ Mistral   │ 0.791 │ 0.81 │ 0.76 │     │
│  ...                                                             │
└──────────────────────────────────────────────────────────────────┘
Table Columns:

Rank (integer)
Model (string)
Provider (string)
TCI - Telco Capability Index (float, 3 decimals)
TeleQnA (float, 2 decimals)
TeleLogs (float, 2 decimals)
TeleMath (float, 2 decimals)
TeleTables (float, 2 decimals)
3GPP-TSG (float, 2 decimals)
Mock Data Requirements
Provider Configuration

PROVIDERS = [
    {"id": "openai", "name": "OpenAI", "prefix": "openai/"},
    {"id": "anthropic", "name": "Anthropic", "prefix": "anthropic/"},
    {"id": "google", "name": "Google", "prefix": "google/"},
    {"id": "mistral", "name": "Mistral", "prefix": "mistral/"},
    {"id": "openrouter", "name": "OpenRouter", "prefix": "openrouter/"},
    {"id": "groq", "name": "Groq", "prefix": "groq/"},
    {"id": "xai", "name": "xAI", "prefix": "xai/"},
    {"id": "deepseek", "name": "DeepSeek", "prefix": "deepseek/"},
    {"id": "perplexity", "name": "Perplexity", "prefix": "perplexity/"},
]
Mock Leaderboard Data
15 entries with realistic model names, providers, and scores.

Mock Evaluation Results
Per-benchmark scores with values between 0.5 and 0.95.

Files Summary
New Files to Create
File Path	Description
widgets/checklist_item.py	ChecklistItem widget with status animation
widgets/benchmark_select.py	BenchmarkSelectModal widget
Files to Modify
File Path	Changes
widgets/panels/model_panel.py	Add model input, validation indicator, more providers
widgets/panels/evals_panel.py	Add stage-based UI, ChecklistItems, results summary
widgets/panels/leaderboard_panel.py	Add loading state, DataTable, row highlighting
examples/eval_data.py	Add providers, mock leaderboard, mock scores
widgets/__init__.py	Export new widgets
Implementation Sequence
ChecklistItem widget - Foundation for progress display
BenchmarkSelectModal widget - Foundation for benchmark selection
Mock data in eval_data.py - Data needed by all panels
SetModelPanel enhancements - Model input and validation UI
RunEvalsPanel enhancements - Stage-based UI with all states
LeaderboardPanel enhancements - Loading, table, highlighting
Acceptance Criteria
ChecklistItem
 Displays correct icon for each status
 Animates ellipsis when status is "running"
 Shows detail text when provided
 Applies correct CSS class for each status
BenchmarkSelectModal
 Displays all benchmarks with checkboxes
 Toggle selection works via click and keyboard
 Select All / None buttons work
 Confirm returns selected IDs
 Cancel returns None
 Escape key cancels
SetModelPanel
 Shows 9 providers in dropdown
 Model input field accepts text
 Provider change updates model prefix
 Validation indicator shows during "check"
 Success Flash appears on save
RunEvalsPanel
 Shows correct UI for each stage
 Connectivity check shows animated ChecklistItem
 BenchmarkSelectModal opens after check passes
 Progress view shows per-benchmark ChecklistItems
 Scores appear as benchmarks complete
 Results summary shows final table
 Cancel works at any stage
LeaderboardPanel
 Throbber shows while "loading"
 DataTable displays all columns
 User's model row is highlighted
 Refresh button triggers reload