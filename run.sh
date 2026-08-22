#!/usr/bin/env bash
# run.sh — Run the chatinho demo app
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Setup if needed
if [ ! -d "$DIR/.venv" ]; then
    bash "$DIR/setup.sh"
fi

exec "$DIR/.venv/bin/python" "$DIR/examples/demo.py" "$@"
