/** Write a single JSONL event to stdout (for streaming commands like `run`). */
export function emitEvent(event: Record<string, unknown>): void {
  process.stdout.write(JSON.stringify(event) + "\n");
}

/** Write a JSON response to stdout (for one-shot commands). */
export function emitJSON(data: unknown): void {
  process.stdout.write(JSON.stringify(data, null, 2) + "\n");
}
