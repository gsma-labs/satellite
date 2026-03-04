import { Box, Text } from "ink";
import type { TokenUsage } from "../types.js";
import { colors, symbols } from "../theme.js";

interface StatusBarProps {
  model: string;
  usage: TokenUsage;
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function formatCost(cost: number): string {
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(3)}`;
}

export function StatusBar({ model, usage }: StatusBarProps) {
  const sep = ` ${symbols.separator} `;

  return (
    <Box>
      <Text color={colors.dim}>
        {model}
        {sep}
        {"↑"}{formatTokens(usage.inputTokens)} {"↓"}{formatTokens(usage.outputTokens)}
        {sep}
        {formatCost(usage.totalCost)}
      </Text>
    </Box>
  );
}
