import { BENCHMARKS } from "../services/benchmark-registry.js";
import { emitJSON } from "../utils/output.js";

export function benchmarksCommand(): void {
  emitJSON(
    BENCHMARKS.map((b) => ({
      id: b.id,
      name: b.name,
      samples: b.samples,
      modulePath: b.modulePath,
    }))
  );
}
