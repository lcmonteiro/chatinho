# Examples

Ready-to-run demos for the chatinho library. Each file is a small,
self-contained app that shows one way of using the library.

## Running

From the project root:

```bash
bash run.sh                    # runs examples/demo.py
python examples/demo.py        # or directly
```

## Available demos

| File | What it shows |
|---|---|
| `demo.py` | Full-featured demo: Markdown rendering, code blocks with syntax highlighting, `/help` and `/code` commands, `/reply <id> <text>`, click-to-reply and a simulated bot that answers to sent messages |

Want to add your own? Drop a new file here — e.g. a themed variant
(`ChatStyle(accent=...)`) or a WebSocket-connected chat — and list it
in the table above.
