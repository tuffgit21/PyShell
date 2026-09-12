#!/usr/bin/env python3
"""
pyshell — matrix.py
A tiny, fast, cross-platform shell with pyfetch integration.

Built-in commands:
  pyshell --version, pyshell quit, pyshell config
  ls, cd, pwd, pyfetch, time, clear, help, cat, echo, whoami, hostname, rps, matrix

pyfetch supports full args: pyfetch --image ./logo.png --logo arch --no-color
Config: pyfetch_config.json (same as pyfetch)
"""

from __future__ import annotations

import contextlib
import datetime
import getpass
import glob as globmod
import importlib
import io
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# --- optional color ---
try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
BR_GREEN = "\033[92m"
BR_CYAN = "\033[96m"
BR_YELLOW = "\033[93m"
BR_RED = "\033[91m"
BR_BLACK = "\033[90m"
BR_WHITE = "\033[97m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

VERSION = "0.3.0-alpha"
CMD_LIST = (
    "pyshell --version  # Shows current version",
    "pyshell quit       # Quits pyshell",
    "pyshell config     # Open pyfetch config",
    "ls [path]          # List directory",
    "cd [path]          # Change directory (no args -> ~ on Linux, C:\\ on Windows; supports ~, -, /home/$USER)",
    "pwd                # Show current directory",
    "pyfetch [args]     # pyfetch system info (supports --image, --logo, --no-color)",
    "time               # Show time and date",
    "clear              # Clear screen",
    "cat <file>         # Show file",
    "echo [-neE] [text] # OG echo like GNU echo (-n no newline, -e escapes \\n\\t\\\\, -E no escapes, -- end opts) - use \"\" for empty line",
    "cp [-rivfn] src dst # Copy file/dir (-r recursive, -v verbose, -i interactive, -f force)",
    "mv [-ivfn] src dst # Move/rename file/dir (-v verbose, -i interactive, -f force)",
    "mkdir [-pv] <dir>  # Make directory (-p parents, -v verbose)",
    "rm [-rfiv] <path>  # Remove file/dir (-r recursive, -f force, -i interactive, -v verbose)",
    "rmdir <dir>        # Remove empty directory",
    "touch <file>       # Create empty file / update timestamp",
    "grep [-inv] <pat> [file] # Search pattern (supports pipes: cat file | grep pat)",
    "export VAR=val     # Set env var (real .sh: export FOO=bar)",
    "unset VAR          # Unset env var",
    "env                # Show environment",
    "source <file> / . <file> # Execute .sh script in current shell",
    "history            # Show command history",
    "whoami             # Show user",
    "hostname           # Show hostname",
    "help               # Show help",
    "rps                # Rock Paper Scissors",
    "matrix             # Matrix rain effect",
)
# Real .sh state
_last_exit_code: int = 0
_last_bg_pid: int | None = None

username = getpass.getuser()
computer = socket.gethostname()

def get_pyshell_home() -> Path:
    """OS-specific home: ~ (/home/$USER) on Linux/macOS, C:\\ on Windows."""
    if os.name == "nt" or platform.system() == "Windows":
        # Windows home is C:\ as requested
        return Path("C:\\")
    else:
        # Linux/macOS: ~ / /home/$USER
        try:
            return Path.home()
        except Exception:
            return Path(f"/home/{username}") if username else Path("/home")

def expand_pyshell_path(path_str: str) -> Path:
    """Expand ~ and handle OS-specific home. ~ -> get_pyshell_home()."""
    s = path_str.strip().strip('"').strip("'")
    if not s:
        return get_pyshell_home()
    # ~, ~/..., ~\...
    if s == "~" or s.startswith("~/") or s.startswith("~\\"):
        home = get_pyshell_home()
        if s == "~":
            return home
        # strip ~/ or ~\  (2 chars)
        rest = s[2:]
        # handle both / and \ in rest
        return (home / rest).resolve() if rest else home
    # Also support explicit /home/$USER on Linux as home alias
    if not (os.name == "nt" or platform.system() == "Windows"):
        # On Linux, treat /home/$USER exactly as home
        try:
            if Path(s).resolve() == Path(f"/home/{username}").resolve():
                return get_pyshell_home()
        except Exception:
            pass
    return Path(s).expanduser()

HISTORY_FILE = get_pyshell_home() / ".pyshell_history"
# Fallback for Windows C:\ history without permission -> use user profile
if os.name == "nt":
    try:
        # Try C:\, if not writable, fallback to user home
        test = HISTORY_FILE.parent
        if not os.access(str(test), os.W_OK):
            HISTORY_FILE = Path.home() / ".pyshell_history"
    except Exception:
        HISTORY_FILE = Path.home() / ".pyshell_history"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    # Logo requested by user - exact pyshell art
    print(BR_CYAN + BOLD + r"   ___       __ _          _ _ " + R)
    print(BR_CYAN + BOLD + r"  / _ \_   _/ _\ |__   ___| | |" + R)
    print(BR_CYAN + BOLD + r" / /_)/ | | \ \| '_ \ / _ \ | |" + f"  {DIM}v{VERSION}{R}")
    print(BR_CYAN + BOLD + r"/ ___/| |_| |\ \ | | |  __/ | |" + f"  {BR_BLACK}type 'help' for commands{R}")
    print(BR_CYAN + BOLD + r"\/     \__, \__/_| |_|\___|_|_|" + R)
    print(BR_CYAN + BOLD + r"       |___/ " + R)
    print(BR_BLACK + "─" * 50 + R)

def cmd_version():
    print(f"{DIM}Loading PyShell version...{R}")
    print(f"PyShell Version: {BOLD}{VERSION}{R}")
    print(f"Python {sys.version.split()[0]} on {os.name} ({socket.gethostname()})")
    return VERSION

def cmd_ls(arg: str):
    if not arg.strip():
        target = Path.cwd()
    else:
        # Use pyshell-aware expansion (~ -> OS home, C:\ for Windows)
        try:
            # Handle quoted paths via shlex
            tokens = shlex.split(arg.strip())
            path_str = tokens[0] if tokens else arg.strip()
        except ValueError:
            path_str = arg.strip()
        target = expand_pyshell_path(path_str)
    if not target.exists():
        print(f"{BR_RED}ls: no such file or directory: {target}{R}")
        return
    if target.is_file():
        print(target.name)
        return
    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for p in entries:
            if p.is_dir():
                print(f"{BR_CYAN}{BOLD}{p.name}/{R}")
            elif p.suffix in (".py", ".sh", ".exe"):
                print(f"{BR_GREEN}{p.name}{R}")
            else:
                print(p.name)
    except PermissionError as e:
        print(f"{BR_RED}ls: permission denied: {e}{R}")

_prev_dir: Path | None = None

def cmd_cd(arg: str):
    global _prev_dir
    raw = arg.strip()
    # cd with no args -> OS home (C:\ on Windows, ~ on Linux), cd - -> previous, cd ~ -> home
    if not raw:
        target = get_pyshell_home()
    elif raw == "-":
        if _prev_dir and _prev_dir.exists():
            target = _prev_dir
            print(str(target))
        else:
            print(f"{BR_YELLOW}cd: no previous directory{R}")
            return
    else:
        # handle quoted paths and spaces correctly, with OS-aware ~ expansion
        try:
            tokens = shlex.split(raw)
            if not tokens:
                target = get_pyshell_home()
            elif len(tokens) == 1:
                # Use pyshell-aware expansion (~ -> C:\ on Windows, ~ -> /home/$USER on Linux)
                target = expand_pyshell_path(tokens[0])
                # Also handle explicit /home/$USER on Linux (already covered)
            else:
                # user typed path with spaces but without proper quoting — treat whole raw as path
                cleaned = raw.strip().strip('"').strip("'")
                target = expand_pyshell_path(cleaned)
        except ValueError:
            target = expand_pyshell_path(raw.strip().strip('"').strip("'"))

    # resolve relative to cwd
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        try:
            target = target.resolve()
        except Exception:
            pass

    try:
        prev = Path.cwd()
        os.chdir(target)
        _prev_dir = prev
    except FileNotFoundError:
        print(f"{BR_RED}cd: no such file or directory: {target}{R}")
    except NotADirectoryError:
        print(f"{BR_RED}cd: not a directory: {target}{R}")
    except PermissionError:
        print(f"{BR_RED}cd: permission denied: {target}{R}")
    except Exception as e:
        print(f"{BR_RED}cd: {e}{R}")

def cmd_pwd(_arg: str = ""):
    print(Path.cwd())

def cmd_cat(arg: str):
    if not arg.strip():
        print(f"{BR_YELLOW}cat: missing file operand{R}")
        print(f"usage: cat <file>")
        return
    # Use OS-aware expansion for ~ and C:\
    try:
        tokens = shlex.split(arg.strip())
        path_str = tokens[0] if tokens else arg.strip()
    except ValueError:
        path_str = arg.strip()
    p = expand_pyshell_path(path_str)
    if not p.exists():
        print(f"{BR_RED}cat: {p}: No such file or directory{R}")
        return
    if p.is_dir():
        print(f"{BR_RED}cat: {p}: Is a directory{R}")
        return
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        print(text, end="" if text.endswith("\n") else "\n")
    except Exception as e:
        print(f"{BR_RED}cat: {e}{R}")

def _parse_cp_mv_args(arg: str):
    """Parse cp/mv args like OG: handles \"\" quoted paths, -options, and -- end."""
    # Use shlex to respect "" and '' - empty string "" will be parsed as '' token
    # shlex.split('""') -> [''] (one empty token) - we need to preserve that for echo but for cp/mv empty is invalid
    try:
        tokens = shlex.split(arg, posix=True)
    except ValueError:
        # Fallback for Windows trailing \ or unbalanced quotes
        try:
            tokens = shlex.split(arg, posix=False)
        except ValueError:
            tokens = arg.split()
    return tokens

def cmd_cp(arg: str):
    """
    OG cp — like GNU cp.
    Usage: cp [-Rrvisfn] [-p] source dest  or  cp [-Rrvisfn] source... directory
    Handles "" quoted paths (e.g., cp "My File.txt" "New Name.txt")
    """
    tokens = _parse_cp_mv_args(arg)
    if not tokens:
        print(f"{BR_YELLOW}cp: missing file operand{R}")
        print(f"Try 'help' for usage: cp [-rivfn] <source> <dest>")
        return
    # Parse options: -r/-R recursive, -v verbose, -i interactive, -f force, -n no-clobber, -p preserve
    opts = {"recursive": False, "verbose": False, "interactive": False, "force": False, "no_clobber": False, "preserve": False}
    idx = 0
    sources = []
    dest = None
    # Handle -- end of options
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--":
            idx += 1
            break
        if tok.startswith("-") and len(tok) > 1 and tok != "-" and all(c in "Rrvifnpsa" for c in tok[1:]):
            for c in tok[1:]:
                if c in "Rr": opts["recursive"] = True
                elif c == "v": opts["verbose"] = True
                elif c == "i": opts["interactive"] = True
                elif c == "f": opts["force"] = True
                elif c == "n": opts["no_clobber"] = True
                elif c == "p": opts["preserve"] = True
                elif c in "as": opts["preserve"] = True  # -a archive includes preserve
            idx += 1
        else:
            break
    remaining = tokens[idx:]
    if len(remaining) < 2:
        print(f"{BR_YELLOW}cp: missing destination file operand after '{remaining[0] if remaining else ''}'{R}")
        print(f"Usage: cp [-Rr] <source> <dest>  (use \"\" for paths with spaces)")
        return
    # All but last are sources, last is dest (like OG cp supports multiple sources)
    *src_tokens, dest_token = remaining
    dest_path = expand_pyshell_path(dest_token) if dest_token else None
    if dest_path is None:
        print(f"{BR_RED}cp: missing destination{R}")
        return

    # Handle multiple sources -> dest must be directory
    if len(src_tokens) > 1 and dest_path.exists() and not dest_path.is_dir():
        print(f"{BR_RED}cp: target '{dest_path}' is not a directory{R}")
        return

    for src_token in src_tokens:
        # Handle "" empty string case: shlex turns "" into '' (empty)
        # An empty source is invalid — treat as missing
        if src_token == "":
            print(f"{BR_RED}cp: cannot stat '': No such file or directory{R}")
            continue
        src = expand_pyshell_path(src_token)
        # Resolve dest per source (if multiple sources, dest is directory)
        cur_dest = dest_path
        if dest_path.exists() and dest_path.is_dir():
            cur_dest = dest_path / src.name
        # Also handle dest with "" -> current dir?
        if dest_token == "":
            cur_dest = Path.cwd() / src.name

        try:
            if not src.exists():
                print(f"{BR_RED}cp: cannot stat '{src}': No such file or directory{R}")
                continue
            if src.is_dir() and not opts["recursive"]:
                print(f"{BR_RED}cp: -r not specified; omitting directory '{src}'{R}")
                continue
            # No-clobber
            if opts["no_clobber"] and cur_dest.exists():
                if opts["verbose"]:
                    print(f"{DIM}cp: '{cur_dest}' not overwritten (no-clobber){R}")
                continue
            # Interactive
            if opts["interactive"] and cur_dest.exists():
                try:
                    ans = input(f"cp: overwrite '{cur_dest}'? [y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    continue
                if ans not in ("y", "yes"):
                    print(f"{DIM}cp: skipped '{cur_dest}'{R}")
                    continue
            # Copy
            if src.is_dir():
                # Use copytree
                if cur_dest.exists():
                    if opts["force"]:
                        shutil.rmtree(cur_dest)
                    else:
                        print(f"{BR_RED}cp: cannot overwrite directory '{cur_dest}' with directory '{src}' (use -f){R}")
                        continue
                # dirs_exist_ok=False by default, we handle above
                if opts["preserve"]:
                    shutil.copytree(src, cur_dest, symlinks=True)
                else:
                    shutil.copytree(src, cur_dest)
                if opts["verbose"]:
                    print(f"'{src}' -> '{cur_dest}'")
            else:
                # File
                if cur_dest.exists() and cur_dest.is_dir():
                    cur_dest = cur_dest / src.name
                # Ensure parent exists
                cur_dest.parent.mkdir(parents=True, exist_ok=True)
                if cur_dest.exists() and not opts["force"] and not opts["interactive"]:
                    # Default cp overwrites, but if no -f and exists, it will overwrite; we allow
                    pass
                # Copy file
                if opts["preserve"]:
                    shutil.copy2(src, cur_dest)
                else:
                    shutil.copy(src, cur_dest)
                if opts["verbose"]:
                    print(f"'{src}' -> '{cur_dest}'")
        except PermissionError as e:
            print(f"{BR_RED}cp: permission denied: {e}{R}")
        except Exception as e:
            print(f"{BR_RED}cp: {e}{R}")

def cmd_mv(arg: str):
    """
    OG mv — like GNU mv (also handles renaming).
    Usage: mv [-ivfn] source dest  or  mv [-ivfn] source... directory
    Handles "" quoted paths. Renaming is just mv oldname newname.
    """
    tokens = _parse_cp_mv_args(arg)
    if not tokens:
        print(f"{BR_YELLOW}mv: missing file operand{R}")
        print(f"Try 'help' for usage: mv [-ivfn] <source> <dest>")
        return
    opts = {"verbose": False, "interactive": False, "force": False, "no_clobber": False}
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--":
            idx += 1
            break
        if tok.startswith("-") and len(tok) > 1 and tok != "-" and all(c in "vifn" for c in tok[1:]):
            for c in tok[1:]:
                if c == "v": opts["verbose"] = True
                elif c == "i": opts["interactive"] = True
                elif c == "f": opts["force"] = True
                elif c == "n": opts["no_clobber"] = True
            idx += 1
        else:
            break
    remaining = tokens[idx:]
    if len(remaining) < 2:
        print(f"{BR_YELLOW}mv: missing destination file operand after '{remaining[0] if remaining else ''}'{R}")
        print(f"Usage: mv <source> <dest>  (use \"\" for paths with spaces, e.g., mv \"old name.txt\" \"new name.txt\")")
        return
    *src_tokens, dest_token = remaining
    dest_path = expand_pyshell_path(dest_token) if dest_token != "" else Path.cwd()
    if dest_token == "":
        dest_path = Path.cwd()

    if len(src_tokens) > 1 and dest_path.exists() and not dest_path.is_dir():
        print(f"{BR_RED}mv: target '{dest_path}' is not a directory{R}")
        return

    for src_token in src_tokens:
        if src_token == "":
            print(f"{BR_RED}mv: cannot stat '': No such file or directory{R}")
            continue
        src = expand_pyshell_path(src_token)
        cur_dest = dest_path
        # If dest is existing directory, move inside it
        if dest_path.exists() and dest_path.is_dir():
            cur_dest = dest_path / src.name
        # Handle renaming: if dest doesn't exist and single source, cur_dest is as given (may be new name)
        # For multiple sources, dest must be dir (checked above)
        try:
            if not src.exists():
                print(f"{BR_RED}mv: cannot stat '{src}': No such file or directory{R}")
                continue
            if opts["no_clobber"] and cur_dest.exists():
                if opts["verbose"]:
                    print(f"{DIM}mv: '{cur_dest}' not overwritten (no-clobber){R}")
                continue
            if opts["interactive"] and cur_dest.exists():
                try:
                    ans = input(f"mv: overwrite '{cur_dest}'? [y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    continue
                if ans not in ("y", "yes"):
                    print(f"{DIM}mv: skipped '{cur_dest}'{R}")
                    continue
            # Ensure parent exists for rename
            cur_dest.parent.mkdir(parents=True, exist_ok=True)
            # If force and dest exists, remove dest first if it's a dir? shutil.move handles
            # For file -> file, move will overwrite
            shutil.move(str(src), str(cur_dest))
            if opts["verbose"]:
                print(f"renamed '{src}' -> '{cur_dest}'" if not dest_path.is_dir() else f"'{src}' -> '{cur_dest}'")
        except PermissionError as e:
            print(f"{BR_RED}mv: permission denied: {e}{R}")
        except Exception as e:
            print(f"{BR_RED}mv: {e}{R}")

def cmd_echo(arg: str):
    r"""
    OG echo — like GNU coreutils echo / bash builtin, but ONLY "" counts for printing.
    Usage: echo [-neE] [--] ["STRING"...]
      -n  no trailing newline
      -e  enable backslash escapes
      -E  disable escapes (default)
      --  end of options
    Only text inside double quotes "" will be printed. Empty "" or no args -> blank line, no PowerShell prompt.
    Escapes (with -e): \a \b \c \e \f \n \r \t \v \\ \0NNN \xHH
    """
    # Use only "" for printing — if no "" found, treat as empty (no InputObject prompt)
    # This prevents PowerShell's Write-Output InputObject prompt when echo is empty
    raw_arg = arg.strip()
    # Check if arg contains double quotes
    has_quotes = '"' in raw_arg
    # Helper to mimic PowerShell's InputObject prompt when echo is empty / no ""
    def _prompt_inputobject():
        print("Supply values for the following parameters:")
        inputs = []
        idx = 0
        while True:
            try:
                val = input(f"InputObject[{idx}]: ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if val == "":
                # Empty line terminates (like InputObject[5]: <enter> in example)
                break
            inputs.append(val)
            idx += 1
        # PowerShell then outputs each InputObject element on new line, each char if they typed per-char
        # In example they typed h,e,l,l,o separately -> we print each as is
        for v in inputs:
            # If user typed "hello" as one line, should we split into chars like example?
            # Example shows they typed h/e/l/l/o as separate prompts, not "hello" as one.
            # We will just print each input as is; if they typed "hello" as one, it prints "hello" on one line.
            # To match example where "hello" typed as 5 separate inputs gives 5 lines h/e/l/l/o, we already do that.
            print(v)

    if not raw_arg:
        # echo with no args -> PowerShell would prompt for InputObject
        _prompt_inputobject()
        return
    if not has_quotes:
        # No "" found -> ONLY "" prints. So echo hello (no quotes) should trigger InputObject prompt, not print hello
        _prompt_inputobject()
        return
    # Has quotes, but check if quoted content is empty (e.g., echo "" with nothing inside)
    # Extract quoted contents to see if empty
    try:
        # Find all "" contents
        quoted_contents = re.findall(r'"([^"]*)"', raw_arg)
        # If all quoted contents are empty or whitespace, treat as empty -> prompt
        if quoted_contents and all(c.strip() == "" for c in quoted_contents):
            # Check if there is any non-option token besides empty quotes
            # e.g., echo "" or echo "" "" -> empty
            _prompt_inputobject()
            return
        # Also handle case: echo "" with no real text after stripping quotes and options
        # We will let normal flow handle it, but we can detect empty after shlex
    except Exception:
        pass

    # Now we know there is at least one "" — extract quoted strings like OG shell does
    # Use shlex to respect quoting like the real shell
    try:
        tokens = shlex.split(arg, posix=True)
    except ValueError as e:
        # Fallback: try to extract quoted substrings manually
        # Find all "..." segments
        quoted = re.findall(r'"([^"]*)"', arg)
        if quoted:
            tokens = quoted
        else:
            tokens = arg.split()

    # Parse options: echo allows combined like -ne, -en, -n, -e
    no_newline = False
    enable_escape = False  # default -E
    idx = 0
    # Check if first token is -- (end of options)
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--":
            idx += 1
            break
        if tok.startswith("-") and len(tok) > 1 and all(c in "neE" for c in tok[1:]):
            for c in tok[1:]:
                if c == "n":
                    no_newline = True
                elif c == "e":
                    enable_escape = True
                elif c == "E":
                    enable_escape = False
            idx += 1
        else:
            break

    # Remaining tokens are the strings to echo
    remaining = tokens[idx:]

    # Join with single space like OG echo
    text = " ".join(remaining)

    # Handle escapes if -e
    output = ""
    suppress_newline = False
    if enable_escape:
        i = 0
        out_chars = []
        while i < len(text):
            ch = text[i]
            if ch == "\\" and i + 1 < len(text):
                nxt = text[i+1]
                if nxt == "a":
                    out_chars.append("\a")
                    i += 2
                elif nxt == "b":
                    out_chars.append("\b")
                    i += 2
                elif nxt == "c":
                    # \c suppresses further output and no newline
                    suppress_newline = True
                    no_newline = True
                    break
                elif nxt == "e" or nxt == "E":
                    out_chars.append("\x1b")
                    i += 2
                elif nxt == "f":
                    out_chars.append("\f")
                    i += 2
                elif nxt == "n":
                    out_chars.append("\n")
                    i += 2
                elif nxt == "r":
                    out_chars.append("\r")
                    i += 2
                elif nxt == "t":
                    out_chars.append("\t")
                    i += 2
                elif nxt == "v":
                    out_chars.append("\v")
                    i += 2
                elif nxt == "\\":
                    out_chars.append("\\")
                    i += 2
                elif nxt == "0":
                    # \0NNN octal, up to 3 octal digits (0-7)
                    octal = ""
                    j = i+1
                    # Include the leading 0, then up to 2 more octal digits (total 3 including leading 0)
                    # GNU: \0NNN where N is octal, up to 3 digits total (including 0)
                    # We handle \0, \0N, \0NN
                    k = 0
                    while j < len(text) and k < 3 and text[j] in "01234567":
                        octal += text[j]
                        j += 1
                        k += 1
                    if octal:
                        try:
                            out_chars.append(chr(int(octal, 8)))
                            i = j
                        except ValueError:
                            out_chars.append("\\")
                            out_chars.append(nxt)
                            i += 2
                    else:
                        out_chars.append("\0")
                        i += 2
                elif nxt == "x":
                    # \xHH hex, 1-2 hex digits
                    hex_digits = ""
                    j = i+2
                    while j < len(text) and len(hex_digits) < 2 and text[j] in "0123456789abcdefABCDEF":
                        hex_digits += text[j]
                        j += 1
                    if hex_digits:
                        try:
                            out_chars.append(chr(int(hex_digits, 16)))
                            i = j
                        except ValueError:
                            out_chars.append("\\")
                            out_chars.append(nxt)
                            i += 2
                    else:
                        # No hex digits, treat as \x
                        out_chars.append("\\")
                        out_chars.append(nxt)
                        i += 2
                else:
                    # Unknown escape, keep as is (GNU keeps \ and next char as is, but we keep literal)
                    # GNU echo: unknown escapes are left as \ + char
                    out_chars.append("\\")
                    out_chars.append(nxt)
                    i += 2
            else:
                out_chars.append(ch)
                i += 1
        output = "".join(out_chars)
        if suppress_newline:
            # \c means no further output at all, including no newline
            no_newline = True
    else:
        output = text

    # Output like OG echo
    if suppress_newline:
        sys.stdout.write(output)
        sys.stdout.flush()
    else:
        if no_newline:
            sys.stdout.write(output)
            sys.stdout.flush()
        else:
            # Use print to add newline, but need to handle embedded newlines from -e
            # print will add its own newline, but output may already contain \n
            # We should use sys.stdout.write to have full control
            sys.stdout.write(output + "\n")
            sys.stdout.flush()

def cmd_time(_arg: str = ""):
    now = datetime.datetime.now()
    print(f"{BR_CYAN}{BOLD}{now.strftime('%Y-%m-%d %H:%M:%S')}{R}  {DIM}{now.strftime('%A')}{R}")
    print(f"{DIM}Timezone: {time.tzname[0] if time.tzname else 'local'}{R}")

def cmd_whoami(_arg: str = ""):
    print(getpass.getuser())

def cmd_hostname(_arg: str = ""):
    print(socket.gethostname())

# --- real .sh builtins ---

def cmd_export(arg: str):
    """Real .sh export: export VAR=val, export VAR, export -p"""
    global _last_exit_code
    arg = arg.strip()
    if not arg or arg in ("-p", "--print"):
        for k, v in sorted(os.environ.items()):
            print(f'declare -x {k}="{v}"')
        _last_exit_code = 0
        return
    # support multiple assignments: export A=1 B=2
    try:
        tokens = shlex.split(arg, posix=True)
    except ValueError:
        tokens = arg.split()
    for tok in tokens:
        if "=" in tok:
            k, v = tok.split("=", 1)
            # strip quotes from value
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            os.environ[k] = v
        else:
            # export VAR (mark existing or set empty)
            if tok not in os.environ:
                # if variable not set, check if it's a shell var? just set empty
                os.environ[tok] = os.environ.get(tok, "")
    _last_exit_code = 0

def cmd_unset(arg: str):
    global _last_exit_code
    try:
        tokens = shlex.split(arg.strip(), posix=True)
    except ValueError:
        tokens = arg.strip().split()
    for tok in tokens:
        # handle -f -v flags (ignore)
        if tok.startswith("-"):
            continue
        os.environ.pop(tok, None)
    _last_exit_code = 0

def cmd_env(_arg: str = ""):
    global _last_exit_code
    for k, v in sorted(os.environ.items()):
        print(f"{k}={v}")
    _last_exit_code = 0

def cmd_history(_arg: str = ""):
    global _last_exit_code
    hist = HISTORY_FILE
    if not hist.exists():
        print(f"{DIM}no history yet{R}")
        _last_exit_code = 0
        return
    try:
        lines = hist.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, l in enumerate(lines[-100:], 1):
            print(f"{BR_BLACK}{i:4d}{R}  {l}")
    except Exception as e:
        print(f"{BR_RED}history: {e}{R}")
        _last_exit_code = 1
        return
    _last_exit_code = 0

def cmd_mkdir(arg: str):
    global _last_exit_code
    try:
        tokens = shlex.split(arg, posix=True)
    except ValueError:
        tokens = shlex.split(arg, posix=False) if arg else []
    if not tokens:
        print(f"{BR_YELLOW}mkdir: missing operand{R}")
        _last_exit_code = 1
        return
    opts = {"parents": False, "verbose": False}
    paths = []
    for tok in tokens:
        if tok == "--":
            continue
        if tok.startswith("-") and all(c in "pv" for c in tok[1:]):
            if "p" in tok: opts["parents"] = True
            if "v" in tok: opts["verbose"] = True
        elif tok.startswith("-"):
            print(f"{BR_RED}mkdir: invalid option -- '{tok}'{R}")
            _last_exit_code = 1
            return
        else:
            paths.append(tok)
    if not paths:
        print(f"{BR_YELLOW}mkdir: missing operand{R}")
        _last_exit_code = 1
        return
    for p_str in paths:
        p = expand_pyshell_path(p_str)
        try:
            if opts["parents"]:
                p.mkdir(parents=True, exist_ok=True)
            else:
                p.mkdir(parents=False, exist_ok=False)
            if opts["verbose"]:
                print(f"mkdir: created directory '{p}'")
            _last_exit_code = 0
        except FileExistsError:
            print(f"{BR_RED}mkdir: cannot create directory '{p}': File exists{R}")
            _last_exit_code = 1
        except FileNotFoundError:
            print(f"{BR_RED}mkdir: cannot create directory '{p}': No such file or directory (use -p){R}")
            _last_exit_code = 1
        except Exception as e:
            print(f"{BR_RED}mkdir: {e}{R}")
            _last_exit_code = 1

def cmd_rm(arg: str):
    global _last_exit_code
    try:
        tokens = shlex.split(arg, posix=True)
    except ValueError:
        tokens = shlex.split(arg, posix=False) if arg else []
    if not tokens:
        print(f"{BR_YELLOW}rm: missing operand{R}")
        _last_exit_code = 1
        return
    opts = {"recursive": False, "force": False, "verbose": False, "interactive": False}
    paths = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            paths.extend(tokens[i+1:])
            break
        if tok.startswith("-") and len(tok) > 1 and all(c in "rfiv" for c in tok[1:]):
            for c in tok[1:]:
                if c == "r": opts["recursive"] = True
                elif c == "f": opts["force"] = True
                elif c == "i": opts["interactive"] = True
                elif c == "v": opts["verbose"] = True
            i += 1
        elif tok.startswith("-"):
            print(f"{BR_RED}rm: invalid option -- '{tok}'{R}")
            _last_exit_code = 1
            return
        else:
            paths.append(tok)
            i += 1
    if not paths:
        print(f"{BR_YELLOW}rm: missing operand{R}")
        _last_exit_code = 1
        return
    _last_exit_code = 0
    for p_str in paths:
        p = expand_pyshell_path(p_str)
        # glob expansion
        expanded = globmod.glob(str(p), recursive=False) if any(c in p_str for c in "*?[") else [str(p)]
        for ep_str in expanded:
            ep = Path(ep_str)
            if not ep.exists() and not ep.is_symlink():
                if not opts["force"]:
                    print(f"{BR_RED}rm: cannot remove '{ep}': No such file or directory{R}")
                    _last_exit_code = 1
                continue
            if opts["interactive"]:
                try:
                    ans = input(f"rm: remove '{ep}'? [y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    continue
                if ans not in ("y", "yes"):
                    continue
            try:
                if ep.is_dir() and not ep.is_symlink():
                    if not opts["recursive"]:
                        print(f"{BR_RED}rm: cannot remove '{ep}': Is a directory (use -r){R}")
                        _last_exit_code = 1
                        continue
                    shutil.rmtree(ep)
                else:
                    ep.unlink(missing_ok=opts["force"])
                if opts["verbose"]:
                    print(f"removed '{ep}'")
            except Exception as e:
                print(f"{BR_RED}rm: cannot remove '{ep}': {e}{R}")
                _last_exit_code = 1

def cmd_rmdir(arg: str):
    global _last_exit_code
    try:
        tokens = shlex.split(arg.strip(), posix=True)
    except ValueError:
        tokens = [arg.strip()]
    if not tokens or not tokens[0]:
        print(f"{BR_YELLOW}rmdir: missing operand{R}")
        _last_exit_code = 1
        return
    for p_str in tokens:
        if p_str.startswith("-"):
            continue
        p = expand_pyshell_path(p_str)
        try:
            p.rmdir()
            _last_exit_code = 0
        except OSError as e:
            print(f"{BR_RED}rmdir: failed to remove '{p}': {e}{R}")
            _last_exit_code = 1

def cmd_touch(arg: str):
    global _last_exit_code
    try:
        tokens = shlex.split(arg, posix=True)
    except ValueError:
        tokens = [arg.strip()]
    if not tokens:
        print(f"{BR_YELLOW}touch: missing file operand{R}")
        _last_exit_code = 1
        return
    for p_str in tokens:
        if p_str.startswith("-"):
            continue
        p = expand_pyshell_path(p_str)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch(exist_ok=True)
            # update mtime
            os.utime(p, None)
            _last_exit_code = 0
        except Exception as e:
            print(f"{BR_RED}touch: cannot touch '{p}': {e}{R}")
            _last_exit_code = 1

def cmd_grep(arg: str, stdin_data: str | None = None):
    """Real grep: grep [-inv] pattern [file] — supports stdin (pipes)."""
    global _last_exit_code
    try:
        tokens = shlex.split(arg, posix=True)
    except ValueError:
        tokens = arg.split()
    opts = {"ignore_case": False, "invert": False, "line_num": False, "count": False}
    pattern = None
    files = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            i += 1
            if i < len(tokens) and pattern is None:
                pattern = tokens[i]
                i += 1
            files.extend(tokens[i:])
            break
        if tok.startswith("-") and len(tok) > 1 and all(c in "invch" for c in tok[1:]):
            for c in tok[1:]:
                if c == "i": opts["ignore_case"] = True
                elif c == "v": opts["invert"] = True
                elif c == "n": opts["line_num"] = True
                elif c == "c": opts["count"] = True
            i += 1
        elif pattern is None:
            pattern = tok
            i += 1
        else:
            files.append(tok)
            i += 1
    if pattern is None:
        print(f"{BR_YELLOW}grep: missing pattern{R}")
        _last_exit_code = 2
        return
    flags = re.IGNORECASE if opts["ignore_case"] else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        # fallback to literal search
        regex = re.compile(re.escape(pattern), flags)
    matched_any = False
    count = 0

    def _process_lines(lines, label=None):
        nonlocal matched_any, count
        for idx, line in enumerate(lines, 1):
            m = bool(regex.search(line))
            if opts["invert"]:
                m = not m
            if m:
                matched_any = True
                count += 1
                if opts["count"]:
                    continue
                prefix = ""
                if label and len(files) > 1:
                    prefix = f"{label}:"
                if opts["line_num"]:
                    prefix += f"{idx}:"
                print(f"{prefix}{line}")

    if stdin_data is not None:
        _process_lines(stdin_data.splitlines())
    elif not files:
        # no files and no stdin: read stdin interactively? treat as error
        if stdin_data is None:
            # try reading from sys.stdin if piped
            if not sys.stdin.isatty():
                data = sys.stdin.read()
                _process_lines(data.splitlines())
            else:
                print(f"{BR_YELLOW}grep: no input{R}")
                _last_exit_code = 2
                return
    else:
        for f_str in files:
            p = expand_pyshell_path(f_str)
            # glob
            if any(c in f_str for c in "*?["):
                globs = globmod.glob(str(expand_pyshell_path(f_str)), recursive=False)
                if not globs:
                    print(f"{BR_RED}grep: {p}: No such file or directory{R}")
                    _last_exit_code = 1
                    continue
                for g in globs:
                    try:
                        text = Path(g).read_text(encoding="utf-8", errors="replace")
                        _process_lines(text.splitlines(), label=g if len(globs) > 1 or len(files) > 1 else None)
                    except Exception as e:
                        print(f"{BR_RED}grep: {g}: {e}{R}")
                        _last_exit_code = 1
                continue
            if not p.exists():
                print(f"{BR_RED}grep: {p}: No such file or directory{R}")
                _last_exit_code = 1
                continue
            if p.is_dir():
                print(f"{BR_RED}grep: {p}: Is a directory{R}")
                _last_exit_code = 1
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                _process_lines(text.splitlines(), label=str(p) if len(files) > 1 else None)
            except Exception as e:
                print(f"{BR_RED}grep: {e}{R}")
                _last_exit_code = 1
    if opts["count"]:
        print(count)
    _last_exit_code = 0 if matched_any else 1

def cmd_source(arg: str):
    """Real .sh source / .: execute .sh script in current shell (keeps cwd, env)."""
    global _last_exit_code
    path_str = arg.strip().strip('"').strip("'")
    if not path_str:
        print(f"{BR_YELLOW}source: missing file operand{R}")
        _last_exit_code = 1
        return
    # handle shlex: source "my script.sh"
    try:
        tokens = shlex.split(arg.strip(), posix=True)
        if tokens:
            path_str = tokens[0]
    except ValueError:
        pass
    p = expand_pyshell_path(path_str)
    if not p.exists():
        # also try relative to script dir
        alt = Path(__file__).parent / path_str
        if alt.exists():
            p = alt
        else:
            print(f"{BR_RED}source: {p}: No such file or directory{R}")
            _last_exit_code = 1
            return
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # handle shebang
            if stripped.startswith("#!"):
                continue
            # dispatch inside source keeps env/cwd
            dispatch(stripped)
        _last_exit_code = 0
    except Exception as e:
        print(f"{BR_RED}source: {e}{R}")
        _last_exit_code = 1

def cmd_pyfetch(arg: str):
    pass

def cmd_matrix(arg: str = ""):
    """Matrix rain — press Ctrl+C to stop."""
    import random
    import shutil as _shutil
    cols, rows = _shutil.get_terminal_size((80, 24))
    chars = "01ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｶﾖｴｷﾝ"
    print(f"{DIM}Matrix rain — Ctrl+C to stop{R}")
    time.sleep(0.5)
    try:
        # simple falling columns
        drops = [0] * cols
        for _ in range(rows * 8):
            line = ""
            for i in range(cols):
                if drops[i] == 0 and random.random() > 0.97:
                    drops[i] = random.randint(5, rows)
                c = random.choice(chars) if drops[i] > 0 else " "
                if drops[i] > 0:
                    # head bright, tail dim
                    if drops[i] == 1:
                        line += f"{BR_GREEN}{BOLD}{c}{R}"
                    else:
                        line += f"{GREEN}{c}{R}"
                    drops[i] -= 1
                else:
                    line += " "
            print(line[:cols])
            time.sleep(0.06)
    except KeyboardInterrupt:
        print(f"\n{BR_BLACK}matrix stopped{R}")

def cmd_help(_arg: str = ""):
    print(f"{BOLD}Available commands:{R}")
    for c in CMD_LIST:
        print(f"  {BR_CYAN}{c}{R}")
    print(f"\n{DIM}Tips: use 'pyfetch --help' or 'pyfetch --image <path>' for images.{R}")
    print(f"{DIM}Config: pyfetch_config.json in script dir. Run 'pyshell config' to open it.{R}")

def cmd_pyshell_config(_arg: str = ""):
    # open config in default editor or print path
    candidates = [
        Path(__file__).parent / "pyfetch_config.json",
        Path.cwd() / "pyfetch_config.json",
        Path.home() / ".pyfetch.json",
    ]
    found = next((p for p in candidates if p.exists()), candidates[0])
    print(f"{BOLD}Config file:{R} {found}")
    if found.exists():
        try:
            print(f"{DIM}{'─' * 50}{R}")
            print(found.read_text(encoding="utf-8")[:2000])
            print(f"{DIM}{'─' * 50}{R}")
        except Exception as e:
            print(f"{BR_RED}cannot read: {e}{R}")
    else:
        print(f"{BR_YELLOW}No config found. Run: python pyfetch.py --save-config{R}")
    # try open with OS
    try:
        if os.name == "nt":
            os.startfile(str(found))  # type: ignore[attr-defined]
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(found)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("open"):
            subprocess.Popen(["open", str(found)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Real .sh engine — expansion, redirections, pipes, chaining
# ---------------------------------------------------------------------------

BUILTINS = {"ls","cd","pwd","pyfetch","time","clear","cls","cat","echo","cp","mv","mkdir","rm","rmdir","touch","grep","export","unset","env","source",".","history","whoami","hostname","help","rps","matrix","quit","exit","q","pyshell"}

def _is_quoted(s: str, pos: int) -> bool:
    """Check if position pos in s is inside single/double quotes."""
    in_single = False
    in_double = False
    escaped = False
    for i, ch in enumerate(s):
        if i >= pos:
            break
        if escaped:
            escaped = False
            continue
        if ch == "\\" and not in_single:
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
    return in_single or in_double

def _split_unquoted(s: str, sep: str) -> list[str]:
    """Split s by sep only when sep is not inside quotes. sep can be multi-char."""
    res = []
    cur = []
    i = 0
    in_single = False
    in_double = False
    escaped = False
    while i < len(s):
        ch = s[i]
        if escaped:
            cur.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            # keep backslash for later, but don't split inside escaped
            escaped = True
            cur.append(ch)
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            cur.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            cur.append(ch)
            i += 1
            continue
        if not in_single and not in_double and s[i:i+len(sep)] == sep:
            res.append("".join(cur))
            cur = []
            i += len(sep)
            continue
        cur.append(ch)
        i += 1
    res.append("".join(cur))
    return res

def _find_unquoted(s: str, sub: str) -> int:
    """Find sub not inside quotes, -1 if not found."""
    in_single = False
    in_double = False
    escaped = False
    i = 0
    while i <= len(s) - len(sub):
        ch = s[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single and not in_double and s[i:i+len(sub)] == sub:
            return i
        i += 1
    return -1

def expand_shell_vars(line: str) -> str:
    """Expand $VAR, ${VAR}, $?, $$, $HOME, ~ is handled separately. Respects single quotes (no expand)."""
    global _last_exit_code
    res = []
    i = 0
    in_single = False
    in_double = False
    while i < len(line):
        ch = line[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            res.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            res.append(ch)
            i += 1
            continue
        if in_single:
            res.append(ch)
            i += 1
            continue
        if ch == "\\":
            # keep escaped next char literally
            res.append(ch)
            if i+1 < len(line):
                res.append(line[i+1])
                i += 2
            else:
                i += 1
            continue
        if ch == "$" and i+1 < len(line):
            nxt = line[i+1]
            if nxt == "?":
                res.append(str(_last_exit_code))
                i += 2
                continue
            elif nxt == "$":
                res.append(str(os.getpid()))
                i += 2
                continue
            elif nxt == "{":
                end = line.find("}", i+2)
                if end != -1:
                    var = line[i+2:end]
                    # support ${VAR:-default} simple fallback
                    if ":-" in var:
                        var, default = var.split(":-", 1)
                        res.append(os.environ.get(var, default))
                    elif "-" in var and var.count("-")==1:
                        # ${VAR-default}
                        var, default = var.split("-", 1)
                        res.append(os.environ.get(var, default) if var in os.environ else default)
                    else:
                        res.append(os.environ.get(var, ""))
                    i = end + 1
                    continue
                else:
                    res.append(ch)
                    i += 1
                    continue
            elif nxt.isalpha() or nxt == "_":
                j = i+1
                while j < len(line) and (line[j].isalnum() or line[j] == "_"):
                    j += 1
                var = line[i+1:j]
                res.append(os.environ.get(var, ""))
                i = j
                continue
            elif nxt.isdigit():
                # $1 $2 etc — not supported (script args), replace empty
                i += 2
                continue
            else:
                res.append(ch)
                i += 1
                continue
        res.append(ch)
        i += 1
    joined = "".join(res)
    # also expand ~ via expand_pyshell_path for leading ~ is handled elsewhere, but do $HOME already
    return os.path.expandvars(joined)  # second pass for ${} handled, but keep for safety

def _extract_redirections(cmd: str):
    """Extract > >> < 2> 2>> &> redirections (quote-aware). Returns (clean_cmd, stdin_file, stdout_file, stdout_append, stderr_file, stderr_append, stderr_to_stdout)."""
    # This operates on a single pipe segment (no |)
    stdin_file = None
    stdout_file = None
    stdout_append = False
    stderr_file = None
    stderr_append = False
    stderr_to_stdout = False
    # We will scan and remove redirections
    # Supported: > file, >> file, < file, 2> file, 2>> file, &> file, &>> file, 2>&1
    # For simplicity handle these sequentially by regex with quote awareness via manual scan
    # Strategy: iterate tokens via shlex to find redirection tokens? Easier: manual char scan to remove patterns and capture filenames.
    clean = []
    i = 0
    in_single = False
    in_double = False
    escaped = False
    n = len(cmd)
    # Build a list of chars, we will reconstruct clean without redirection parts
    while i < n:
        ch = cmd[i]
        if escaped:
            clean.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            clean.append(ch)
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            clean.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            clean.append(ch)
            i += 1
            continue
        if in_single or in_double:
            clean.append(ch)
            i += 1
            continue
        # not in quotes: check for redirections
        # &>> and &> and 2>&1
        if cmd[i:i+2] == "2>" and i+2 < n and cmd[i+2] == "&" and i+3 < n and cmd[i+3] == "1":
            # 2>&1
            stderr_to_stdout = True
            i += 4
            continue
        if cmd[i:i+3] == "&>>":
            # &>> file
            i += 3
            while i < n and cmd[i] in " \t":
                i += 1
            start = i
            # read filename (handle quotes)
            if i < n and cmd[i] in ('"', "'"):
                q = cmd[i]
                i += 1
                start = i
                while i < n and cmd[i] != q:
                    if cmd[i] == "\\":
                        i += 2
                    else:
                        i += 1
                fname = cmd[start:i]
                if i < n:
                    i += 1
            else:
                while i < n and cmd[i] not in " \t;|&":
                    i += 1
                fname = cmd[start:i].strip()
            stdout_file = fname
            stderr_file = fname
            stdout_append = True
            stderr_append = True
            continue
        if cmd[i:i+2] == "&>":
            i += 2
            while i < n and cmd[i] in " \t":
                i += 1
            start = i
            if i < n and cmd[i] in ('"', "'"):
                q = cmd[i]
                i += 1
                start = i
                while i < n and cmd[i] != q:
                    if cmd[i] == "\\":
                        i += 2
                    else:
                        i += 1
                fname = cmd[start:i]
                if i < n:
                    i += 1
            else:
                while i < n and cmd[i] not in " \t;|&":
                    i += 1
                fname = cmd[start:i].strip()
            stdout_file = fname
            stderr_file = fname
            stdout_append = False
            stderr_append = False
            continue
        if cmd[i:i+3] == "2>>":
            i += 3
            while i < n and cmd[i] in " \t":
                i += 1
            start = i
            if i < n and cmd[i] in ('"', "'"):
                q = cmd[i]
                i += 1
                start = i
                while i < n and cmd[i] != q:
                    if cmd[i]=="\\":
                        i+=2
                    else:
                        i+=1
                fname = cmd[start:i]
                if i < n:
                    i+=1
            else:
                while i < n and cmd[i] not in " \t;|&":
                    i+=1
                fname = cmd[start:i].strip()
            stderr_file = fname
            stderr_append = True
            continue
        if cmd[i:i+2] == "2>":
            i += 2
            while i < n and cmd[i] in " \t":
                i += 1
            start = i
            if i < n and cmd[i] in ('"', "'"):
                q = cmd[i]
                i+=1
                start=i
                while i < n and cmd[i]!=q:
                    if cmd[i]=="\\":
                        i+=2
                    else:
                        i+=1
                fname=cmd[start:i]
                if i<n:
                    i+=1
            else:
                while i<n and cmd[i] not in " \t;|&":
                    i+=1
                fname=cmd[start:i].strip()
            stderr_file=fname
            stderr_append=False
            continue
        if cmd[i:i+2] == ">>":
            i+=2
            while i<n and cmd[i] in " \t":
                i+=1
            start=i
            if i<n and cmd[i] in ('"',"'"):
                q=cmd[i]
                i+=1
                start=i
                while i<n and cmd[i]!=q:
                    if cmd[i]=="\\":
                        i+=2
                    else:
                        i+=1
                fname=cmd[start:i]
                if i<n:
                    i+=1
            else:
                while i<n and cmd[i] not in " \t;|&":
                    i+=1
                fname=cmd[start:i].strip()
            stdout_file=fname
            stdout_append=True
            continue
        if cmd[i]==">" :
            # avoid already handled >> (but we handled >> first)
            i+=1
            while i<n and cmd[i] in " \t":
                i+=1
            start=i
            if i<n and cmd[i] in ('"',"'"):
                q=cmd[i]
                i+=1
                start=i
                while i<n and cmd[i]!=q:
                    if cmd[i]=="\\":
                        i+=2
                    else:
                        i+=1
                fname=cmd[start:i]
                if i<n:
                    i+=1
            else:
                while i<n and cmd[i] not in " \t;|&":
                    i+=1
                fname=cmd[start:i].strip()
            stdout_file=fname
            stdout_append=False
            continue
        if cmd[i]=="<":
            i+=1
            while i<n and cmd[i] in " \t":
                i+=1
            start=i
            if i<n and cmd[i] in ('"',"'"):
                q=cmd[i]
                i+=1
                start=i
                while i<n and cmd[i]!=q:
                    if cmd[i]=="\\":
                        i+=2
                    else:
                        i+=1
                fname=cmd[start:i]
                if i<n:
                    i+=1
            else:
                while i<n and cmd[i] not in " \t;|&":
                    i+=1
                fname=cmd[start:i].strip()
            stdin_file=fname
            continue
        clean.append(ch)
        i+=1
    clean_cmd = "".join(clean).strip()
    return clean_cmd, stdin_file, stdout_file, stdout_append, stderr_file, stderr_append, stderr_to_stdout

def _run_single_with_redirects(clean_cmd: str, stdin_file, stdout_file, stdout_append, stderr_file, stderr_append, stderr_to_stdout, stdin_data: str | None = None) -> tuple[int, str, str]:
    """Run a single command (no pipes) with redirections. Returns (exit_code, stdout, stderr). Captures output."""
    global _last_exit_code
    # Handle stdin file
    actual_stdin = stdin_data
    if stdin_file:
        try:
            p = expand_pyshell_path(stdin_file.strip().strip('"').strip("'"))
            actual_stdin = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return 1, "", f"pyshell: {stdin_file}: {e}"
    # Capture stdout/stderr by redirecting
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    # Parse clean_cmd to get cmd name
    stripped = clean_cmd.strip()
    if not stripped:
        return 0, "", ""
    # We need to dispatch but capture output
    # Use contextlib.redirect_stdout/stderr
    exit_code = 0
    should_quit = False
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        # dispatch_single handles builtins vs external
        quit_flag = _dispatch_single(stripped, stdin_data=actual_stdin)
        if quit_flag is False:
            should_quit = True
        # _last_exit_code is set by builtin/external
        exit_code = _last_exit_code
    out = stdout_buf.getvalue()
    err = stderr_buf.getvalue()
    if stderr_to_stdout:
        out = out + err
        err = ""
    # Handle stdout redirection to file
    if stdout_file:
        try:
            p = expand_pyshell_path(stdout_file.strip().strip('"').strip("'"))
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if stdout_append else "w"
            with open(p, mode, encoding="utf-8", errors="replace") as f:
                f.write(out)
            out = ""  # consumed
        except Exception as e:
            err += f"\npyshell: {stdout_file}: {e}"
            exit_code = 1
    if stderr_file and not stderr_to_stdout:
        try:
            p = expand_pyshell_path(stderr_file.strip().strip('"').strip("'"))
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if stderr_append else "w"
            with open(p, mode, encoding="utf-8", errors="replace") as f:
                f.write(err)
            err = ""
        except Exception as e:
            err += f"\npyshell: {stderr_file}: {e}"
            exit_code = 1
    # If not redirected, out/err remain for pipe chaining or final print
    # For non-piped single command, we already printed via redirect? Actually we captured, so need to emit to real stdout if not redirected
    # Caller decides: for top-level single command without pipe, print directly. But we captured, so emit now if not part of pipeline
    # We will let pipeline caller handle printing; for direct call with no pipe, print here
    # This function is low-level, caller will print if pipeline
    # For now return; the wrapper _dispatch_single_with_operators will handle printing
    return exit_code, out, err

def _dispatch_single(line: str, stdin_data: str | None = None) -> bool | None:
    """Dispatch a single command without operators. Returns False to quit, True/None to continue. Sets _last_exit_code."""
    global _last_exit_code
    raw = line.strip()
    if not raw:
        _last_exit_code = 0
        return True
    # variable expansion first (except for export which we want raw? but expand anyway)
    # Don't expand inside single quotes — expand_shell_vars respects that
    raw_expanded = expand_shell_vars(raw)
    # Update raw to expanded for parsing (but keep original for fallback shell)
    raw = raw_expanded
    # shlex parse
    try:
        parts = shlex.split(raw, posix=True)
    except ValueError:
        try:
            parts = shlex.split(raw, posix=False)
        except ValueError:
            parts = raw.split()
    if not parts:
        _last_exit_code = 0
        return True
    cmd = parts[0].lower()
    # handle `VAR=value` inline assignment without export (real .sh: FOO=bar cmd)
    if "=" in parts[0] and not parts[0].startswith("-"):
        # Check if first token is VAR=val
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=.*', parts[0]):
            # Handle assignments prefixing a command: FOO=bar echo hi  or just FOO=bar
            assignments = []
            idx = 0
            while idx < len(parts) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=.*', parts[idx]):
                k, v = parts[idx].split("=", 1)
                if len(v) >= 2 and v[0]==v[-1] and v[0] in ('"',"'"):
                    v = v[1:-1]
                assignments.append((k, v))
                idx += 1
            if idx >= len(parts):
                # Only assignments, set env and done
                for k, v in assignments:
                    os.environ[k] = v
                _last_exit_code = 0
                return True
            else:
                # Assignments + command: temporarily set env for this command
                old = {}
                for k, v in assignments:
                    old[k] = os.environ.get(k)
                    os.environ[k] = v
                # Reconstruct command without assignments
                remaining = " ".join(shlex.quote(p) for p in parts[idx:])
                # Need to reconstruct arg preservation? Use raw after assignments
                # Simpler: join remaining parts as line
                result = _dispatch_single(remaining, stdin_data=stdin_data)
                # Restore? In real sh, VAR=val cmd is temporary, not persistent. Restore old.
                for k, v in assignments:
                    if old[k] is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = old[k]
                return result

    try:
        _, arg = raw.split(None, 1)
        arg = arg.strip()
    except ValueError:
        arg = ""

    # pyshell meta
    if cmd == "pyshell":
        sub = parts[1].lower() if len(parts) > 1 else ""
        if sub in ("--version", "-v", "version"):
            cmd_version()
            _last_exit_code = 0
        elif sub in ("quit", "exit", "q"):
            _last_exit_code = 0
            return False
        elif sub in ("config", "cfg"):
            cmd_pyshell_config()
            _last_exit_code = 0
        else:
            print(f"{BR_YELLOW}usage: pyshell --version | pyshell quit | pyshell config{R}")
            _last_exit_code = 1
        return True

    # direct commands
    if cmd in ("quit", "exit", "q"):
        _last_exit_code = 0
        return False
    if cmd == "ls":
        cmd_ls(arg)
        _last_exit_code = 0
    elif cmd == "cd":
        cmd_cd(arg)
        _last_exit_code = 0
    elif cmd in ("pwd",):
        cmd_pwd(arg)
        _last_exit_code = 0
    elif cmd == "pyfetch":
        cmd_pyfetch(arg)
        _last_exit_code = 0
    elif cmd == "time":
        cmd_time(arg)
        _last_exit_code = 0
    elif cmd in ("clear", "cls"):
        clear_screen()
        _last_exit_code = 0
    elif cmd == "cat":
        # support stdin_data (pipe) — if stdin_data provided and no file, print stdin
        if stdin_data is not None and not arg.strip():
            print(stdin_data, end="" if stdin_data.endswith("\n") else "\n")
            _last_exit_code = 0
        else:
            # if stdin_data + file, grep style? just cat files
            cmd_cat(arg)
            _last_exit_code = 0
    elif cmd == "echo":
        cmd_echo(arg)
        _last_exit_code = 0
    elif cmd == "cp":
        cmd_cp(arg)
    elif cmd == "mv":
        cmd_mv(arg)
    elif cmd == "mkdir":
        cmd_mkdir(arg)
    elif cmd == "rm":
        cmd_rm(arg)
    elif cmd == "rmdir":
        cmd_rmdir(arg)
    elif cmd == "touch":
        cmd_touch(arg)
    elif cmd == "grep":
        cmd_grep(arg, stdin_data=stdin_data)
    elif cmd == "export":
        cmd_export(arg)
    elif cmd == "unset":
        cmd_unset(arg)
    elif cmd == "env":
        if stdin_data is not None:
            print(stdin_data, end="")
        cmd_env(arg)
    elif cmd in ("source", "."):
        cmd_source(arg)
    elif cmd == "history":
        cmd_history(arg)
    elif cmd == "whoami":
        cmd_whoami(arg)
        _last_exit_code = 0
    elif cmd == "hostname":
        cmd_hostname(arg)
        _last_exit_code = 0
    elif cmd in ("help", "?", "h"):
        cmd_help(arg)
        _last_exit_code = 0
    elif cmd == "rps":
        try:
            from .Builtin import RockPaperScissors
            RockPaperScissors.rock_paper_scissors()
            _last_exit_code = 0
        except Exception as e:
            print(f"{BR_RED}rps: {e}{R}")
            _last_exit_code = 1
    elif cmd == "matrix":
        cmd_matrix(arg)
        _last_exit_code = 0
    else:
        # external command — support pipe stdin_data via input
        try:
            if stdin_data is not None:
                result = subprocess.run(raw, shell=True, input=stdin_data, text=True)
            else:
                result = subprocess.run(raw, shell=True)
            _last_exit_code = result.returncode if result.returncode is not None else 0
            if _last_exit_code != 0 and result.returncode is None:
                _last_exit_code = 0
        except Exception as e:
            print(f"{BR_RED}{cmd}: command not found ({e}){R}")
            print(f"{DIM}type 'help' for built-ins{R}")
            _last_exit_code = 127
    return True

def dispatch(line: str) -> bool:
    """Top-level real .sh dispatcher: handles ; && || | > >> < & and comments. Returns False to quit."""
    global _last_exit_code
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return True
    # Handle background & at end (real .sh: cmd &)
    is_background = False
    if raw.endswith("&") and not raw.endswith("&&") and not _is_quoted(raw, len(raw)-1):
        # check not inside quotes and not && 
        stripped = raw[:-1].strip()
        if _find_unquoted(stripped + " &", " &") != -1 or raw.rstrip().endswith("&"):
            # simple: trailing & means background
            is_background = True
            raw = raw[:-1].strip()

    # 1) Handle ; (sequential) — split top-level ;
    # Must not split inside quotes, and not part of ;; etc. (simple)
    if _find_unquoted(raw, ";") != -1:
        parts = _split_unquoted(raw, ";")
        should_quit = False
        for part in parts:
            p = part.strip()
            if not p:
                continue
            res = dispatch(p)
            if res is False:
                should_quit = True
                break
        return False if should_quit else True

    # 2) Handle && and ||
    # We need to parse left-to-right
    # Find first && or || not in quotes
    # Recursively handle
    for op in ("&&", "||"):
        idx = _find_unquoted(raw, op)
        if idx != -1:
            left = raw[:idx].strip()
            right = raw[idx+len(op):].strip()
            # dispatch left first (with full operator handling)
            # Use a helper to get exit code without printing duplication? dispatch handles printing.
            # We need to capture exit code: run left, check _last_exit_code, then decide right
            cont = dispatch(left)
            if cont is False:
                return False
            left_code = _last_exit_code
            if op == "&&":
                if left_code == 0:
                    return dispatch(right)
                else:
                    return True
            else:  # ||
                if left_code != 0:
                    return dispatch(right)
                else:
                    return True

    # 3) Handle pipes | (not || already handled, not inside quotes)
    if _find_unquoted(raw, "|") != -1:
        # split by | not in quotes
        segments = _split_unquoted(raw, "|")
        # Need to handle each segment's redirections
        # Pipeline: output of segment i becomes stdin_data of i+1
        stdin_data = None
        last_code = 0
        # If background, run pipeline in background thread?
        # For simplicity, if pipeline and background, run all in subprocess shell
        if is_background:
            # delegate entire pipeline to system shell background
            try:
                subprocess.Popen(raw + " | ".join(segments), shell=True)
                print(f"{DIM}[bg] pipeline started{R}")
                _last_exit_code = 0
                return True
            except Exception as e:
                print(f"{BR_RED}bg: {e}{R}")
                _last_exit_code = 1
                return True
        for idx, seg in enumerate(segments):
            seg = seg.strip()
            if not seg:
                continue
            clean, si, so, so_a, se, se_a, se2out = _extract_redirections(seg)
            # For intermediate pipes, ignore stdout redirection except last? but keep as is for last
            # If not last segment, stdout redirection should still be honored? Real sh: cmd > file | other reads empty
            # So honor it
            code, out, err = _run_single_with_redirects(clean, si, so, so_a, se, se_a, se2out, stdin_data=stdin_data)
            last_code = code
            # If stdout was redirected to file, out is "" — pipeline gets empty
            # err is printed already? _run_single_with_redirects captures but doesn't print for pipeline intermediates
            # For pipeline, we need to feed out to next; err should go to real stderr immediately
            if err:
                sys.stderr.write(err)
                if not err.endswith("\n"):
                    sys.stderr.write("\n")
            # stdout file redirection consumed out, so next gets empty
            # Only last segment prints to real stdout if not redirected
            if idx == len(segments) - 1:
                # last segment: print out/err to real terminal if not redirected
                if out:
                    sys.stdout.write(out)
                    if not out.endswith("\n"):
                        sys.stdout.write("\n")
                    sys.stdout.flush()
                if err:
                    pass  # already printed
            else:
                # intermediate: out becomes stdin_data for next
                stdin_data = out
                # we ignore err for pipe (already printed)
        _last_exit_code = last_code
        return True

    # 4) No pipes: handle single command with redirections
    clean, si, so, so_a, se, se_a, se2out = _extract_redirections(raw)
    if si or so or se or se2out:
        code, out, err = _run_single_with_redirects(clean, si, so, so_a, se, se_a, se2out, stdin_data=None)
        _last_exit_code = code
        # Print captured out/err if not redirected to file
        if out:
            sys.stdout.write(out)
            if not out.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
        if err:
            sys.stderr.write(err)
            if not err.endswith("\n"):
                sys.stderr.write("\n")
            sys.stderr.flush()
        return True
    else:
        # No redirections, no pipes: direct dispatch
        if is_background:
            # run in background
            try:
                subprocess.Popen(clean, shell=True)
                print(f"{DIM}[bg] {clean} &{R}")
                _last_exit_code = 0
                return True
            except Exception as e:
                print(f"{BR_RED}bg: {e}{R}")
                _last_exit_code = 1
                return True
        res = _dispatch_single(clean, stdin_data=None)
        # _dispatch_single already printed directly (not captured), so nothing to do
        if res is False:
            return False
        return True

# ---------------------------------------------------------------------------
# main loop
# ---------------------------------------------------------------------------

def load_history():
    try:
        if HISTORY_FILE.exists():
            # try readline
            try:
                import readline  # type: ignore
                readline.read_history_file(str(HISTORY_FILE))
            except Exception:
                pass
    except Exception:
        pass

def save_history():
    try:
        try:
            import readline  # type: ignore
            readline.write_history_file(str(HISTORY_FILE))
        except Exception:
            pass
    except Exception:
        pass

def _run_script_file(path: Path):
    """Run a .sh script file non-interactively (real .sh mode)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"{BR_RED}pyshell: {path}: {e}{R}", file=sys.stderr)
        sys.exit(1)
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("#!"):
            continue
        # dispatch returns False on quit — break
        if not dispatch(stripped):
            break
    sys.exit(_last_exit_code)

def main():
    # --- real .sh: handle CLI args before interactive ---
    # pyshell.py [--version|--help|-c "cmd"|script.sh]
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        if arg1 in ("--version", "-v", "version"):
            cmd_version()
            sys.exit(0)
        elif arg1 in ("--help", "-h", "help"):
            cmd_help()
            print(f"\n{DIM}Usage as real .sh:{R}")
            print(f"  ./pyshell.sh                  # interactive")
            print(f"  ./pyshell.sh script.sh        # run .sh script")
            print(f"  ./pyshell.sh -c \"ls | grep py > out\" # one-liner")
            print(f"  python pyshell.py script.sh   # same")
            print(f"  source pyshell.sh             # source in current shell")
            sys.exit(0)
        elif arg1 in ("-c", "--command"):
            if len(sys.argv) < 3:
                print(f"{BR_RED}pyshell: -c requires a command{R}", file=sys.stderr)
                sys.exit(1)
            cmd_str = " ".join(sys.argv[2:])
            # support multiple commands via ; already in dispatch
            dispatch(cmd_str)
            sys.exit(_last_exit_code)
        elif Path(arg1).exists() and Path(arg1).is_file():
            # script file execution (real .sh)
            _run_script_file(Path(arg1))
        elif arg1.endswith(".sh") or arg1.endswith(".bash"):
            print(f"{BR_RED}pyshell: {arg1}: No such file{R}", file=sys.stderr)
            sys.exit(1)

    # Start in OS-specific home ( ~ on Linux, C:\ on Windows ) as requested
    try:
        home = get_pyshell_home()
        if home.exists():
            os.chdir(home)
    except Exception:
        pass
    print_banner()
    # Show where pyshell home is
    try:
        h = get_pyshell_home()
        if platform.system() == "Windows":
            print(f"{DIM}home: C:\\  (use 'cd ~' or 'cd C:\\' to return){R}")
        else:
            print(f"{DIM}home: ~ ({h})  (use 'cd ~' or 'cd /home/{username}'){R}")
    except Exception:
        pass
    load_history()
    # enable tab completion for built-ins if readline available
    try:
        import readline  # type: ignore
        cmds = ["ls", "cd", "pwd", "pyfetch", "time", "clear", "cls", "cat", "echo", "cp", "mv", "mkdir", "rm", "rmdir", "touch", "grep", "export", "unset", "env", "source", ".", "history", "whoami", "hostname", "help", "rps", "matrix", "quit", "exit", "pyshell"]
        def completer(text, state):
            opts = [c for c in cmds if c.startswith(text)]
            return opts[state] if state < len(opts) else None
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")
        readline.set_history_length(500)
    except Exception:
        pass

    while True:
        try:
            # OS-aware prompt: show ~ for Linux home, C:\ for Windows home
            try:
                cwd_path = Path.cwd()
                home = get_pyshell_home()
                cwd_str = str(cwd_path)
                home_str = str(home)
                # Resolve for accurate comparison
                try:
                    cwd_res = str(cwd_path.resolve())
                    home_res = str(home.resolve())
                except Exception:
                    cwd_res = cwd_str
                    home_res = home_str
                if platform.system() == "Windows":
                    # Windows home is C:\
                    if cwd_res == home_res:
                        cwd_display = "C:\\"
                    else:
                        # Keep full Windows path (don't map C:\Users -> ~)
                        cwd_display = cwd_str
                        # Optionally show ~ if in real user profile and they typed ~
                        # But keep as is for clarity
                else:
                    # Linux/macOS: ~ for /home/$USER
                    if cwd_res == home_res:
                        cwd_display = "~"
                    elif cwd_res.startswith(home_res + os.sep):
                        cwd_display = "~" + cwd_str[len(home_str):]
                    else:
                        cwd_display = cwd_str
            except Exception:
                cwd_display = str(Path.cwd())
            prompt = f"{BR_GREEN}{username}{R}{BR_WHITE}@{R}{BR_CYAN}{computer}{R} {DIM}{cwd_display}{R} $> "
            line = input(prompt)
            # save to readline history + file (real .sh history)
            try:
                import readline  # type: ignore
                # readline auto adds, but ensure
                pass
            except Exception:
                pass
            # also append to history file for `history` builtin (works without readline)
            try:
                with open(HISTORY_FILE, "a", encoding="utf-8", errors="replace") as hf:
                    hf.write(line + "\n")
            except Exception:
                pass
            if not dispatch(line):
                break
        except KeyboardInterrupt:
            print(f"\n{BR_YELLOW}Use 'quit' or 'pyshell quit' to exit{R}")
            continue
        except EOFError:
            break
        except Exception as e:
            print(f"{BR_RED}error: {e}{R}")
            continue

    save_history()
    print(f"\n{BR_BLACK}[  {time.time():.4f}] Status: Quiting pyshell...{R}")

if __name__ == "__main__":
    main()
