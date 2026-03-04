import { watch, mkdirSync } from "node:fs";
import type { EvalSettings } from "../types/index.js";
import { getBenchmark } from "./benchmark-registry.js";
import { readEvalLogHeader, listEvalLogs } from "./eval-log-reader.js";

export interface EvalRunnerOptions {
  jobId: string;
  benchmarkId: string;
  model: string;
  logDir: string;
  settings: EvalSettings;
  onProgress?: (completed: number, total: number) => void;
}

export interface EvalRunnerResult {
  success: boolean;
  error?: string;
  cancelled?: boolean;
}

export async function runEval(options: EvalRunnerOptions): Promise<EvalRunnerResult> {
  const { benchmarkId, model, logDir, settings, onProgress } = options;

  const benchmark = getBenchmark(benchmarkId);
  if (!benchmark) {
    return { success: false, error: `Unknown benchmark: ${benchmarkId}` };
  }

  // Ensure log directory exists
  mkdirSync(logDir, { recursive: true });

  // Build inspect eval command
  const args = [
    "inspect",
    "eval",
    benchmark.modulePath,
    "--model",
    model,
    "--log-dir",
    logDir,
    "--epochs",
    String(settings.epochs),
    "--max-connections",
    String(settings.maxConnections),
    "--log-format",
    "json",
    "--display",
    "none",
    "--log-realtime",
  ];

  if (settings.logSamples) {
    args.push("--log-samples");
  }

  if (settings.limit != null) {
    args.push("--limit", String(settings.limit));
  }

  // Spawn subprocess
  const proc = Bun.spawn(args, {
    cwd: process.cwd(),
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env },
  });

  let cancelled = false;

  // Forward SIGINT to subprocess
  const sigintHandler = () => {
    cancelled = true;
    proc.kill("SIGINT");
  };
  process.on("SIGINT", sigintHandler);

  // Progress tracking via fs.watch + polling fallback
  async function scanProgress(): Promise<void> {
    try {
      const logFiles = await listEvalLogs(logDir);
      for (const logFile of logFiles) {
        const header = await readEvalLogHeader(logFile);
        if (header && header.totalSamples != null && header.completedSamples != null) {
          onProgress?.(header.completedSamples, header.totalSamples);
        }
      }
    } catch {
      // Ignore scan errors during progress tracking
    }
  }

  let watcher: ReturnType<typeof watch> | null = null;
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  if (onProgress) {
    try {
      watcher = watch(logDir, { recursive: true }, (_event, filename) => {
        if (filename?.endsWith(".json")) {
          void scanProgress();
        }
      });
    } catch {
      // fs.watch may not be available on all platforms
    }

    pollInterval = setInterval(() => {
      void scanProgress();
    }, 2000);
  }

  // Wait for subprocess to exit
  const exitCode = await proc.exited;

  // Cleanup
  process.off("SIGINT", sigintHandler);
  if (watcher) {
    watcher.close();
  }
  if (pollInterval) {
    clearInterval(pollInterval);
  }

  // Final progress scan
  if (onProgress) {
    await scanProgress();
  }

  if (cancelled) {
    return { success: false, cancelled: true };
  }

  if (exitCode !== 0) {
    let stderrText = "";
    try {
      stderrText = await new Response(proc.stderr).text();
    } catch {
      // Ignore stderr read errors
    }
    return {
      success: false,
      error: stderrText || `inspect eval exited with code ${exitCode}`,
    };
  }

  return { success: true };
}
