import { Box, Text } from "ink";
import type { ToolCallDisplay } from "../types.js";
import { colors, symbols } from "../theme.js";
import { Spinner } from "./spinner.js";
import { ProgressBar } from "./progress-bar.js";

interface ToolCallPanelProps {
  toolCall: ToolCallDisplay;
}

const MAX_RESULT_LENGTH = 120;

function truncate(str: string, max: number): string {
  if (str.length <= max) return str;
  return str.slice(0, max) + "...";
}

export function ToolCallPanel({ toolCall }: ToolCallPanelProps) {
  const { toolName, params, status, verb, pastTense, result, error, progress } = toolCall;

  let borderColor: string;
  if (status === "running") borderColor = colors.toolBorder;
  else if (status === "error") borderColor = colors.error;
  else borderColor = colors.dim;

  return (
    <Box
      borderStyle="round"
      borderColor={borderColor}
      flexDirection="column"
      paddingLeft={1}
      paddingRight={1}
    >
      <Box>
        {status === "running" && <Spinner label={verb} />}
        {status === "completed" && (
          <Text color={colors.success}>{symbols.toolCompleted} {pastTense}</Text>
        )}
        {status === "error" && (
          <Text color={colors.error}>{symbols.toolError} {error ?? "Unknown error"}</Text>
        )}
      </Box>

      <Text color={colors.dim}>{toolName}({truncate(JSON.stringify(params), 80)})</Text>

      {progress && (
        <ProgressBar completed={progress.completed} total={progress.total} />
      )}

      {status === "completed" && result && (
        <Text color={colors.dim}>{truncate(result, MAX_RESULT_LENGTH)}</Text>
      )}
    </Box>
  );
}
