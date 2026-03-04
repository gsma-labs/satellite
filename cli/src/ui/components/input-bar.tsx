import { useState } from "react";
import { Box, Text, useInput } from "ink";
import { colors, symbols } from "../theme.js";
import { Spinner } from "./spinner.js";

interface InputBarProps {
  onSubmit: (text: string) => void;
  isDisabled?: boolean;
}

export function InputBar({ onSubmit, isDisabled }: InputBarProps) {
  const [text, setText] = useState("");

  useInput((input, key) => {
    if (isDisabled) return;

    if (key.return) {
      const trimmed = text.trim();
      if (trimmed.length > 0) {
        onSubmit(trimmed);
        setText("");
      }
      return;
    }

    if (key.backspace || key.delete) {
      setText(prev => prev.slice(0, -1));
      return;
    }

    if (!key.ctrl && !key.meta && input) {
      setText(prev => prev + input);
    }
  });

  if (isDisabled) {
    return (
      <Box>
        <Spinner label="Thinking..." />
      </Box>
    );
  }

  return (
    <Box>
      <Text color={colors.user}>{symbols.userPrompt} </Text>
      <Text>{text}</Text>
      <Text color={colors.dim}>{symbols.cursor}</Text>
    </Box>
  );
}
