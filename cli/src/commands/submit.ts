import type { CLIArgs } from "../types/index.js";
import { emitJSON } from "../utils/output.js";
import { exitWithError } from "../utils/errors.js";
import { submitToLeaderboard } from "../services/submit-service.js";
import { resolveJobsDir, loadJob } from "../services/job-manager.js";
import { join } from "node:path";

export async function submitCommand(cli: CLIArgs): Promise<void> {
  const jobId = cli.flags["job"];
  const model = cli.flags["model"];
  const token = cli.flags["token"] ?? process.env.GITHUB_TOKEN;

  if (typeof jobId !== "string") exitWithError("--job is required", "INVALID_ARGS");
  if (typeof model !== "string") exitWithError("--model is required", "INVALID_ARGS");
  if (typeof token !== "string")
    exitWithError("--token or GITHUB_TOKEN env required", "CONFIG_ERROR");

  const jobsDir = resolveJobsDir(
    typeof cli.flags["jobs-dir"] === "string" ? cli.flags["jobs-dir"] : undefined,
  );

  // Verify job exists and is completed
  const job = await loadJob(join(jobsDir, jobId));
  if (!job) exitWithError(`Job not found: ${jobId}`, "NOT_FOUND");
  if (job!.status !== "completed")
    exitWithError(`Job ${jobId} not completed (${job!.status})`, "EVAL_ERROR");

  try {
    const result = await submitToLeaderboard(jobId, model, token, jobsDir);
    emitJSON(result);
  } catch (err) {
    exitWithError(err instanceof Error ? err.message : String(err), "SUBMIT_ERROR");
  }
}
