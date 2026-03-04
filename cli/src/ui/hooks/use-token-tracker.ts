import { useState, useCallback } from "react";
import type { TokenUsage } from "../types.js";
import { pricing } from "../theme.js";

export function useTokenTracker() {
  const [usage, setUsage] = useState<TokenUsage>({
    inputTokens: 0,
    outputTokens: 0,
    totalCost: 0,
  });

  const addUsage = useCallback((input: number, output: number) => {
    setUsage((prev) => {
      const inputTokens = prev.inputTokens + input;
      const outputTokens = prev.outputTokens + output;
      const totalCost =
        (inputTokens / 1000) * pricing.inputPer1k +
        (outputTokens / 1000) * pricing.outputPer1k;
      return { inputTokens, outputTokens, totalCost };
    });
  }, []);

  return { usage, addUsage };
}
