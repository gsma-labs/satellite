# Satetoad TUI Demo - VHS Tape File
# Run with: vhs scripts/demo.tape
# Output: docs/demo.gif (and docs/demo.mp4)

Require uv

Output docs/demo.gif
Output docs/demo.mp4

# Terminal appearance
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

# ─── Launch the app ───────────────────────────
Hide
Type "cd /Users/emolero/Documents/GitHub/ot/satetoad"
Enter
Sleep 500ms
Show

Type "uv run python -m satetoad"
Enter
Sleep 4s

# ─── Show the main screen ────────────────────
# Pause to let viewers see the landing page
Sleep 3s

# ─── Help overlay (F1) ───────────────────────
Type@200ms "?"
Sleep 3s

# ─── Navigate action boxes with arrow keys ───
Down
Sleep 800ms
Down
Sleep 800ms
Up
Sleep 800ms
Up
Sleep 800ms

# ─── Open Evals modal (key 1) ────────────────
Type "1"
Sleep 2s

# Toggle a benchmark off with Space
Down
Sleep 500ms
Down
Sleep 500ms
Space
Sleep 1s

# Toggle it back on
Space
Sleep 1s

# Close Evals modal
Escape
Sleep 2s

# ─── Open Leaderboard modal (key 2) ──────────
Type "2"
Sleep 4s

# Navigate leaderboard table
Down
Sleep 400ms
Down
Sleep 400ms
Down
Sleep 400ms
Up
Sleep 400ms

# Close Leaderboard
Escape
Sleep 2s

# ─── Open Submit modal (key 3) ───────────────
Type "3"
Sleep 2s

# Fill in the form
Tab
Sleep 300ms
Type@100ms "GPT-4o Evaluation"
Tab
Sleep 300ms
Type@100ms "Open Telco"
Tab
Sleep 300ms
Type@100ms "Benchmark run v1"
Sleep 2s

# Close without submitting
Escape
Sleep 2s

# ─── Open Lab APIs model config (key 4) ──────
Type "4"
Sleep 2s

# Navigate the form
Tab
Sleep 500ms
Tab
Sleep 500ms
Tab
Sleep 500ms

Sleep 2s

# Close model config
Escape
Sleep 2s

# ─── Open Env Vars (key c) ───────────────────
Type "c"
Sleep 2s

# Close env vars
Escape
Sleep 2s

# ─── Navigate to agents section ──────────────
Sleep 1s

# Launch an agent (key 9 = Claude Code)
Type "9"
Sleep 3s

# ─── Final pause on main screen ──────────────
Sleep 2s

# ─── Quit ─────────────────────────────────────
Type "q"
Sleep 2s
