# Examples

Ready-to-run demos for the chatinho library. Each file is a small,
self-contained app that shows one way of using the library.

## Running

From the project root:

```bash
bash run.sh                             # runs examples/demo.py
python examples/demo.py                 # or directly
python examples/headless.py             # the same chat, no TUI
printf '/help\nola\n' | python examples/headless.py   # or scripted
```

## Available demos

| File | What it shows |
|---|---|
| `demo.py` | Full-featured TUI built on `create_chat`: Markdown rendering, code blocks with syntax highlighting, a custom `BaseCommand` (`/code`) next to the library's `/help`, command autocomplete, click-to-reply, and an echo `BaseConnector` that answers every sent message |
| `headless.py` | The same chat with no terminal UI: a `ChatSession` wired to stdin/stdout. Same commands, same connector, same hooks — the presentation layer is one `print`. Reads from a pipe when stdin is not a TTY, so it doubles as a scriptable transcript |

The demo runs without credentials or a backend. The shipped `A2AConnector` and
`OpenAIConnector` both reach the network in `initialize()`, so an example using
them needs real endpoints and keys.

Want to add your own? Drop a new file here — e.g. a themed variant
(`create_chat(style=ChatStyle(...))`) or a WebSocket-connected chat — and list it
in the table above.
