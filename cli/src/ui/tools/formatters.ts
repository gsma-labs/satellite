export function formatToolResult(toolName: string, resultJson: string): string {
  try {
    const data = JSON.parse(resultJson);
    switch (toolName) {
      case "list_benchmarks":
        return formatBenchmarks(data);
      case "run_eval":
        return formatEvalResult(data);
      default:
        return resultJson;
    }
  } catch {
    return resultJson;
  }
}

function formatBenchmarks(
  data: Array<{ id: string; name: string; samples: number }>,
): string {
  return data
    .map((b) => `${b.name} (${b.id}) — ${b.samples} samples`)
    .join("\n");
}

function formatEvalResult(data: {
  benchmark?: string;
  model?: string;
  score?: number;
  stderr?: number;
  samples?: number;
}): string {
  const parts: string[] = [];
  if (data.score != null) {
    let scoreStr = `Score: ${data.score}%`;
    if (data.stderr != null) {
      scoreStr += ` (±${data.stderr}%)`;
    }
    parts.push(scoreStr);
  }
  if (data.samples != null) {
    parts.push(`${data.samples} samples`);
  }
  if (data.model) {
    parts.push(`Model: ${data.model}`);
  }
  return parts.join(" | ") || "Evaluation completed";
}
