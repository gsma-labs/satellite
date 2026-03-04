import type { ErrorCode } from "../types/index.js";

export class SatelliteError extends Error {
  constructor(
    message: string,
    public code: ErrorCode,
    public cause?: unknown
  ) {
    super(message);
    this.name = "SatelliteError";
  }

  toJSON() {
    return { error: this.message, code: this.code };
  }
}

export function exitWithError(message: string, code: ErrorCode): never {
  process.stderr.write(JSON.stringify({ error: message, code }) + "\n");
  process.exit(1);
}
