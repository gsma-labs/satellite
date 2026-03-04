import { Text } from "ink";
import { symbols, colors } from "../theme.js";

interface UserMessageProps {
  text: string;
}

export function UserMessage({ text }: UserMessageProps) {
  return (
    <Text color={colors.user}>
      {symbols.userPrompt} {text}
    </Text>
  );
}
