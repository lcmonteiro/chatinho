#!/usr/bin/env bash
#
# What chatinho can and cannot do on *this* terminal.
#
# Copying is the part of a TUI chat that depends most on the terminal it runs
# in, and it fails silently in several different ways: a terminal may drop
# OSC 52, take a long press for its own menu, or never report a key at all.
# None of that is visible from the code, so this asks the machine instead.
#
# Run it on the machine that is having trouble:
#
#     ./diagnose.sh
#
set -u
cd "$(dirname "$0")"

echo "== chatinho =="
if git rev-parse --git-dir >/dev/null 2>&1; then
    echo "  commit: $(git log --oneline -1)"
    echo "  branch: $(git rev-parse --abbrev-ref HEAD)"
    [ -n "$(git status --porcelain)" ] && echo "  (with uncommitted changes)"
else
    echo "  not a git checkout — an installed copy?"
fi

echo "== python =="
for py in python3 python3.12 python; do
    if command -v "$py" >/dev/null 2>&1; then
        echo "  $py: $("$py" --version 2>&1)"
    fi
done
if [ -x .venv/bin/python ]; then
    echo "  .venv:   $(.venv/bin/python --version 2>&1)"
    echo "  textual: $(.venv/bin/python -c 'import textual; print(textual.__version__)' 2>&1)"
else
    echo "  .venv:   missing — run ./setup.sh"
fi

echo "== terminal =="
echo "  TERM=${TERM:-<unset>}  TERM_PROGRAM=${TERM_PROGRAM:-<unset>}"
echo "  PREFIX=${PREFIX:-<unset>}   # set on Termux"

echo "== clipboard helpers =="
found=""
for helper in termux-clipboard-set wl-copy xclip xsel pbcopy; do
    if path=$(command -v "$helper" 2>/dev/null); then
        echo "  present: $helper -> $path"
        [ -z "$found" ] && found="$helper"
    else
        echo "  missing: $helper"
    fi
done
[ -z "$found" ] && echo "  => no helper: OSC 52 is the only route, and some terminals drop it"

echo "== does the clipboard actually take it? =="
if command -v termux-clipboard-set >/dev/null 2>&1; then
    if printf 'chatinho-probe' | timeout 10 termux-clipboard-set 2>&1; then
        echo "  wrote it; read back: [$(timeout 10 termux-clipboard-get 2>&1)]"
        echo "  (if that is empty, the Termux:API *app* is missing — the package is only half)"
    else
        echo "  termux-clipboard-set failed — the Termux:API app is probably not installed"
    fi
elif [ -n "$found" ]; then
    echo "  $found is present; not exercised here, it needs a display"
else
    echo "  nothing to try"
fi

echo
echo "Paste all of the above back."
