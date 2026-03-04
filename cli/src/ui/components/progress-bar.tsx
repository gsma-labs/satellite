import { Text } from "ink";
import { symbols, colors } from "../theme.js";

interface ProgressBarProps {
  completed: number;
  total: number;
  width?: number;
}

export function ProgressBar({ completed, total, width = 20 }: ProgressBarProps) {
  const ratio = total > 0 ? Math.min(completed / total, 1) : 0;
  const filled = Math.round(ratio * width);
  const empty = width - filled;
  const pct = Math.round(ratio * 100);

  return (
    <Text>
      <Text color={colors.success}>{symbols.progressFilled.repeat(filled)}</Text>
      <Text color={colors.dim}>{symbols.progressEmpty.repeat(empty)}</Text>
      <Text color={colors.dim}> {completed}/{total} ({pct}%)</Text>
    </Text>
  );
}
