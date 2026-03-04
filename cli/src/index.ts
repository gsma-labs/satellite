#!/usr/bin/env bun
import type { CLIArgs } from "./types/index.js";
import { exitWithError } from "./utils/errors.js";

function parseArgs(argv: string[]): CLIArgs {
  const args = argv.slice(2); // skip bun + script
  const command = args[0] ?? "";
  const flags: Record<string, string | boolean> = {};
  const positional: string[] = [];

  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith("--")) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = true;
      }
    } else {
      positional.push(arg);
    }
  }

  return { command, flags, positional };
}

async function main() {
  const cli = parseArgs(process.argv);

  // Interactive mode: no command + TTY + not JSON mode
  const isInteractive = !cli.command && process.stdout.isTTY && !cli.flags.json;
  if (isInteractive) {
    const { startUI } = await import("./ui/main.js");
    return startUI();
  }

  switch (cli.command) {
    case "benchmarks": {
      const { benchmarksCommand } = await import("./commands/benchmarks.js");
      return benchmarksCommand();
    }
    case "status": {
      const { statusCommand } = await import("./commands/status.js");
      return statusCommand(cli);
    }
    case "results": {
      const { resultsCommand } = await import("./commands/results.js");
      return resultsCommand(cli);
    }
    case "leaderboard": {
      const { leaderboardCommand } = await import("./commands/leaderboard.js");
      return leaderboardCommand();
    }
    case "run": {
      const { runCommand } = await import("./commands/run.js");
      return runCommand(cli);
    }
    case "submit": {
      const { submitCommand } = await import("./commands/submit.js");
      return submitCommand(cli);
    }
    default:
      exitWithError(
        `Unknown command: "${cli.command}". Available: benchmarks, status, results, leaderboard, run, submit`,
        "INVALID_ARGS"
      );
  }
}

main().catch((err) => {
  exitWithError(
    err instanceof Error ? err.message : String(err),
    "EVAL_ERROR"
  );
});
