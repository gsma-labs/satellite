import { Box, Text } from "ink";
import { useConversation } from "./hooks/use-conversation.js";
import { useTokenTracker } from "./hooks/use-token-tracker.js";
import { MessageHistory } from "./components/message-history.js";
import { AssistantMessage } from "./components/assistant-message.js";
import { ToolCallPanel } from "./components/tool-call-panel.js";
import { InputBar } from "./components/input-bar.js";
import { StatusBar } from "./components/status-bar.js";
import { TOOL_SCHEMAS } from "./tools/schemas.js";
import { executeTool } from "./tools/executor.js";
import { pricing } from "./theme.js";

export function App() {
  const { usage, addUsage } = useTokenTracker();
  const { state, sendMessage } = useConversation({
    toolSchemas: TOOL_SCHEMAS,
    executeTool,
    onUsage: addUsage,
  });

  const isInputDisabled = state.isStreaming || state.isToolRunning;

  return (
    <Box flexDirection="column">
      <MessageHistory messages={state.finalizedMessages} />

      {state.streamingText && (
        <AssistantMessage
          text={state.streamingText}
          isStreaming={state.isStreaming}
        />
      )}

      {state.activeToolCalls.map((tc) => (
        <ToolCallPanel key={tc.id} toolCall={tc} />
      ))}

      {state.error && (
        <Box>
          <Text color="red">Error: {state.error}</Text>
        </Box>
      )}

      <InputBar onSubmit={sendMessage} isDisabled={isInputDisabled} />
      <StatusBar model={pricing.model} usage={usage} />
    </Box>
  );
}
