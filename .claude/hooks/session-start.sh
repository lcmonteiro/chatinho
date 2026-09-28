#!/bin/bash
# Installs the OpenSpec CLI used by the /opsx:* commands and openspec-* skills.
set -euo pipefail

if ! command -v openspec >/dev/null 2>&1; then
  npm install -g @fission-ai/openspec@latest >/dev/null 2>&1 \
    || echo "Warning: failed to install OpenSpec CLI (npm install -g @fission-ai/openspec)" >&2
fi
