import { useState, useRef, useCallback } from "react";
import Anthropic from "@anthropic-ai/sdk";
import type { ConversationState, DisplayMessage, ToolCallDisplay } from "../types.js";
import { toolVerbs, pricing } from "../theme.js";
import { formatToolResult } from "../tools/formatters.js";

const SYSTEM_PROMPT = `You are Satellite, an AI assistant for running telecom LLM benchmarks. You have tools to list benchmarks and run evaluations. Be concise and helpful.

When the user asks about available benchmarks, use the list_benchmarks tool.
When the user asks to run a benchmark, use the run_eval tool with the appropriate benchmark_id and model.
For quick tests, suggest using limit parameter (e.g., limit: 5).`;

interface UseConversationOptions {
  toolSchemas: Anthropic.Tool[];
  executeTool: (
    name: string,
    params: Record<string, unknown>,
    onProgress?: (completed: number, total: number) => void,
  ) => Promise<string>;
  onUsage: (input: number, output: number) => void;
}

interface UseConversationReturn {
  state: ConversationState;
  sendMessage: (text: string) => void;
}

const INITIAL_STATE: ConversationState = {
  finalizedMessages: [],
  streamingText: "",
  activeToolCalls: [],
  isStreaming: false,
  isToolRunning: false,
  error: null,
};

export function useConversation({
  toolSchemas,
  executeTool,
  onUsage,
}: UseConversationOptions): UseConversationReturn {
  const [state, setState] = useState<ConversationState>(INITIAL_STATE);
  const apiMessages = useRef<Anthropic.MessageParam[]>([]);
  const clientRef = useRef<Anthropic | null>(null);

  function getClient(): Anthropic {
    if (!clientRef.current) {
      clientRef.current = new Anthropic();
    }
    return clientRef.current;
  }

  const streamResponse = useCallback(async () => {
    const client = getClient();

    let accumulatedText = "";
    const pendingToolCalls: ToolCallDisplay[] = [];

    try {
      const stream = client.messages.stream({
        model: pricing.model,
        max_tokens: 4096,
        system: SYSTEM_PROMPT,
        messages: apiMessages.current,
        tools: toolSchemas,
      });

      stream.on("text", (text) => {
        accumulatedText += text;
        setState((prev) => ({
          ...prev,
          streamingText: accumulatedText,
        }));
      });

      stream.on("contentBlock", (block) => {
        if (block.type === "tool_use") {
          const verbs = toolVerbs[block.name] ?? {
            verb: `Running ${block.name}...`,
            pastTense: `Ran ${block.name}`,
          };
          const tc: ToolCallDisplay = {
            id: block.id,
            toolName: block.name,
            params: block.input as Record<string, unknown>,
            status: "running",
            verb: verbs.verb,
            pastTense: verbs.pastTense,
          };
          pendingToolCalls.push(tc);
          setState((prev) => ({
            ...prev,
            activeToolCalls: [...prev.activeToolCalls, tc],
          }));
        }
      });

      const response = await stream.finalMessage();

      // Track token usage
      onUsage(response.usage.input_tokens, response.usage.output_tokens);

      // Push assistant message to API history
      apiMessages.current.push({
        role: "assistant",
        content: response.content,
      });

      if (response.stop_reason === "tool_use") {
        // Execute tool calls
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          isToolRunning: true,
        }));

        for (const block of response.content) {
          if (block.type !== "tool_use") continue;

          const onProgress = (completed: number, total: number) => {
            setState((prev) => ({
              ...prev,
              activeToolCalls: prev.activeToolCalls.map((tc) =>
                tc.id === block.id
                  ? { ...tc, progress: { completed, total } }
                  : tc,
              ),
            }));
          };

          try {
            const result = await executeTool(
              block.name,
              block.input as Record<string, unknown>,
              onProgress,
            );

            const displayResult = formatToolResult(block.name, result);

            setState((prev) => ({
              ...prev,
              activeToolCalls: prev.activeToolCalls.map((tc) =>
                tc.id === block.id
                  ? { ...tc, status: "completed", result: displayResult }
                  : tc,
              ),
            }));

            apiMessages.current.push({
              role: "user",
              content: [
                {
                  type: "tool_result",
                  tool_use_id: block.id,
                  content: result,
                },
              ],
            });
          } catch (err) {
            const errorMsg =
              err instanceof Error ? err.message : String(err);

            setState((prev) => ({
              ...prev,
              activeToolCalls: prev.activeToolCalls.map((tc) =>
                tc.id === block.id
                  ? { ...tc, status: "error", error: errorMsg }
                  : tc,
              ),
            }));

            apiMessages.current.push({
              role: "user",
              content: [
                {
                  type: "tool_result",
                  tool_use_id: block.id,
                  content: errorMsg,
                  is_error: true,
                },
              ],
            });
          }
        }

        // Continue the conversation loop
        setState((prev) => ({
          ...prev,
          isStreaming: true,
          isToolRunning: false,
          streamingText: "",
        }));

        await streamResponse();
      } else {
        // End of conversation turn — finalize
        setState((prev) => {
          const assistantMsg: DisplayMessage = {
            id: crypto.randomUUID(),
            role: "assistant",
            text: accumulatedText,
            toolCalls:
              prev.activeToolCalls.length > 0
                ? [...prev.activeToolCalls]
                : undefined,
            timestamp: Date.now(),
          };

          return {
            ...prev,
            finalizedMessages: [...prev.finalizedMessages, assistantMsg],
            streamingText: "",
            activeToolCalls: [],
            isStreaming: false,
            isToolRunning: false,
          };
        });
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setState((prev) => ({
        ...prev,
        isStreaming: false,
        isToolRunning: false,
        error: errorMsg,
      }));
    }
  }, [toolSchemas, executeTool, onUsage]);

  const sendMessage = useCallback(
    (text: string) => {
      // Add user message to API history
      apiMessages.current.push({
        role: "user",
        content: text,
      });

      // Add to display and start streaming
      const userMsg: DisplayMessage = {
        id: crypto.randomUUID(),
        role: "user",
        text,
        timestamp: Date.now(),
      };

      setState((prev) => ({
        ...prev,
        finalizedMessages: [...prev.finalizedMessages, userMsg],
        streamingText: "",
        activeToolCalls: [],
        isStreaming: true,
        error: null,
      }));

      // Fire and forget — stream handles its own state
      void streamResponse();
    },
    [streamResponse],
  );

  return { state, sendMessage };
}
