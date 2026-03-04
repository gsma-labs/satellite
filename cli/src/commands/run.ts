import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import type { CLIArgs } from "../types/index.js";
import { emitEvent } from "../utils/output.js";
import { exitWithError } from "../utils/errors.js";
import { getBenchmark } from "../services/benchmark-registry.js";
import { loadEvalSettings } from "../services/config-manager.js";
import { runEval } from "../services/eval-runner.js";
import { readEvalLogHeader, listEvalLogs } from "../services/eval-log-reader.js";

function generateJobId(): string {
  const now = new Date();
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  const stamp = [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    "_",
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
  ].join("");
  return `job_${stamp}`;
}

export async function runCommand(args: CLIArgs): Promise<void> {
  const benchmarkId = args.flags.benchmark;
  const model = args.flags.model;
  const limitFlag = args.flags.limit;
  const jobsDirFlag = args.flags["jobs-dir"];

  if (typeof benchmarkId !== "string" || !benchmarkId) {
    exitWithError("--benchmark is required", "INVALID_ARGS");
  }
  if (typeof model !== "string" || !model) {
    exitWithError("--model is required", "INVALID_ARGS");
  }

  const benchmark = getBenchmark(benchmarkId);
  if (!benchmark) {
    exitWithError(`Unknown benchmark: ${benchmarkId}`, "NOT_FOUND");
  }

  // Load settings and apply overrides
  const settings = loadEvalSettings();
  if (typeof limitFlag === "string") {
    const parsed = parseInt(limitFlag, 10);
    if (!Number.isNaN(parsed) && parsed > 0) {
      settings.limit = parsed;
    }
  }

  const jobId = generateJobId();
  const jobsDir = typeof jobsDirFlag === "string" ? resolve(jobsDirFlag) : resolve("jobs");
  const logDir = join(jobsDir, jobId, model);

  // Create job directory and write manifest
  mkdirSync(logDir, { recursive: true });
  const manifest = {
    evals: { [model]: [benchmarkId] },
    total_evals: 1,
  };
  writeFileSync(join(jobsDir, jobId, "job-manifest.json"), JSON.stringify(manifest, null, 2) + "\n");

  // Emit started event
  emitEvent({ event: "started", jobId, benchmark: benchmarkId, model });

  // Handle SIGINT for cancellation
  let cancelRequested = false;
  const sigintHandler = () => {
    cancelRequested = true;
  };
  process.on("SIGINT", sigintHandler);

  // Run evaluation
  const result = await runEval({
    jobId,
    benchmarkId,
    model,
    logDir,
    settings,
    onProgress(completed, total) {
      emitEvent({ event: "progress", jobId, completed, total });
    },
  });

  process.off("SIGINT", sigintHandler);

  if (result.cancelled || cancelRequested) {
    emitEvent({ event: "cancelled", jobId });
    process.exit(2);
  }

  if (!result.success) {
    emitEvent({ event: "error", jobId, message: result.error ?? "Unknown error" });
    process.exit(1);
  }

  // Read final results for completed event
  const logFiles = await listEvalLogs(logDir);
  let score = 0;
  let stderr: number | undefined;
  let samples = 0;

  for (const logFile of logFiles) {
    const header = await readEvalLogHeader(logFile);
    if (header?.status === "success") {
      score = header.accuracy ?? 0;
      stderr = header.stderr;
      samples = header.totalSamples ?? 0;
      break;
    }
  }

  const completedEvent: Record<string, unknown> = {
    event: "completed",
    jobId,
    score,
    samples,
  };
  if (stderr != null) {
    completedEvent.stderr = stderr;
  }
  emitEvent(completedEvent);
  process.exit(0);
}
