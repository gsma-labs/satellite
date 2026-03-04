import { readdir, stat, access } from "node:fs/promises";
import { join } from "node:path";
import type { JobStatus } from "../types/index.js";
import {
  readEvalLogHeader,
  listEvalLogs,
  extractAccuracy,
  extractSampleCount,
} from "./eval-log-reader.js";

// ── Constants ─────────────────────────────────────────────────────────

const CANCELLED_MARKER = "cancelled";

const STATUS_PRIORITY: Record<string, number> = {
  running: 0,
  error: 1,
  cancelled: 2,
  success: 3,
};

// ── Status mapping ────────────────────────────────────────────────────

/** Map Inspect AI log status to our JobStatus. */
function mapLogStatus(logStatus: string): JobStatus {
  switch (logStatus) {
    case "started":
      return "running";
    case "success":
      return "completed";
    case "error":
      return "failed";
    case "cancelled":
      return "cancelled";
    default:
      return "unknown";
  }
}

// ── Manifest / eval-set parsing ───────────────────────────────────────

interface JobManifest {
  evals: Record<string, string[]>;
  total_evals: number;
  settings?: Record<string, unknown>;
}

interface LegacyEvalSet {
  tasks: Array<{ model: string; name: string }>;
}

async function loadManifest(
  jobDir: string
): Promise<{ evals: Record<string, string[]>; totalEvals: number } | null> {
  const manifestPath = join(jobDir, "job-manifest.json");
  try {
    const file = Bun.file(manifestPath);
    if (!(await file.exists())) return null;
    const data: JobManifest = await file.json();
    return {
      evals: data.evals ?? {},
      totalEvals: data.total_evals ?? 0,
    };
  } catch {
    return null;
  }
}

async function loadLegacyEvalSets(
  jobDir: string
): Promise<{ evals: Record<string, string[]>; totalEvals: number }> {
  const evals: Record<string, string[]> = {};

  async function scanDir(dir: string): Promise<void> {
    let entries: string[];
    try {
      entries = await readdir(dir);
    } catch {
      return;
    }
    for (const entry of entries) {
      const fullPath = join(dir, entry);
      const info = await stat(fullPath).catch(() => null);
      if (!info) continue;
      if (info.isDirectory()) {
        await scanDir(fullPath);
      } else if (entry === "eval-set.json") {
        try {
          const data: LegacyEvalSet = await Bun.file(fullPath).json();
          const tasks = data.tasks ?? [];
          if (tasks.length > 0) {
            const model = tasks[0].model;
            const benchmarks = tasks.map((t) => t.name.split("/").pop() ?? t.name);
            evals[model] = benchmarks;
          }
        } catch {
          // Skip malformed eval-set files
        }
      }
    }
  }

  await scanDir(jobDir);
  const totalEvals = Object.values(evals).reduce((sum, b) => sum + b.length, 0);
  return { evals, totalEvals };
}

// ── Job loading ───────────────────────────────────────────────────────

export interface Job {
  jobId: string;
  status: JobStatus;
  evals: Record<string, string[]>;
  totalEvals: number;
  completedEvals: number;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
}

async function hasCancelledMarker(jobDir: string): Promise<boolean> {
  try {
    await access(join(jobDir, CANCELLED_MARKER));
    return true;
  } catch {
    return false;
  }
}

async function getCreatedAt(jobDir: string): Promise<string> {
  const manifestPath = join(jobDir, "job-manifest.json");
  try {
    const info = await stat(manifestPath);
    return info.mtime.toISOString();
  } catch {
    // Fall back to job directory mtime
    try {
      const info = await stat(jobDir);
      return info.mtime.toISOString();
    } catch {
      return new Date().toISOString();
    }
  }
}

/**
 * Discover model subdirectories that contain eval log files.
 */
async function discoverModelDirs(jobDir: string): Promise<string[]> {
  const modelDirs: string[] = [];
  let entries: string[];
  try {
    entries = await readdir(jobDir);
  } catch {
    return [];
  }

  for (const entry of entries) {
    const fullPath = join(jobDir, entry);
    const info = await stat(fullPath).catch(() => null);
    if (!info?.isDirectory()) continue;
    const logs = await listEvalLogs(fullPath);
    if (logs.length > 0) {
      modelDirs.push(fullPath);
    }
  }
  return modelDirs;
}

/**
 * Aggregate status and progress from all eval logs in model directories.
 */
async function aggregateProgress(
  modelDirs: string[]
): Promise<{
  status: JobStatus;
  completedEvals: number;
  foundEvals: number;
  startedAt?: string;
  completedAt?: string;
}> {
  const statuses: string[] = [];
  let completedEvals = 0;
  let foundEvals = 0;
  const startedTimes: string[] = [];
  const completedTimes: string[] = [];

  for (const modelDir of modelDirs) {
    const logFiles = await listEvalLogs(modelDir);
    for (const logFile of logFiles) {
      const log = await readEvalLogHeader(logFile);
      if (!log) continue;

      foundEvals++;
      statuses.push(log.status);

      if (log.status !== "started") {
        completedEvals++;
      }

      if (log.startedAt) startedTimes.push(log.startedAt);
      if (log.completedAt) completedTimes.push(log.completedAt);
    }
  }

  // Determine aggregate status: use min by priority
  let status: JobStatus = "running";
  if (statuses.length > 0) {
    const minPriorityStatus = statuses.reduce((a, b) =>
      (STATUS_PRIORITY[a] ?? 99) <= (STATUS_PRIORITY[b] ?? 99) ? a : b
    );
    status = mapLogStatus(minPriorityStatus);
  }

  const startedAt =
    startedTimes.length > 0
      ? startedTimes.sort()[0]
      : undefined;
  const completedAt =
    completedTimes.length > 0
      ? completedTimes.sort().pop()
      : undefined;

  return { status, completedEvals, foundEvals, startedAt, completedAt };
}

// ── Public API ────────────────────────────────────────────────────────

/**
 * Resolve the jobs directory.
 * Priority: --jobs-dir flag > SATELLITE_JOBS_DIR env > ./jobs > ../jobs
 */
export function resolveJobsDir(flagOverride?: string): string {
  if (flagOverride) return flagOverride;

  const envDir = process.env.SATELLITE_JOBS_DIR;
  if (envDir) return envDir;

  // Check ./jobs relative to cwd
  const cwd = process.cwd();
  const localJobs = join(cwd, "jobs");
  const parentJobs = join(cwd, "..", "jobs");

  // We cannot use synchronous exists check with Bun.file,
  // so use a try/catch with accessSync
  try {
    const { accessSync } = require("node:fs");
    accessSync(localJobs);
    return localJobs;
  } catch {
    try {
      const { accessSync } = require("node:fs");
      accessSync(parentJobs);
      return parentJobs;
    } catch {
      // Default to ./jobs even if it doesn't exist yet
      return localJobs;
    }
  }
}

/**
 * Load a single Job from its directory.
 */
export async function loadJob(jobDir: string): Promise<Job | null> {
  const jobId = jobDir.split("/").pop() ?? jobDir;
  const createdAt = await getCreatedAt(jobDir);

  // Load manifest or fall back to legacy eval-set files
  let manifest = await loadManifest(jobDir);
  if (!manifest || Object.keys(manifest.evals).length === 0) {
    manifest = await loadLegacyEvalSets(jobDir);
  }

  if (Object.keys(manifest.evals).length === 0) {
    return null;
  }

  // Check for cancelled marker
  if (await hasCancelledMarker(jobDir)) {
    return {
      jobId,
      status: "cancelled",
      evals: manifest.evals,
      totalEvals: manifest.totalEvals,
      completedEvals: 0,
      createdAt,
    };
  }

  // Discover model dirs and aggregate progress
  const modelDirs = await discoverModelDirs(jobDir);
  if (modelDirs.length === 0) {
    return {
      jobId,
      status: "running",
      evals: manifest.evals,
      totalEvals: manifest.totalEvals,
      completedEvals: 0,
      createdAt,
    };
  }

  const progress = await aggregateProgress(modelDirs);

  // If we found fewer evals than the manifest says, and all observed are
  // "completed", the job is still running (not all evals have started yet).
  let { status } = progress;
  if (progress.foundEvals < manifest.totalEvals && status === "completed") {
    status = "running";
  }

  return {
    jobId,
    status,
    evals: manifest.evals,
    totalEvals: manifest.totalEvals,
    completedEvals: progress.completedEvals,
    createdAt,
    startedAt: progress.startedAt,
    completedAt: progress.completedAt,
  };
}

/**
 * List all jobs in the jobs directory, running first then by recency.
 */
export async function listJobs(
  jobsDir: string,
  limit?: number
): Promise<Job[]> {
  let entries: string[];
  try {
    entries = await readdir(jobsDir);
  } catch {
    return [];
  }

  const jobs: Job[] = [];
  for (const entry of entries) {
    if (!entry.startsWith("job_")) continue;
    const fullPath = join(jobsDir, entry);
    const info = await stat(fullPath).catch(() => null);
    if (!info?.isDirectory()) continue;

    const job = await loadJob(fullPath);
    if (job) jobs.push(job);
  }

  // Sort: running first, then by createdAt descending
  jobs.sort((a, b) => {
    const aRunning = a.status === "running" ? 0 : 1;
    const bRunning = b.status === "running" ? 0 : 1;
    if (aRunning !== bRunning) return aRunning - bRunning;
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });

  if (limit != null) {
    return jobs.slice(0, limit);
  }
  return jobs;
}

/**
 * Get accuracy scores for a job: {model: {benchmark: score}}.
 */
export async function getJobResults(
  jobsDir: string,
  jobId: string
): Promise<Record<string, Record<string, number>>> {
  const jobDir = join(jobsDir, jobId);
  const logFiles = await listEvalLogs(jobDir);
  const results: Record<string, Record<string, number>> = {};

  for (const logFile of logFiles) {
    const log = await readEvalLogHeader(logFile);
    if (!log) continue;
    const triple = extractAccuracy(log);
    if (!triple) continue;

    const { model, taskName, accuracy } = triple;
    if (!results[model]) results[model] = {};
    results[model][taskName] = accuracy;
  }

  return results;
}

/**
 * Get sample counts for a job: {model: {benchmark: count}}.
 */
export async function getJobSampleCounts(
  jobsDir: string,
  jobId: string
): Promise<Record<string, Record<string, number>>> {
  const jobDir = join(jobsDir, jobId);
  const logFiles = await listEvalLogs(jobDir);
  const counts: Record<string, Record<string, number>> = {};

  for (const logFile of logFiles) {
    const log = await readEvalLogHeader(logFile);
    if (!log) continue;
    const triple = extractSampleCount(log);
    if (!triple) continue;

    const { model, taskName, sampleCount } = triple;
    if (!counts[model]) counts[model] = {};
    counts[model][taskName] = sampleCount;
  }

  return counts;
}
