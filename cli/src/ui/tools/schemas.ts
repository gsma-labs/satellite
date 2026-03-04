import type Anthropic from "@anthropic-ai/sdk";

export const TOOL_SCHEMAS: Anthropic.Tool[] = [
  {
    name: "list_benchmarks",
    description:
      "List all available telecom LLM benchmarks with their IDs, names, and sample counts.",
    input_schema: {
      type: "object" as const,
      properties: {},
      required: [],
    },
  },
  {
    name: "run_eval",
    description:
      "Run a benchmark evaluation on a specified model. Returns the job ID, score, and sample count when complete.",
    input_schema: {
      type: "object" as const,
      properties: {
        benchmark_id: {
          type: "string",
          description:
            "The benchmark ID to run (e.g., 'teleqna', 'telelogs', 'telemath', 'teletables', 'three_gpp', 'oranbench', 'srsranbench')",
        },
        model: {
          type: "string",
          description:
            "The model to evaluate (e.g., 'openai/gpt-4o', 'anthropic/claude-sonnet-4-20250514')",
        },
        limit: {
          type: "number",
          description:
            "Optional: limit the number of samples to evaluate (useful for quick tests)",
        },
      },
      required: ["benchmark_id", "model"],
    },
  },
];
