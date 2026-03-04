import { Static, Box } from "ink";
import type { DisplayMessage } from "../types.js";
import { UserMessage } from "./user-message.js";
import { AssistantMessage } from "./assistant-message.js";
import { ToolCallPanel } from "./tool-call-panel.js";

interface MessageHistoryProps {
  messages: DisplayMessage[];
}

export function MessageHistory({ messages }: MessageHistoryProps) {
  return (
    <Static items={messages}>
      {(msg) => (
        <Box key={msg.id} flexDirection="column" marginBottom={1}>
          {msg.role === "user" ? (
            <UserMessage text={msg.text} />
          ) : (
            <AssistantMessage text={msg.text} />
          )}
          {msg.toolCalls?.map(tc => (
            <ToolCallPanel key={tc.id} toolCall={tc} />
          ))}
        </Box>
      )}
    </Static>
  );
}
