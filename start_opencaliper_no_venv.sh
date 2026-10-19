#!/usr/bin/env sh
# Use the current environment; preserve relative measurement paths.
if command -v python >/dev/null 2>&1; then
    exec python -m opencaliper gui "$@"
elif command -v python3 >/dev/null 2>&1; then
    exec python3 -m opencaliper gui "$@"
else
    echo 'Python 3.10 or newer is required. See the README for installation in an existing environment.' >&2
    exit 1
fi
