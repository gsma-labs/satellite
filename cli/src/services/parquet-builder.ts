import { ParquetWriter, ParquetSchema } from "@dsnp/parquetjs";
import type { SchemaDefinition } from "@dsnp/parquetjs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readFile, unlink } from "node:fs/promises";
import { BENCHMARKS } from "./benchmark-registry.js";

const SCORE_COLUMNS = BENCHMARKS.map((b) => b.id);
const MODEL_CARDS_DIR = "model_cards";

const _PATH_TRAVERSAL_PATTERNS = ["..", "/", "\\"];

function validateSafePathComponent(name: string): string {
  for (const pattern of _PATH_TRAVERSAL_PATTERNS) {
    if (name.includes(pattern)) {
      throw new Error(`Unsafe character in model directory name: ${name}`);
    }
  }
  return name;
}

export interface ParquetBuildResult {
  remotePath: string;
  parquetBytes: Buffer;
}

export async function buildModelCardParquet(
  modelName: string,
  provider: string,
  modelDirName: string,
  benchmarkScores: Map<string, { score: number; stderr: number }>,
): Promise<ParquetBuildResult> {
  const safeDirName = validateSafePathComponent(modelDirName);

  // Build schema — all UTF8
  const schemaFields: SchemaDefinition = {
    model: { type: "UTF8" },
    provider: { type: "UTF8" },
  };
  for (const col of SCORE_COLUMNS) {
    schemaFields[col] = { type: "UTF8", optional: true };
  }
  schemaFields.date = { type: "UTF8" };

  const schema = new ParquetSchema(schemaFields);

  // Build row
  const row: Record<string, string | null> = {
    model: modelName,
    provider: provider,
  };
  for (const col of SCORE_COLUMNS) {
    const entry = benchmarkScores.get(col);
    row[col] = entry
      ? `[${entry.score.toFixed(6)}, ${entry.stderr.toFixed(6)}]`
      : null;
  }
  row.date = new Date().toISOString().split("T")[0];

  // Write to temp file, then read back as Buffer
  const tmpPath = join(tmpdir(), `satellite-${Date.now()}-${Math.random().toString(36).slice(2)}.parquet`);
  const writer = await ParquetWriter.openFile(schema, tmpPath);
  await writer.appendRow(row);
  await writer.close();

  const parquetBytes = Buffer.from(await readFile(tmpPath));
  await unlink(tmpPath);

  const remotePath = `${MODEL_CARDS_DIR}/${safeDirName}.parquet`;
  return { remotePath, parquetBytes };
}
