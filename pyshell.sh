#!/usr/bin/env bash
# pyshell.sh — real POSIX shell entrypoint for PyShell
# Makes PyShell a real .sh: executable, pipeable, scriptable, sourceable
# Usage:
#   ./pyshell.sh                  # interactive shell
#   ./pyshell.sh script.sh        # run shell script non-interactively
#   ./pyshell.sh -c "ls | grep py" # run single command
#   source ./pyshell.sh           # source (no exec, keeps cwd)
#   bash pyshell.sh --version

set -e

# --- resolve script dir (real path, handles symlinks) ---
PYSHELL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PYSHELL_PY="$PYSHELL_DIR/pyshell.py"

# fallback if BASH_SOURCE empty (when run via sh)
if [ ! -f "$PYSHELL_PY" ]; then
    PYSHELL_PY="$(dirname "$0")/pyshell.py"
fi

# --- find python ---
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "pyshell: python3 not found in PATH" >&2
    exit 127
fi

# --- handle .sh passthrough: if invoked as `pyshell.sh script.sh`, delegate to python ---
# Also supports: pyshell.sh --version, --help, -c "cmd"

# If no args: interactive mode (python handles banner, cwd -> ~ / C:\)
if [ $# -eq 0 ]; then
    exec "$PYTHON" "$PYSHELL_PY"
fi

case "$1" in
    --version|-v|version)
        exec "$PYTHON" "$PYSHELL_PY" --version
        ;;
    --help|-h|help)
        exec "$PYTHON" "$PYSHELL_PY" --help
        ;;
    -c|--command)
        shift
        # Join remaining args as one command string and pass via -c
        # This lets: ./pyshell.sh -c "ls | grep py > out.txt"
        CMD="$*"
        if [ -z "$CMD" ]; then
            echo "pyshell: -c requires a command" >&2
            exit 1
        fi
        exec "$PYTHON" "$PYSHELL_PY" -c "$CMD"
        ;;
    *.sh|*.bash|*.zsh)
        # Run a shell script file inside pyshell (real .sh execution)
        # Supports shebang, pipes, redirections, vars, etc. via pyshell engine
        if [ -f "$1" ]; then
            exec "$PYTHON" "$PYSHELL_PY" "$1" "${@:2}"
        else
            echo "pyshell: $1: No such file" >&2
            exit 1
        fi
        ;;
    *)
        # If first arg is an existing file, treat as script; otherwise pass through
        if [ -f "$1" ]; then
            exec "$PYTHON" "$PYSHELL_PY" "$@"
        else
            # Could be `pyshell config`, `pyshell quit`, etc. — pass through
            # Also handles `./pyshell.sh ls -la` style single command
            # Try to run as one-shot pyshell command: join args
            exec "$PYTHON" "$PYSHELL_PY" -c "$*"
        fi
        ;;
esac
