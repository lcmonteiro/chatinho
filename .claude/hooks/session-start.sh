#!/bin/bash
# Gets a session ready to work: in a cloud session, the .venv the checks run in.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# The checks need .venv, and a cloud container starts without one. setup.sh is
# idempotent and picks the right extra; a local session is left to the person
# running it, who may be on Termux or not want uv installed for them.
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  bash ./setup.sh >&2
fi
