import { join } from "node:path";
import { BENCHMARKS, BENCHMARKS_BY_ID } from "./benchmark-registry.js";
import { normalizeModelPath } from "./config-manager.js";
import { buildModelCardParquet } from "./parquet-builder.js";
import { GitHubClient } from "./github-client.js";
import { getJobResults, getJobSampleCounts } from "./job-manager.js";
import { readEvalLogHeader, listEvalLogs } from "./eval-log-reader.js";
import { SatelliteError } from "../utils/errors.js";
import type { SubmitResult } from "../types/index.js";

const LEADERBOARD_REPO = "gsma-labs/leaderboard";
const REQUIRED_BENCHMARK_IDS = new Set(BENCHMARKS.map((b) => b.id));
const REQUIRED_SAMPLE_COUNTS = Object.fromEntries(BENCHMARKS.map((b) => [b.id, b.samples]));

const UNSAFE_CHARS = /[^a-z0-9_-]/g;

export function parseModelIdentity(modelString: string): { provider: string; modelName: string } {
  const normalized = normalizeModelPath(modelString);
  const slashIdx = normalized.indexOf("/");
  if (slashIdx === -1 || slashIdx === normalized.length - 1) {
    throw new SatelliteError(`Invalid model format: ${modelString}`, "INVALID_ARGS");
  }
  const provider = normalized.slice(0, slashIdx);
  const modelName = normalized.slice(slashIdx + 1);
  return { provider, modelName };
}

export function modelDirName(provider: string, modelName: string): string {
  const raw = `${provider}_${modelName}`.replace(/\./g, "_").replace(/\//g, "_");
  return raw.toLowerCase().replace(UNSAFE_CHARS, "");
}

export function isModelEligible(
  scores: Record<string, number>,
  sampleCounts: Record<string, number>,
): boolean {
  for (const benchId of REQUIRED_BENCHMARK_IDS) {
    if (!(benchId in scores)) return false;
    if ((sampleCounts[benchId] ?? 0) < REQUIRED_SAMPLE_COUNTS[benchId]) return false;
  }
  return true;
}

async function collectStderr(
  jobsDir: string,
  jobId: string,
  model: string,
): Promise<Record<string, number>> {
  const jobDir = join(jobsDir, jobId);
  const logFiles = await listEvalLogs(jobDir);
  const stderrMap: Record<string, number> = {};

  for (const logFile of logFiles) {
    const log = await readEvalLogHeader(logFile);
    if (!log || log.evalModel !== model) continue;
    if (log.stderr != null) {
      stderrMap[log.taskName] = log.stderr;
    }
  }

  return stderrMap;
}

export async function submitToLeaderboard(
  jobId: string,
  model: string,
  token: string,
  jobsDir: string,
): Promise<SubmitResult> {
  // 1. Parse model identity
  const { provider, modelName } = parseModelIdentity(model);
  const dirName = modelDirName(provider, modelName);

  // 2. Get scores from job
  const scores = await getJobResults(jobsDir, jobId);
  const sampleCounts = await getJobSampleCounts(jobsDir, jobId);
  const modelScores = scores[model] ?? {};
  const modelSampleCounts = sampleCounts[model] ?? {};

  // 3. Check eligibility
  if (!isModelEligible(modelScores, modelSampleCounts)) {
    throw new SatelliteError(
      "Model is not eligible: missing benchmarks or insufficient samples",
      "SUBMIT_ERROR",
    );
  }

  // 4. Collect stderr values from eval logs
  const stderrValues = await collectStderr(jobsDir, jobId, model);

  // 5. Build parquet
  const benchmarkScores = new Map<string, { score: number; stderr: number }>();
  for (const [benchId, score] of Object.entries(modelScores)) {
    benchmarkScores.set(benchId, {
      score,
      stderr: stderrValues[benchId] ?? 0,
    });
  }

  const providerDisplay = provider.charAt(0).toUpperCase() + provider.slice(1);
  const { remotePath, parquetBytes } = await buildModelCardParquet(
    modelName,
    providerDisplay,
    dirName,
    benchmarkScores,
  );

  // 6. Submit via GitHub
  const client = new GitHubClient(token);
  const username = await client.checkAuth();
  const canPush = await client.hasPushAccess(LEADERBOARD_REPO);
  const baseSha = await client.getDefaultBranchSha(LEADERBOARD_REPO);

  const timestamp = new Date()
    .toISOString()
    .replace(/[-:T]/g, "")
    .slice(0, 15);
  const branchName = `submit/${dirName}/${timestamp}`;

  const targetRepo = canPush
    ? LEADERBOARD_REPO
    : await client.ensureFork(LEADERBOARD_REPO);
  await client.createBranch(targetRepo, branchName, baseSha);
  await client.uploadFiles(targetRepo, branchName, [
    { path: remotePath, content: parquetBytes },
  ]);

  // Build PR body
  const scoreLines = Object.entries(modelScores)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([benchId, score]) => {
      const bench = BENCHMARKS_BY_ID[benchId];
      return `| ${bench?.name ?? benchId} | ${score.toFixed(4)} |`;
    });

  const title = `Add ${providerDisplay}/${dirName} evaluation results`;
  const body = [
    `## Submission: ${model}`,
    `**Provider:** ${providerDisplay}`,
    `**Job ID:** ${jobId}`,
    "",
    "### Benchmark Scores",
    "",
    "| Benchmark | Score |",
    "|-----------|-------|",
    ...scoreLines,
    "",
    "---",
    "*Submitted via Satellite CLI*",
  ].join("\n");

  const head = canPush ? branchName : `${username}:${branchName}`;
  const prUrl = await client.createPR(LEADERBOARD_REPO, head, title, body);

  return { prUrl, branch: branchName, model };
}
