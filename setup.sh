#!/usr/bin/env bash
# setup.sh — chatinho package setup (pyproject.toml)
# Creates the .venv and installs ALL dependencies, extras included.
# If uv is not installed, installs it automatically.
set -euo pipefail

# Operate relative to this script's directory, regardless of caller's cwd.
cd "$(cd "$(dirname "$0")" && pwd)"

echo "🐍 chatinho setup — preparing virtual environment..."

# Locate uv: PATH or common locations (includes $PREFIX for Termux).
find_uv() {
    local cand
    for cand in "$(command -v uv 2>/dev/null || true)" \
        "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" \
        "/usr/local/bin/uv" "${PREFIX:-/usr}/bin/uv"; do
        if [ -x "$cand" ]; then
            echo "$cand"
            return 0
        fi
    done
    return 1
}

# A pre-set UV wins, so the script can be driven somewhere other than where
# find_uv looks — which is also how its Termux branch is exercised off a phone.
UV="${UV:-$(find_uv || true)}"

# Detect Termux/Android: the official uv installer does not support aarch64-linux-android.
is_termux() {
    [ -n "${PREFIX:-}" ] && [ -x "$PREFIX/bin/pkg" ]
}

# If uv does not exist, install it automatically.
if [ -z "$UV" ]; then
    echo "⬇️  uv not found — installing automatically..."
    if is_termux; then
        echo "   (Termux detected — installing via pkg)"
        pkg install -y uv
    elif command -v curl &>/dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &>/dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    elif command -v pip3 &>/dev/null; then
        echo "   (no curl/wget — falling back to pip3)"
        pip3 install --user uv
    else
        echo "❌ No curl/wget/pip — install uv manually: https://docs.astral.sh/uv/"
        echo "   (Termux: pkg install uv)"
        exit 1
    fi
    UV="$(find_uv || true)"
    if [ -z "$UV" ]; then
        echo "❌ uv installed but not found — add ~/.local/bin to PATH and run again."
        echo "   (Current PATH: $PATH)"
        exit 1
    fi
    echo "✅ uv installed at: $UV"
fi

# Create .venv if it doesn't exist
if [ ! -d .venv ]; then
    "$UV" venv
    echo "✅ .venv created"
else
    echo "🔄 .venv exists — updating dependencies..."
fi

# Which extra to sync. `dev` is explicit on purpose: the package itself installs
# nothing, and the batteries live behind extras, so a bare `uv sync` would depend
# on which uv you have for whether the test tools land in .venv at all.
#
# Termux is the exception, and not a preference: PyPI ships no aarch64-Android
# wheel for `ruff` (Rust) or for `openai`'s pydantic-core (Rust), so `--extra dev`
# there is not an install at all — it is uv handing both to maturin and cargo to
# compile on a phone, which is slow when it works and fails outright when the
# cargo registry has a half-extracted crate in it ("failed to open .cargo-ok:
# File exists"). `tui` is textual and nothing else, all pure-Python wheels, and
# it is the whole of what ./run.sh needs.
EXTRA="${CHATINHO_EXTRA:-}"
if [ -z "$EXTRA" ]; then
    if is_termux; then
        EXTRA="tui"
    else
        EXTRA="dev"
    fi
fi

echo "📦 Installing/updating dependencies (--extra $EXTRA)..."
"$UV" sync --extra "$EXTRA"

if [ "$EXTRA" = "tui" ] && is_termux; then
    echo "   (Termux: the terminal only. ruff and openai are Rust on this platform"
    echo "    and would be built from source — CHATINHO_EXTRA=dev bash setup.sh if"
    echo "    you have a working cargo and want the checks too.)"
fi
echo "✅ Setup complete — run: ./run.sh  (or .venv/bin/python demo.py)"
