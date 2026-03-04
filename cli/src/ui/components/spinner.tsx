import { useState, useEffect } from "react";
import { Text } from "ink";
import { spinnerFrames, colors } from "../theme.js";

interface SpinnerProps {
  label?: string;
}

export function Spinner({ label }: SpinnerProps) {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setFrame(prev => (prev + 1) % spinnerFrames.length);
    }, 80);
    return () => clearInterval(timer);
  }, []);
  return (
    <Text color={colors.toolBorder}>
      {spinnerFrames[frame]}{label ? ` ${label}` : ""}
    </Text>
  );
}
