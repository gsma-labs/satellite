import { useState, useEffect } from "react";
import { Text } from "ink";
import { symbols, colors } from "../theme.js";

interface AssistantMessageProps {
  text: string;
  isStreaming?: boolean;
}

export function AssistantMessage({ text, isStreaming }: AssistantMessageProps) {
  const [cursorVisible, setCursorVisible] = useState(true);

  useEffect(() => {
    if (!isStreaming) return;
    const timer = setInterval(() => {
      setCursorVisible(prev => !prev);
    }, 500);
    return () => clearInterval(timer);
  }, [isStreaming]);

  return (
    <Text color={colors.assistant}>
      {symbols.assistantBullet} {text}
      {isStreaming && cursorVisible ? symbols.cursor : ""}
    </Text>
  );
}
