#!/bin/bash
# Gets a session ready to work: the OpenSpec CLI the /opsx:* commands and
# openspec-* skills use, and — in a cloud session — the .venv the checks run in.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# The OpenSpec version is CI's, read from the workflow rather than written here
# a second time: a newer CLI is stricter, so @latest failed `validate --strict`
# on specs CI passes. "~1.13" accepts any 1.13.x, so the minor is what is compared.
pin="$(grep -o '@fission-ai/openspec@[^[:space:]"]*' .github/workflows/tests.yml | head -n 1 || true)"
pin="${pin:-@fission-ai/openspec@latest}"
wanted="${pin##*@}"
wanted="${wanted#[~^]}"
wanted="$(echo "$wanted" | cut -d. -f1,2)"
installed="$(openspec --version 2>/dev/null | cut -d. -f1,2 || true)"
if [ -z "$installed" ] || { [ "$wanted" != "latest" ] && [ "$installed" != "$wanted" ]; }; then
  npm install -g "$pin" >/dev/null 2>&1 \
    || echo "Warning: failed to install OpenSpec CLI (npm install -g $pin)" >&2
fi

# The checks need .venv, and a cloud container starts without one. setup.sh is
# idempotent and picks the right extra; a local session is left to the person
# running it, who may be on Termux or not want uv installed for them.
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  bash ./setup.sh >&2
fi
