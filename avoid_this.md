# Avoid This

Things that broke the TUI and should not be done again.

---

## TabItem: Do NOT use `background: transparent`

**Date:** 2026-02-03

**What happened:**
Changed `TabItem` CSS from `background: #44475A` to `background: transparent` to fix a double-border visual issue.

**Result:**
Broke the entire TUI layout.

**Lesson:**
TabItem needs a solid background color. To fix double-border issues, try removing or adjusting the `border` property instead, not the background.

---

## ANSI escape sequences before Textual app.run()

**Date:** 2026-02-03

**What happened:**
Tried to set terminal tab title by writing ANSI escape sequence before starting Textual:
```python
sys.stdout.write("\033]0;🛰️ Satellite\007")
sys.stdout.flush()
app = SatetoadApp()
app.run()
```

**Result:**
Broke the TUI. When pressing "Evals", the app crashed and displayed garbage characters.

**Lesson:**
Writing stdout before Textual takes control of the terminal, destroys the whole code. NEVER AGAIN.

Never write raw escape codes to stdout before Textual takes control. Textual manages the terminal itself (alternate screen buffer, raw mode, etc.) and raw escape codes corrupt its state. Use Textual's `TITLE` class attribute instead - if the terminal doesn't respect it, that's a terminal limitation, not something to work around with raw escape codes.
