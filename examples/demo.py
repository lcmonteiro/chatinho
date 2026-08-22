"""Demo of the chatinho library: shows markdown, code blocks, commands,
replies and command autocomplete.

Run with:  bash run.sh
"""

from textual.widgets import Input

from chatinho import ChatApp

COMMANDS = {
    "help": "Show available commands",
    "code": "Show a Python code block with syntax highlighting",
    "reply": "Reply to a message: /reply <id> <text>",
}


class DemoChat(ChatApp):
    """ChatApp with a simulated bot that replies to commands and messages."""

    def __init__(self) -> None:
        super().__init__(commands=COMMANDS)
        self._input_placeholder = "Type /help, /code, /reply <id> <text>, or a message…"

    def on_mount(self) -> None:
        super().on_mount()
        # Welcome message with markdown + code block
        self.receive_message(
            "Welcome to **chatinho**! 👋\n\n"
            "You can send commands — type `/` to see suggestions:\n"
            "- `/help` — shows this help\n"
            "- `/code` — shows an example with syntax highlighting\n\n"
            "Everything you type is rendered as Markdown."
        )

    def on_input_submitted(self, message: Input.Submitted) -> None:
        """Intercepts commands before passing them to ChatApp."""
        del message
        inp = self.query_one("#input-line", Input)
        text = inp.value.strip()
        if not text:
            return
        inp.value = ""
        if text.startswith("/"):
            parts = text[1:].split(maxsplit=1)
            if not parts:
                return
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            if cmd == "reply":
                # /reply <msg_id> <text>
                reply_parts = args.split(maxsplit=1)
                if len(reply_parts) != 2:
                    self.receive_message("Usage: /reply <msg_id> <text>")
                    return
                reply_id, reply_text = reply_parts
                mid = self.send_message(reply_text, reply_to=reply_id)
                self._fake_reply(mid, reply_text)
            else:
                self.send_command(text[1:].strip())
        else:
            # If a message is selected (click), reply to it
            mid = self.send_pending_reply(text) or self.send_message(text)
            self._fake_reply(mid, text)
    def on_command(self, command: str) -> None:
        """Bot that replies to known commands."""
        match command:
            case "help":
                self.receive_message(
                    "## Available commands\n\n"
                    "- `/help` — shows this help\n"
                    "- `/code` — shows a Python code block\n"
                    "- `/reply <id> <text>` — replies to a message"
                )
            case "code":
                self.receive_message(
                    "Here is an example with **syntax highlighting**:\n\n"
                    "```python\n"
                    "def fib(n: int) -> int:\n"
                    "    a, b = 0, 1\n"
                    "    for _ in range(n):\n"
                    "        a, b = b, a + b\n"
                    "    return a\n"
                    "```"
                )
            case _:
                self.receive_message(f"Unknown command: `/{command}`. Try `/help`.")

    def _fake_reply(self, msg_id: str, text: str) -> None:
        """Simulates a reply from the 'other side' to the sent message.

        Uses set_timer instead of time.sleep so the UI thread is never
        blocked: the sent message paints immediately, and the reply lands
        0.6s later without freezing the app.
        """
        self.set_timer(
            0.6,
            lambda: self.receive_message(f"Received: _{text}_", reply_to=msg_id),
        )


if __name__ == "__main__":
    DemoChat().run()
