// ── Display Types for React Ink UI ─────────────────────────────────

export type MessageRole = "user" | "assistant";

export interface DisplayMessage {
  id: string;
  role: MessageRole;
  text: string;
  toolCalls?: ToolCallDisplay[];
  timestamp: number;
}

export interface ToolCallDisplay {
  id: string;
  toolName: string;
  params: Record<string, unknown>;
  status: "running" | "completed" | "error";
  verb: string;        // "Running evaluation..."
  pastTense: string;   // "Ran evaluation"
  result?: string;
  error?: string;
  progress?: { completed: number; total: number };
}

export interface ConversationState {
  finalizedMessages: DisplayMessage[];
  streamingText: string;
  activeToolCalls: ToolCallDisplay[];
  isStreaming: boolean;
  isToolRunning: boolean;
  error: string | null;
}

export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
  totalCost: number;
}
