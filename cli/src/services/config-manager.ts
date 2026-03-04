import { existsSync, readFileSync } from "node:fs";
import { writeFileSync, mkdirSync, openSync, writeSync, closeSync, constants } from "node:fs";
import { dirname, resolve } from "node:path";
import { homedir } from "node:os";
import type { EvalSettings } from "../types/index.js";

// ── Eval Settings ─────────────────────────────────────────────────────

const DEFAULT_SETTINGS_PATH = resolve(homedir(), ".satellite", "eval_settings.json");

const DEFAULT_EVAL_SETTINGS: EvalSettings = {
  epochs: 1,
  maxConnections: 10,
  logSamples: true,
};

export function loadEvalSettings(path?: string): EvalSettings {
  const settingsPath = path ?? DEFAULT_SETTINGS_PATH;
  if (!existsSync(settingsPath)) {
    return { ...DEFAULT_EVAL_SETTINGS };
  }
  try {
    const raw = readFileSync(settingsPath, "utf-8");
    const data = JSON.parse(raw) as Record<string, unknown>;
    return {
      epochs: typeof data.epochs === "number" ? data.epochs : DEFAULT_EVAL_SETTINGS.epochs,
      maxConnections:
        typeof data.maxConnections === "number"
          ? data.maxConnections
          : DEFAULT_EVAL_SETTINGS.maxConnections,
      logSamples:
        typeof data.logSamples === "boolean" ? data.logSamples : DEFAULT_EVAL_SETTINGS.logSamples,
      ...(typeof data.limit === "number" ? { limit: data.limit } : {}),
    };
  } catch {
    return { ...DEFAULT_EVAL_SETTINGS };
  }
}

export function saveEvalSettings(settings: EvalSettings, path?: string): void {
  const settingsPath = path ?? DEFAULT_SETTINGS_PATH;
  const dir = dirname(settingsPath);
  mkdirSync(dir, { recursive: true });
  writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + "\n", "utf-8");
}

// ── .env File Handling ────────────────────────────────────────────────

/**
 * Parse a .env file into a Record<string, string>.
 * Handles single-quoted, double-quoted, and unquoted values.
 * Skips empty lines and comments.
 */
export function loadEnvFile(envPath: string): Record<string, string> {
  if (!existsSync(envPath)) {
    return {};
  }
  const content = readFileSync(envPath, "utf-8");
  const vars: Record<string, string> = {};

  for (const rawLine of content.split("\n")) {
    const line = rawLine.trim();
    // Skip empty lines and comments
    if (!line || line.startsWith("#")) {
      continue;
    }
    const eqIndex = line.indexOf("=");
    if (eqIndex === -1) {
      continue;
    }
    const key = line.slice(0, eqIndex).trim();
    let value = line.slice(eqIndex + 1).trim();

    // Strip surrounding quotes
    if (value.length >= 2) {
      if (value.startsWith("'") && value.endsWith("'")) {
        value = value.slice(1, -1);
      } else if (value.startsWith('"') && value.endsWith('"')) {
        // Unescape double-quoted values
        value = value
          .slice(1, -1)
          .replace(/\\"/g, '"')
          .replace(/\\\$/g, "$")
          .replace(/\\\\/g, "\\");
      }
    }

    vars[key] = value;
  }

  return vars;
}

/**
 * Format a value for writing to a .env file.
 * Uses single quotes if the value contains no single quotes,
 * otherwise double-quotes with escaping.
 */
function formatEnvValue(value: string): string {
  if (value.includes("\n") || value.includes("\r")) {
    throw new Error("Environment variable values cannot contain newlines");
  }
  if (!value.includes("'")) {
    return `'${value}'`;
  }
  // Double-quote: escape \, $, "
  const escaped = value
    .replace(/\\/g, "\\\\")
    .replace(/\$/g, "\\$")
    .replace(/"/g, '\\"');
  return `"${escaped}"`;
}

/**
 * Write environment variables to a .env file with 0o600 permissions.
 * Uses O_CREAT to avoid TOCTOU race.
 */
export function writeEnvFile(envPath: string, vars: Record<string, string>): void {
  const dir = dirname(envPath);
  mkdirSync(dir, { recursive: true });

  const lines = Object.entries(vars).map(([key, value]) => `${key}=${formatEnvValue(value)}`);
  const data = lines.join("\n") + "\n";

  const fd = openSync(envPath, constants.O_WRONLY | constants.O_CREAT | constants.O_TRUNC, 0o600);
  try {
    writeSync(fd, data, undefined, "utf-8");
  } finally {
    closeSync(fd);
  }
}

/**
 * Read a single environment variable from a .env file.
 * Returns undefined if not found.
 */
export function getEnvVar(envPath: string, key: string): string | undefined {
  const vars = loadEnvFile(envPath);
  return vars[key];
}

// ── Provider / Model Detection ────────────────────────────────────────

const PROXY_PREFIXES = new Set(["openrouter", "bedrock", "vertex", "azureai"]);

export const PROVIDER_PREFIXES: Record<string, string> = {
  "openai/": "openai",
  "anthropic/": "anthropic",
  "google/": "google",
  "mistral/": "mistral",
  "deepseek/": "deepseek",
  "grok/": "grok",
  "perplexity/": "perplexity",
  "openrouter/": "openrouter",
  "bedrock/": "bedrock",
  "azureai/": "azureai",
  "vertex/": "vertex",
  "groq/": "groq",
  "together/": "together",
  "fireworks/": "fireworks",
  "sambanova/": "sambanova",
  "cf/": "cloudflare",
  "hf-inference-providers/": "hf-inference",
  "ollama/": "ollama",
  "vllm/": "vllm",
  "sglang/": "sglang",
  "llama-cpp-python/": "llama-cpp",
  "hf/": "hf-local",
  "transformerlens/": "transformerlens",
  "nnterp/": "nnterp",
};

/**
 * Strip proxy prefixes (openrouter, bedrock, vertex, azureai) from a model string.
 * e.g. "openrouter/openai/gpt-4o" -> "openai/gpt-4o"
 */
export function normalizeModelPath(modelString: string): string {
  const parts = modelString.toLowerCase().trim().replace(/^\/+|\/+$/g, "").split("/");
  if (parts.length === 0) {
    return modelString;
  }
  if (PROXY_PREFIXES.has(parts[0])) {
    parts.shift();
  }
  return parts.join("/");
}

/**
 * Detect the provider from a model string by matching known prefixes.
 * Returns undefined if no provider matches.
 */
export function detectProvider(modelString: string): string | undefined {
  for (const [prefix, provider] of Object.entries(PROVIDER_PREFIXES)) {
    if (modelString.startsWith(prefix)) {
      return provider;
    }
  }
  return undefined;
}
