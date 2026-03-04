// ── Benchmark Registry ──────────────────────────────────────────────

export interface BenchmarkConfig {
  id: string;
  name: string;
  modulePath: string;
  samples: number;
  hfColumn: string;
}

// ── Eval / Job Types ────────────────────────────────────────────────

export type JobStatus =
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "unknown";

export interface JobInfo {
  jobId: string;
  benchmarkId: string;
  model: string;
  status: JobStatus;
  startedAt: string;
  completedAt?: string;
  score?: number;
  stderr?: number;
  totalSamples?: number;
  completedSamples?: number;
}

export interface EvalLogHeader {
  status: "started" | "success" | "error" | "cancelled";
  evalModel: string;
  evalTask: string;
  totalSamples?: number;
  completedSamples?: number;
}

export interface EvalLogResult {
  score: number;
  stderr?: number;
  totalSamples: number;
  metric: string;
}

// ── Run Command Events (JSONL) ──────────────────────────────────────

export type RunEvent =
  | { event: "started"; jobId: string; benchmark: string; model: string }
  | {
      event: "progress";
      jobId: string;
      completed: number;
      total: number;
    }
  | {
      event: "completed";
      jobId: string;
      score: number;
      stderr?: number;
      samples: number;
    }
  | { event: "error"; jobId: string; message: string }
  | { event: "cancelled"; jobId: string };

// ── Leaderboard ─────────────────────────────────────────────────────

export interface LeaderboardEntry {
  model: string;
  provider?: string;
  scores: Record<string, LeaderboardScore>;
  date?: string;
}

export interface LeaderboardScore {
  score: number;
  stderr?: number;
  samples?: number;
}

// ── Submit ───────────────────────────────────────────────────────────

export interface SubmitPreview {
  model: string;
  provider: string;
  benchmarks: Record<string, { score: number; stderr?: number }>;
  parquetPath: string;
}

export interface SubmitResult {
  prUrl: string;
  branch: string;
  model: string;
}

// ── Config ───────────────────────────────────────────────────────────

export interface EvalSettings {
  epochs: number;
  maxConnections: number;
  limit?: number;
  logSamples: boolean;
}

export interface EnvConfig {
  model?: string;
  githubToken?: string;
  [key: string]: string | undefined;
}

// ── GitHub API ───────────────────────────────────────────────────────

export interface GitHubUser {
  login: string;
}

export interface GitHubRef {
  ref: string;
  object: { sha: string; type: string };
}

export interface GitHubBlob {
  sha: string;
  url: string;
}

export interface GitHubTree {
  sha: string;
  url: string;
}

export interface GitHubCommit {
  sha: string;
  url: string;
}

export interface GitHubPR {
  html_url: string;
  number: number;
}

// ── CLI ──────────────────────────────────────────────────────────────

export interface CLIArgs {
  command: string;
  flags: Record<string, string | boolean>;
  positional: string[];
}

// ── Errors ───────────────────────────────────────────────────────────

export type ErrorCode =
  | "EVAL_ERROR"
  | "PARSE_ERROR"
  | "CONFIG_ERROR"
  | "SUBMIT_ERROR"
  | "GITHUB_ERROR"
  | "NETWORK_ERROR"
  | "NOT_FOUND"
  | "INVALID_ARGS"
  | "CANCELLED";
