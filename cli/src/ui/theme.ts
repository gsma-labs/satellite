// ── Claude Code Visual Theme ───────────────────────────────────────

export const colors = {
  user: "#22c55e",       // green
  assistant: "#eab308",  // yellow
  toolBorder: "#06b6d4", // cyan
  toolDim: "#6b7280",    // gray
  error: "#ef4444",      // red
  success: "#22c55e",    // green
  dim: "#6b7280",        // gray-500
  accent: "#a78bfa",     // purple
  statusBg: "#1f2937",   // gray-800
} as const;

export const symbols = {
  userPrompt: ">",
  assistantBullet: "●",
  cursor: "█",
  toolRunning: "⣾",
  toolCompleted: "✓",
  toolError: "✗",
  separator: "│",
  progressFilled: "█",
  progressEmpty: "░",
} as const;

// Braille spinner frames (same as Claude Code)
export const spinnerFrames = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"] as const;

// Tool display metadata: verb while running, past tense when done
export const toolVerbs: Record<string, { verb: string; pastTense: string }> = {
  list_benchmarks: { verb: "Listing benchmarks...", pastTense: "Listed benchmarks" },
  run_eval:        { verb: "Running evaluation...", pastTense: "Ran evaluation" },
  list_jobs:       { verb: "Listing jobs...",       pastTense: "Listed jobs" },
  get_job_results: { verb: "Fetching results...",   pastTense: "Fetched results" },
  check_job_status:{ verb: "Checking status...",    pastTense: "Checked status" },
  fetch_leaderboard:{ verb: "Fetching leaderboard...", pastTense: "Fetched leaderboard" },
  get_eval_settings:{ verb: "Reading settings...",  pastTense: "Read settings" },
  submit_to_leaderboard: { verb: "Submitting results...", pastTense: "Submitted results" },
} as const;

// Claude API pricing (Sonnet 4)
export const pricing = {
  model: "claude-sonnet-4-20250514",
  inputPer1k: 0.003,
  outputPer1k: 0.015,
} as const;
