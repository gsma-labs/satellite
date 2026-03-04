import type { BenchmarkConfig } from "../types/index.js";

export const BENCHMARKS: BenchmarkConfig[] = [
  {
    id: "teleqna",
    name: "TeleQnA",
    modulePath: "evals.teleqna.teleqna",
    samples: 1000,
    hfColumn: "teleqna",
  },
  {
    id: "telelogs",
    name: "TeleLogs",
    modulePath: "evals.telelogs.telelogs",
    samples: 100,
    hfColumn: "telelogs",
  },
  {
    id: "telemath",
    name: "TeleMath",
    modulePath: "evals.telemath.telemath",
    samples: 100,
    hfColumn: "telemath",
  },
  {
    id: "teletables",
    name: "TeleTables",
    modulePath: "evals.teletables.teletables",
    samples: 100,
    hfColumn: "teletables",
  },
  {
    id: "three_gpp",
    name: "3GPP",
    modulePath: "evals.three_gpp.three_gpp",
    samples: 100,
    hfColumn: "3gpp_tsg",
  },
  {
    id: "oranbench",
    name: "ORANBench",
    modulePath: "evals.oranbench.oranbench",
    samples: 150,
    hfColumn: "oranbench",
  },
  {
    id: "srsranbench",
    name: "srsRANBench",
    modulePath: "evals.srsranbench.srsranbench",
    samples: 150,
    hfColumn: "srsranbench",
  },
];

export const BENCHMARKS_BY_ID: Record<string, BenchmarkConfig> =
  Object.fromEntries(BENCHMARKS.map((b) => [b.id, b]));

export function getBenchmark(id: string): BenchmarkConfig | undefined {
  return BENCHMARKS_BY_ID[id];
}
