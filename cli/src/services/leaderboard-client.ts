import type { LeaderboardEntry, LeaderboardScore } from "../types/index.js";
import { BENCHMARKS } from "./benchmark-registry.js";

const CSV_URL =
  "https://huggingface.co/datasets/GSMA/leaderboard/resolve/main/leaderboard_scores.csv";

/**
 * Parse a CSV score cell.
 *
 * Values are string-encoded lists like `"[0.852, 0.0112]"` where the first
 * element is the accuracy in 0-1 range.  Returns a LeaderboardScore (percentage)
 * or null.
 */
function parseCsvScore(raw: string): LeaderboardScore | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    // Maybe a plain number
    const num = Number(trimmed);
    if (!Number.isFinite(num)) return null;
    return { score: num * 100 };
  }

  if (Array.isArray(parsed)) {
    if (parsed.length === 0) return null;
    const val = Number(parsed[0]);
    if (!Number.isFinite(val)) return null;
    const stderr =
      parsed.length > 1 && parsed[1] != null
        ? Number(parsed[1]) * 100
        : undefined;
    return {
      score: val * 100,
      stderr: stderr != null && Number.isFinite(stderr) ? stderr : undefined,
    };
  }

  // Scalar JSON value
  const val = Number(parsed);
  if (!Number.isFinite(val)) return null;
  return { score: val * 100 };
}

/**
 * Split a CSV line into fields, respecting double-quoted values that may
 * contain commas (e.g. `"[0.852, 0.0112]"`).
 */
function splitCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === "," && !inQuotes) {
      fields.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  fields.push(current);
  return fields;
}

/**
 * Parse CSV text into rows of key-value pairs (simple DictReader equivalent).
 * Handles quoted fields containing commas.
 */
function parseCsv(text: string): Record<string, string>[] {
  const lines = text.split("\n").filter((l) => l.trim().length > 0);
  if (lines.length === 0) return [];

  const headers = splitCsvLine(lines[0]).map((h) => h.trim());
  const rows: Record<string, string>[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = splitCsvLine(lines[i]);
    const row: Record<string, string> = {};
    for (let j = 0; j < headers.length; j++) {
      row[headers[j]] = (values[j] ?? "").trim();
    }
    rows.push(row);
  }

  return rows;
}

/**
 * Parse a single CSV row into a LeaderboardEntry.
 */
function parseRow(
  row: Record<string, string>,
  scoreCols: string[],
): LeaderboardEntry {
  const model = row["model"]?.trim() || "Unknown";
  const provider = row["provider"]?.trim() || undefined;
  const date = row["date"]?.trim() || undefined;

  const scores: Record<string, LeaderboardScore> = {};
  for (const col of scoreCols) {
    const parsed = parseCsvScore(row[col] ?? "");
    if (parsed) {
      scores[col] = parsed;
    }
  }

  return { model, provider, scores, date };
}

/**
 * Compute average score across all benchmarks for an entry.
 */
function avgScore(entry: LeaderboardEntry): number | null {
  const values = Object.values(entry.scores).map((s) => s.score);
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/**
 * Fetch the remote leaderboard from the GSMA/leaderboard HuggingFace dataset.
 * Returns entries sorted by average score descending.
 */
export async function fetchLeaderboard(): Promise<LeaderboardEntry[]> {
  const response = await fetch(CSV_URL);
  if (!response.ok) {
    throw new Error(
      `Failed to fetch leaderboard: ${response.status} ${response.statusText}`,
    );
  }
  const text = await response.text();
  const rows = parseCsv(text);

  // CSV columns match benchmark IDs (e.g. "three_gpp"), not hfColumn
  const availableCols = new Set(Object.keys(rows[0] ?? {}));
  const scoreCols = BENCHMARKS.map((b) => b.id).filter((id) =>
    availableCols.has(id),
  );

  const entries = rows.map((row) => parseRow(row, scoreCols));

  // Sort by average score descending; entries with no scores go last
  entries.sort((a, b) => {
    const aAvg = avgScore(a);
    const bAvg = avgScore(b);
    if (aAvg === null && bAvg === null) return 0;
    if (aAvg === null) return 1;
    if (bAvg === null) return -1;
    return bAvg - aAvg;
  });

  return entries;
}
