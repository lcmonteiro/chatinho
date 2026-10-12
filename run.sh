#!/usr/bin/env bash
# run.sh — Run the chatinho assistant demo (needs OPENAI_API_KEY)
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Setup if needed
if [ ! -d "$DIR/.venv" ]; then
    bash "$DIR/setup.sh"
fi

exec "$DIR/.venv/bin/python" "$DIR/examples/assistant.py" "$@"
