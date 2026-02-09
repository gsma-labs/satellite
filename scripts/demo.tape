# Satetoad TUI Demo - VHS Tape File
# Run with: vhs scripts/demo.tape
# Output: docs/demo.gif (and docs/demo.mp4)
# Duration: ~30-35s (fast-paced showcase)

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
Set PlaybackSpeed 1.2
Set TypingSpeed 35ms
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
Sleep 3s

# ─── Show the main screen ────────────────────
Sleep 1.5s

# ─── Help overlay (?) ─────────────────────────
Type@200ms "?"
Sleep 1.5s

# ─── Navigate action boxes with arrow keys ───
Down
Sleep 250ms
Down
Sleep 250ms
Up
Sleep 250ms
Up
Sleep 400ms

# ─── Open Evals modal (key 1) ────────────────
Type "1"
Sleep 1.5s

# Toggle a benchmark off with Space
Down
Sleep 300ms
Down
Sleep 300ms
Space
Sleep 800ms

# Toggle it back on
Space
Sleep 800ms

# Close Evals modal
Escape
Sleep 1s

# ─── Open Leaderboard modal (key 2) ──────────
Type "2"
Sleep 2s

# Scroll the leaderboard table
Down
Sleep 250ms
Down
Sleep 250ms
Down
Sleep 250ms
Up
Sleep 400ms

# Close Leaderboard
Escape
Sleep 1s

# ─── Open Submit modal (key 3) ───────────────
Type "3"
Sleep 1.5s

# Fill in the form
Tab
Sleep 200ms
Type@60ms "GPT-4o Evaluation"
Tab
Sleep 200ms
Type@60ms "Open Telco"
Tab
Sleep 200ms
Type@60ms "Benchmark run v1"
Sleep 1.5s

# Close without submitting
Escape
Sleep 1s

# ─── Open Lab APIs model config (key 4) ──────
Type "4"
Sleep 1.5s

# Tab through the form fields
Tab
Sleep 300ms
Tab
Sleep 300ms
Tab
Sleep 300ms

Sleep 1s

# Close model config
Escape
Sleep 1s

# ─── Open Cloud APIs (key 5) ─────────────────
Type "5"
Sleep 1.5s

# Close Cloud APIs
Escape
Sleep 1s

# ─── Final pause on main screen ──────────────
Sleep 1s

# ─── Quit ─────────────────────────────────────
Type "q"
Sleep 1.5s
