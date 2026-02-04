# Satetoad TUI Feature Parity TODO

Focus: UI/UX enhancements with mocked backend. No real API calls.

---

## 1. Model Configuration Panel

### Missing UI
- [ ] Model input field (format: `provider/model-name`)
- [ ] More providers (satellite has 9, satetoad has 4)
- [ ] API key validation indicator (checking → valid/invalid)
- [ ] Success feedback when key is "saved"

### Mock Behavior
- [ ] Store config in memory (mock persistence)
- [ ] Simulate validation delay (1s)

---

## 2. Run Evals Panel

### Missing UI: Pre-run Check
- [ ] Checklist widget showing "Checking model connectivity..."
- [ ] Animated status (pending → running → passed/failed)

### Missing UI: Benchmark Selection
- [ ] Modal/overlay to select which benchmarks to run
- [ ] Checkboxes with benchmark names

### Missing UI: Evaluation Progress
- [ ] Per-benchmark progress row showing:
  - Benchmark name
  - Running indicator (animated)
  - Score when complete
- [ ] Cancel button

### Missing UI: Results
- [ ] Summary of all scores when complete

### Mock Behavior
- [ ] Simulate connectivity check (2s)
- [ ] Simulate eval progress (3s per benchmark)
- [ ] Return mock scores

---

## 3. Leaderboard Panel

### Missing UI
- [ ] Loading indicator (Throbber)
- [ ] Proper table with columns: Rank, Model, Provider, TCI, per-benchmark scores
- [ ] Highlight row for user's model
- [ ] Refresh button

### Mock Behavior
- [ ] Mock leaderboard data (15 entries)
- [ ] Simulate fetch delay (1.5s)

---

## 4. Settings/Submit Panel (Simplified)

### For Now (Minimal)
- [ ] GitHub token input field
- [ ] Token validation indicator
- [ ] "Coming soon" message for actual submission

---

## 5. New Widgets Needed

### ChecklistItem
- [ ] Status icon: ○ (pending), ◐ (running), ● (done), ✕ (failed)
- [ ] Label text
- [ ] Animated dots when running

### BenchmarkSelectModal
- [ ] List of benchmarks with checkboxes
- [ ] Select all / None buttons
- [ ] Confirm / Cancel

---

## 6. Mock Data

### Add to `examples/eval_data.py`
- [ ] Full provider list (9 providers)
- [ ] Mock leaderboard entries (15 models with scores)
- [ ] Mock eval results per benchmark

---

## Implementation Order

1. [ ] Add ChecklistItem widget
2. [ ] Add BenchmarkSelectModal widget
3. [ ] Enhance model_panel.py (more providers, validation UI)
4. [ ] Enhance evals_panel.py (checklist, selection, progress)
5. [ ] Enhance leaderboard_panel.py (loading, proper table)
6. [ ] Add mock data to eval_data.py
