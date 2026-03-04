import { BENCHMARKS, getBenchmark } from "../../services/benchmark-registry.js";
import { runEval } from "../../services/eval-runner.js";
import { resolveJobsDir } from "../../services/job-manager.js";
import { loadEvalSettings } from "../../services/config-manager.js";
import { readEvalLogHeader, listEvalLogs } from "../../services/eval-log-reader.js";
import { join } from "node:path";
import { mkdirSync } from "node:fs";

export async function executeTool(
  name: string,
  params: Record<string, unknown>,
  onProgress?: (completed: number, total: number) => void,
): Promise<string> {
  switch (name) {
    case "list_benchmarks":
      return handleListBenchmarks();
    case "run_eval":
      return handleRunEval(params, onProgress);
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

function handleListBenchmarks(): string {
  const list = BENCHMARKS.map((b) => ({
    id: b.id,
    name: b.name,
    samples: b.samples,
  }));
  return JSON.stringify(list);
}

function sanitizeForPath(s: string): string {
  return s.replace(/\//g, "_").replace(/[^a-zA-Z0-9_.-]/g, "");
}

async function handleRunEval(
  params: Record<string, unknown>,
  onProgress?: (completed: number, total: number) => void,
): Promise<string> {
  const benchmarkId = params.benchmark_id as string;
  const model = params.model as string;
  const limit = params.limit as number | undefined;

  const benchmark = getBenchmark(benchmarkId);
  if (!benchmark) {
    throw new Error(
      `Unknown benchmark: "${benchmarkId}". Available: ${BENCHMARKS.map((b) => b.id).join(", ")}`,
    );
  }

  const jobId = `job_${Date.now()}`;
  const jobsDir = resolveJobsDir();
  const logDir = join(jobsDir, jobId, sanitizeForPath(model));
  mkdirSync(logDir, { recursive: true });

  const settings = loadEvalSettings();
  if (limit != null) {
    settings.limit = limit;
  }

  const result = await runEval({
    jobId,
    benchmarkId,
    model,
    logDir,
    settings,
    onProgress,
  });

  if (!result.success) {
    if (result.cancelled) {
      throw new Error("Evaluation was cancelled");
    }
    throw new Error(result.error ?? "Evaluation failed");
  }

  // Read final eval log to get score
  const logFiles = await listEvalLogs(logDir);
  let score: number | undefined;
  let stderr: number | undefined;
  let samples: number | undefined;

  for (const logFile of logFiles) {
    const header = await readEvalLogHeader(logFile);
    if (header?.accuracy != null) {
      score = Math.round(header.accuracy * 10000) / 100;
      stderr = header.stderr != null ? Math.round(header.stderr * 10000) / 100 : undefined;
      samples = header.totalSamples;
      break;
    }
  }

  return JSON.stringify({
    jobId,
    benchmark: benchmark.name,
    model,
    score,
    stderr,
    samples,
  });
}
