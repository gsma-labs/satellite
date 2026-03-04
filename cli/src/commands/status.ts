import type { CLIArgs } from "../types/index.js";
import { emitJSON } from "../utils/output.js";
import { exitWithError } from "../utils/errors.js";
import { resolveJobsDir, listJobs, loadJob } from "../services/job-manager.js";
import { join } from "node:path";

export async function statusCommand(cli: CLIArgs): Promise<void> {
  const jobsDir = resolveJobsDir(
    typeof cli.flags["jobs-dir"] === "string" ? cli.flags["jobs-dir"] : undefined
  );
  const jobId = cli.flags["job"];

  if (typeof jobId === "string") {
    // Single job detail
    const jobDir = join(jobsDir, jobId);
    const job = await loadJob(jobDir);
    if (!job) {
      exitWithError(`Job not found: ${jobId}`, "NOT_FOUND");
    }
    emitJSON(job);
  } else {
    // List all jobs
    const jobs = await listJobs(jobsDir);
    emitJSON(jobs);
  }
}
