#!/usr/bin/env sh
# Keep the caller's working directory so relative measurement paths still work.
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$script_dir/scripts/launch.py" "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "$script_dir/scripts/launch.py" "$@"
else
    echo 'Python 3.10 or newer is required. Install Python, pip and venv, then run this launcher again.' >&2
    exit 1
fi
