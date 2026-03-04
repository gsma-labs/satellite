import { readdir, stat } from "node:fs/promises";
import { join } from "node:path";

// ── Types for raw Inspect AI JSON log structure ───────────────────────

interface RawEvalLog {
  status: "started" | "success" | "error" | "cancelled";
  eval: {
    task: string;
    model: string;
    dataset?: {
      samples?: number;
      sample_ids?: string[];
    };
    config?: {
      epochs?: number;
      limit?: number | null;
    };
    eval_id?: string;
  };
  results?: {
    scores?: Array<{
      metrics: Record<string, { value: number }>;
    }>;
    total_samples?: number;
    completed_samples?: number;
  };
  stats?: {
    started_at?: string;
    completed_at?: string;
    model_usage?: Record<string, { total_tokens?: number }>;
  };
}

export interface ParsedEvalLog {
  status: "started" | "success" | "error" | "cancelled";
  evalModel: string;
  evalTask: string;
  taskName: string;
  totalSamples?: number;
  completedSamples?: number;
  accuracy?: number;
  stderr?: number;
  startedAt?: string;
  completedAt?: string;
  totalTokens?: number;
}

// ── Core functions ────────────────────────────────────────────────────

/**
 * Read and parse an Inspect AI JSON log file, returning structured header info.
 */
export async function readEvalLogHeader(filePath: string): Promise<ParsedEvalLog | null> {
  try {
    const file = Bun.file(filePath);
    const text = await file.text();
    const raw: RawEvalLog = JSON.parse(text);

    if (!raw.status || !raw.eval) {
      return null;
    }

    const taskName = raw.eval.task.split("/").pop() ?? raw.eval.task;

    let accuracy: number | undefined;
    let stderr: number | undefined;
    if (raw.results?.scores?.length) {
      const metrics = raw.results.scores[0].metrics;
      if (metrics.accuracy) {
        accuracy = metrics.accuracy.value;
      }
      if (metrics.stderr) {
        stderr = metrics.stderr.value;
      }
    }

    let totalTokens: number | undefined;
    if (raw.stats?.model_usage) {
      totalTokens = 0;
      for (const usage of Object.values(raw.stats.model_usage)) {
        totalTokens += usage.total_tokens ?? 0;
      }
    }

    return {
      status: raw.status,
      evalModel: raw.eval.model,
      evalTask: raw.eval.task,
      taskName,
      totalSamples: raw.results?.total_samples,
      completedSamples: raw.results?.completed_samples,
      accuracy,
      stderr,
      startedAt: raw.stats?.started_at,
      completedAt: raw.stats?.completed_at,
      totalTokens,
    };
  } catch {
    return null;
  }
}

/**
 * Find all .json eval log files in a directory (recursively).
 * Only includes files that look like Inspect AI eval logs.
 */
export async function listEvalLogs(dir: string): Promise<string[]> {
  const results: string[] = [];

  async function walk(currentDir: string): Promise<void> {
    let entries: string[];
    try {
      entries = await readdir(currentDir);
    } catch {
      return;
    }

    for (const entry of entries) {
      const fullPath = join(currentDir, entry);
      try {
        const info = await stat(fullPath);
        if (info.isDirectory()) {
          await walk(fullPath);
        } else if (entry.endsWith(".json") && !entry.startsWith(".")) {
          // Quick check: read first ~500 bytes to verify it looks like an eval log
          const file = Bun.file(fullPath);
          if (file.size === 0) continue;
          const slice = await file.slice(0, 500).text();
          if (slice.includes('"status"') && slice.includes('"eval"')) {
            results.push(fullPath);
          }
        }
      } catch {
        // Skip unreadable entries
      }
    }
  }

  await walk(dir);
  return results;
}

/**
 * Extract (model, taskName, accuracy) from a parsed eval log.
 */
export function extractAccuracy(
  log: ParsedEvalLog
): { model: string; taskName: string; accuracy: number } | null {
  if (!log.evalModel || !log.evalTask || log.accuracy == null) {
    return null;
  }
  return {
    model: log.evalModel,
    taskName: log.taskName,
    accuracy: log.accuracy,
  };
}

/**
 * Extract (model, taskName, sampleCount) from a parsed eval log.
 */
export function extractSampleCount(
  log: ParsedEvalLog
): { model: string; taskName: string; sampleCount: number } | null {
  if (!log.evalModel || !log.evalTask || log.totalSamples == null) {
    return null;
  }
  return {
    model: log.evalModel,
    taskName: log.taskName,
    sampleCount: log.totalSamples,
  };
}
