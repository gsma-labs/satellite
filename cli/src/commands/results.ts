import type { CLIArgs } from "../types/index.js";
import { emitJSON } from "../utils/output.js";
import { exitWithError } from "../utils/errors.js";
import {
  resolveJobsDir,
  loadJob,
  getJobResults,
  getJobSampleCounts,
} from "../services/job-manager.js";
import { join } from "node:path";

export async function resultsCommand(cli: CLIArgs): Promise<void> {
  const jobsDir = resolveJobsDir(
    typeof cli.flags["jobs-dir"] === "string" ? cli.flags["jobs-dir"] : undefined
  );
  const jobId = cli.flags["job"];

  if (typeof jobId !== "string") {
    exitWithError("--job JOB_ID is required for the results command", "INVALID_ARGS");
  }

  const jobDir = join(jobsDir, jobId);
  const job = await loadJob(jobDir);

  if (!job) {
    exitWithError(`Job not found: ${jobId}`, "NOT_FOUND");
  }

  if (job.status !== "completed") {
    exitWithError(
      `Job ${jobId} is not completed (status: ${job.status})`,
      "EVAL_ERROR"
    );
  }

  const scores = await getJobResults(jobsDir, jobId);
  const sampleCounts = await getJobSampleCounts(jobsDir, jobId);

  emitJSON({
    jobId: job.jobId,
    status: job.status,
    createdAt: job.createdAt,
    completedAt: job.completedAt,
    results: scores,
    sampleCounts,
  });
}
