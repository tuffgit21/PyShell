#!/usr/bin/env python3
"""
pyshell — matrix.py
A tiny, fast, cross-platform shell with pyfetch integration.

Built-in commands:
  pyshell --version, pyshell quit, pyshell config, pyshell --refresh/-r, pyshell theme [list|set|preview], p10k configure, pyshell prompt [list|set|preview], refresh/ref/reload
  ls, cd, pwd, time, clear, help, cat, echo, whoami, hostname, theme/p10k/format/prompt, rps, world
  + Unix-replicating (also in CMD_LIST, hidden from help.html): cp, mv, mkdir, rm, rmdir, touch, grep, export, unset, env, source
  Themes: dark, light, dracula, nord, monokai, solarized, matrix, ocean, sunset, neon, p10k, p10k_lean, p10k_rainbow (powerlevel10k)
  Formats: classic, pure, minimal, two-line, git, nerd, compact, full, p10k, powerline

pyfetch supports full args: pyfetch --image ./logo.png --logo arch --no-color
Config: pyshell_config.json (validated — warns if missing/invalid/empty)
"""

from __future__ import annotations

import contextlib
import datetime
import getpass
import glob as globmod
import importlib
import io
import json
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
BR_BLUE = "\033[94m"
BR_MAGENTA = "\033[95m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
# Backgrounds for powerlevel10k segments
BG_BLACK = "\033[40m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_CYAN = "\033[46m"
BG_WHITE = "\033[47m"
BG_BR_BLACK = "\033[100m"
BG_BR_RED = "\033[101m"
BG_BR_GREEN = "\033[102m"
BG_BR_YELLOW = "\033[103m"
BG_BR_BLUE = "\033[104m"
BG_BR_MAGENTA = "\033[105m"
BG_BR_CYAN = "\033[106m"
BG_BR_WHITE = "\033[107m"
# Powerline glyphs (fallback to > if font missing)
POWERLINE_RIGHT = ""
POWERLINE_RIGHT_THIN = ""
POWERLINE_LEFT = ""
POWERLINE_LEFT_THIN = ""

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Themes — presets + custom overrides
# ---------------------------------------------------------------------------
COLOR_MAP: dict[str, str] = {
    "reset": R,
    "bold": BOLD,
    "dim": DIM,
    "green": GREEN,
    "cyan": CYAN,
    "yellow": YELLOW,
    "blue": BLUE,
    "magenta": MAGENTA,
    "red": BR_RED,
    "black": BR_BLACK,
    "white": BR_WHITE,
    "bright_green": BR_GREEN,
    "bright_cyan": BR_CYAN,
    "bright_yellow": BR_YELLOW,
    "bright_red": BR_RED,
    "bright_black": BR_BLACK,
    "bright_white": BR_WHITE,
    "bright_blue": BR_BLUE,
    "bright_magenta": BR_MAGENTA,
    "bright_cyan": BR_CYAN,
    # backgrounds for p10k
    "bg_black": BG_BLACK,
    "bg_red": BG_RED,
    "bg_green": BG_GREEN,
    "bg_yellow": BG_YELLOW,
    "bg_blue": BG_BLUE,
    "bg_magenta": BG_MAGENTA,
    "bg_cyan": BG_CYAN,
    "bg_white": BG_WHITE,
    "bg_bright_black": BG_BR_BLACK,
    "bg_bright_red": BG_BR_RED,
    "bg_bright_green": BG_BR_GREEN,
    "bg_bright_yellow": BG_BR_YELLOW,
    "bg_bright_blue": BG_BR_BLUE,
    "bg_bright_magenta": BG_BR_MAGENTA,
    "bg_bright_cyan": BG_BR_CYAN,
    "bg_bright_white": BG_BR_WHITE,
}

THEMES: dict[str, dict] = {
    "dark": {
        "name": "Dark",
        "description": "Default — cyan banner, green user, dim cwd",
        "banner": "bright_cyan",
        "user": "bright_green",
        "host": "bright_cyan",
        "cwd": "dim",
        "symbol": "white",
        "git": "bright_yellow",
        "error": "bright_red",
        "success": "bright_green",
    },
    "light": {
        "name": "Light",
        "description": "For light terminals — blue banner, muted tones",
        "banner": "blue",
        "user": "blue",
        "host": "magenta",
        "cwd": "black",
        "symbol": "black",
        "git": "yellow",
        "error": "red",
        "success": "green",
    },
    "dracula": {
        "name": "Dracula",
        "description": "Purple/pink — popular Dracula palette",
        "banner": "bright_magenta",
        "user": "bright_green",
        "host": "bright_magenta",
        "cwd": "dim",
        "symbol": "bright_white",
        "git": "bright_yellow",
        "error": "bright_red",
        "success": "bright_green",
    },
    "nord": {
        "name": "Nord",
        "description": "Arctic blues — Nord inspired",
        "banner": "bright_cyan",
        "user": "bright_blue",
        "host": "bright_white",
        "cwd": "cyan",
        "symbol": "white",
        "git": "bright_yellow",
        "error": "bright_red",
        "success": "bright_cyan",
    },
    "monokai": {
        "name": "Monokai",
        "description": "Warm — Monokai yellow/pink/green",
        "banner": "bright_yellow",
        "user": "bright_green",
        "host": "bright_magenta",
        "cwd": "yellow",
        "symbol": "white",
        "git": "bright_yellow",
        "error": "bright_red",
        "success": "bright_green",
    },
    "solarized": {
        "name": "Solarized",
        "description": "Solarized — yellow/cyan/blue",
        "banner": "yellow",
        "user": "cyan",
        "host": "blue",
        "cwd": "dim",
        "symbol": "white",
        "git": "yellow",
        "error": "red",
        "success": "green",
    },
    "matrix": {
        "name": "Matrix",
        "description": "All green — Matrix rain vibe",
        "banner": "bright_green",
        "user": "bright_green",
        "host": "green",
        "cwd": "green",
        "symbol": "bright_green",
        "git": "bright_green",
        "error": "bright_red",
        "success": "bright_green",
    },
    "ocean": {
        "name": "Ocean",
        "description": "Deep blues/cyans — ocean",
        "banner": "bright_blue",
        "user": "bright_cyan",
        "host": "bright_blue",
        "cwd": "cyan",
        "symbol": "white",
        "git": "bright_cyan",
        "error": "bright_red",
        "success": "bright_cyan",
    },
    "sunset": {
        "name": "Sunset",
        "description": "Warm oranges — sunset",
        "banner": "bright_yellow",
        "user": "bright_yellow",
        "host": "bright_red",
        "cwd": "yellow",
        "symbol": "white",
        "git": "bright_magenta",
        "error": "bright_red",
        "success": "bright_yellow",
    },
    "neon": {
        "name": "Neon",
        "description": "High contrast — neon pink/cyan",
        "banner": "bright_magenta",
        "user": "bright_cyan",
        "host": "bright_magenta",
        "cwd": "bright_white",
        "symbol": "bright_yellow",
        "git": "bright_cyan",
        "error": "bright_red",
        "success": "bright_green",
    },
    # ── Powerlevel10k family ──
    "p10k": {
        "name": "Powerlevel10k",
        "description": "p10k classic — powerline , git, icons (requires Nerd Font)",
        "banner": "bright_cyan",
        "user": "bright_white",
        "host": "bright_white",
        "cwd": "bright_white",
        "symbol": "bright_green",
        "git": "bright_white",
        "error": "bright_red",
        "success": "bright_green",
        "p10k": True,
        "style": "classic",
        "segments": {
            "os": {"bg": "bg_bright_black", "fg": "bright_white", "icon": ""},
            "context": {"bg": "bg_bright_black", "fg": "bright_yellow", "icon": ""},
            "dir": {"bg": "bg_bright_blue", "fg": "bright_white", "icon": ""},
            "vcs": {"bg": "bg_bright_green", "fg": "black", "icon": ""},
            "status": {"bg": "bg_bright_black", "fg": "bright_red"},
        },
    },
    "p10k_lean": {
        "name": "Powerlevel10k Lean",
        "description": "p10k lean — no powerline bg, 8-color, fast",
        "banner": "cyan",
        "user": "cyan",
        "host": "cyan",
        "cwd": "bright_blue",
        "symbol": "bright_green",
        "git": "yellow",
        "error": "red",
        "success": "green",
        "p10k": True,
        "style": "lean",
        "segments": {
            "os": {"bg": "", "fg": "bright_black", "icon": ""},
            "context": {"bg": "", "fg": "yellow", "icon": ""},
            "dir": {"bg": "", "fg": "bright_blue", "icon": ""},
            "vcs": {"bg": "", "fg": "green", "icon": ""},
            "status": {"bg": "", "fg": "red"},
        },
    },
    "p10k_rainbow": {
        "name": "Powerlevel10k Rainbow",
        "description": "p10k rainbow — colorful powerline per segment",
        "banner": "bright_magenta",
        "user": "bright_yellow",
        "host": "bright_cyan",
        "cwd": "bright_white",
        "symbol": "bright_green",
        "git": "bright_white",
        "error": "bright_red",
        "success": "bright_green",
        "p10k": True,
        "style": "rainbow",
        "segments": {
            "os": {"bg": "bg_bright_magenta", "fg": "bright_white", "icon": ""},
            "context": {"bg": "bg_bright_yellow", "fg": "black", "icon": ""},
            "dir": {"bg": "bg_bright_cyan", "fg": "black", "icon": ""},
            "vcs": {"bg": "bg_bright_green", "fg": "black", "icon": ""},
            "status": {"bg": "bg_red", "fg": "bright_white"},
        },
    },
}

FORMAT_PRESETS: dict[str, dict] = {
    "classic": {
        "name": "Classic",
        "description": "Classic — user@host cwd $>",
        "format": "{user}@{host} {cwd} $> ",
        "git_branch": False,
    },
    "pure": {
        "name": "Pure",
        "description": "Pure — minimal cwd ❯ (like pure)",
        "format": "{cwd} ❯ ",
        "git_branch": False,
    },
    "minimal": {
        "name": "Minimal",
        "description": "Minimal — just $>",
        "format": "$> ",
        "git_branch": False,
    },
    "two-line": {
        "name": "Two-line",
        "description": "Two-line — user@host cwd on first line, ❯ on second",
        "format": "{user}@{host} {cwd}\n❯ ",
        "git_branch": False,
    },
    "git": {
        "name": "Git",
        "description": "Git — classic + branch {git}",
        "format": "{user}@{host} {cwd} {git} $> ",
        "git_branch": True,
    },
    "nerd": {
        "name": "Nerd",
        "description": "Nerd — with icons and ❯, git branch",
        "format": "{user}@{host} {cwd} {git} ❯ ",
        "git_branch": True,
    },
    "compact": {
        "name": "Compact",
        "description": "Compact — cwd with git, $>",
        "format": "{cwd} {git}$> ",
        "git_branch": True,
    },
    "full": {
        "name": "Full",
        "description": "Full — [user@host] cwd git on first line",
        "format": "[{user}@{host}] {cwd} {git}\n$> ",
        "git_branch": True,
    },
    "p10k": {
        "name": "Powerlevel10k",
        "description": "p10k — powerline prompt (use p10k theme)",
        "format": "{p10k}",
        "git_branch": False,
    },
    "powerline": {
        "name": "Powerline",
        "description": "Powerline — user@host  cwd  git — fallback if no Nerd Font",
        "format": "{user}  {cwd}  {git} ❯ ",
        "git_branch": True,
    },
    "time": {
        "name": "Time",
        "description": "Time — user@host time cwd $>  (new {current_time})",
        "format": "{user}@{host} {current_time} {cwd} $> ",
        "git_branch": False,
    },
}

def _color(name: str) -> str:
    return COLOR_MAP.get(name.lower(), COLOR_MAP.get(name, R))

def _get_time_str(fmt: str = "%H:%M:%S") -> str:
    try:
        return datetime.datetime.now().strftime(fmt)
    except Exception:
        return ""

def _current_theme_name() -> str:
    try:
        n = str(PYSHELL_CONFIG.get("appearance", {}).get("theme", "dark")).lower()
        return n if n in _all_themes() else "dark"
    except Exception:
        return "dark"

def _theme_colors(name: str | None = None) -> dict[str, str]:
    tname = (name or _current_theme_name()).lower()
    base = _all_themes().get(tname, THEMES["dark"])
    # custom overrides via appearance.custom_colors or banner_color
    # banner_color overrides theme banner if set and not empty
    custom = {}
    try:
        app = PYSHELL_CONFIG.get("appearance", {})
        if isinstance(app.get("custom_colors"), dict):
            for k, v in app["custom_colors"].items():
                if isinstance(v, str) and v.lower() in COLOR_MAP:
                    custom[k] = v.lower()
        # legacy banner_color — only if no custom banner override
        bc = app.get("banner_color")
        if isinstance(bc, str) and bc.strip() and bc.lower() in COLOR_MAP:
            if "banner" not in custom:
                custom["banner"] = bc.lower()
    except Exception:
        pass
    merged = dict(base)
    merged.update(custom)
    # resolve to ANSI
    return {k: _color(v) if k in ("banner","user","host","cwd","symbol","git","error","success") else v for k, v in merged.items()}

def _all_themes() -> dict:
    """All themes including custom_themes from config."""
    base = dict(THEMES)
    try:
        custom = PYSHELL_CONFIG.get("appearance", {}).get("custom_themes", {})
        if isinstance(custom, dict):
            for k, v in custom.items():
                if isinstance(v, dict) and "name" in v:
                    base[k.lower()] = v
                elif isinstance(v, dict):
                    # allow shorthand without name
                    base[k.lower()] = {"name": k, "description": "Custom", **v}
    except Exception:
        pass
    return base

def _all_formats() -> dict:
    """All formats including custom_formats from config."""
    base = dict(FORMAT_PRESETS)
    try:
        custom = PYSHELL_CONFIG.get("prompt", {}).get("custom_formats", {})
        if isinstance(custom, dict):
            for k, v in custom.items():
                if isinstance(v, dict) and "format" in v:
                    base[k.lower()] = v
                elif isinstance(v, str):
                    base[k.lower()] = {"name": k, "description": "Custom", "format": v, "git_branch": "{git}" in v}
    except Exception:
        pass
    return base

def _current_format_preset() -> str:
    try:
        preset = PYSHELL_CONFIG.get("prompt", {}).get("preset", "")
        if isinstance(preset, str) and preset.lower() in _all_formats():
            return preset.lower()
        cur_fmt = PYSHELL_CONFIG.get("prompt", {}).get("format", "")
        for k, v in _all_formats().items():
            if v["format"] == cur_fmt:
                return k
        return "custom"
    except Exception:
        return "custom"

def _is_p10k_theme(name: str | None = None) -> bool:
    tname = (name or _current_theme_name()).lower()
    th = _all_themes().get(tname, {})
    return bool(th.get("p10k"))

def _get_git_p10k() -> tuple[str, bool, bool]:
    """Return (branch, dirty, ahead) for p10k vcs segment."""
    try:
        # branch
        br = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
        if not br or br == "HEAD":
            # detached or no git
            return "", False, False
        # dirty: check porcelain
        dirty = False
        ahead = False
        try:
            status = subprocess.check_output(["git", "status", "--porcelain", "-b"], stderr=subprocess.DEVNULL, text=True)
            if status:
                lines = status.splitlines()
                # first line is ## branch... [ahead/behind]
                if len(lines) > 1:
                    dirty = True
                # check ahead
                if lines and "ahead" in lines[0]:
                    ahead = True
                # also check untracked/modified
                for l in lines[1:]:
                    if l.strip():
                        dirty = True
                        break
        except Exception:
            pass
        return br, dirty, ahead
    except Exception:
        return "", False, False

def _render_p10k_prompt(username: str, computer: str, cwd_display: str, git_str: str, exit_code: int, tc: dict, th: dict) -> str:
    """Build powerlevel10k-like prompt with powerline segments."""
    style = th.get("style", "classic")  # classic / lean / rainbow
    segs = th.get("segments", {})
    # Use powerline glyphs if not lean, else simple separators
    use_powerline = style != "lean"
    sep = POWERLINE_RIGHT if use_powerline else " "
    sep_thin = POWERLINE_RIGHT_THIN if use_powerline else " "

    # Helper to make segment with bg/fg
    def seg(text: str, bg_key: str, fg_key: str, icon: str = "") -> str:
        bg = _color(segs.get(bg_key, {}).get("bg", "") if isinstance(segs.get(bg_key), dict) else th.get(bg_key, ""))
        # Actually segs is per-segment dict, but we passed bg_key as segment name
        # For generic, fetch segment config
        seg_cfg = segs.get(bg_key, {}) if isinstance(segs.get(bg_key), dict) else {}
        bg_c = _color(seg_cfg.get("bg", "")) if seg_cfg.get("bg") else ""
        fg_c = _color(seg_cfg.get("fg", th.get(fg_key, fg_key))) if seg_cfg else _color(th.get(fg_key, fg_key))
        # Lean style: no bg
        if style == "lean" or not bg_c:
            # lean: just fg + icon + text
            ic = f"{icon} " if icon else ""
            return f"{fg_c}{ic}{text}{R}"
        else:
            ic = f"{icon} " if icon else ""
            # bg + fg + text
            return f"{bg_c}{fg_c} {ic}{text} {R}"

    # Build left segments
    parts = []
    # OS icon segment — only for classic/rainbow
    if style != "lean":
        os_cfg = segs.get("os", {})
        os_icon = os_cfg.get("icon", "") if os_cfg else ""
        # Determine OS icon by platform
        if platform.system() == "Windows":
            os_icon = ""
        elif platform.system() == "Darwin":
            os_icon = ""
        else:
            os_icon = os_cfg.get("icon", "") if os_cfg else ""
        parts.append(seg(os_icon, "os", "os"))

    # Context segment user@host — show if not default? p10k shows when not default user
    ctx_cfg = segs.get("context", {})
    ctx_text = f"{username}@{computer}"
    # optionally hide host if local? keep for now
    parts.append(seg(ctx_text, "context", "user", ctx_cfg.get("icon", "")))

    # Dir segment
    dir_cfg = segs.get("dir", {})
    # powerlevel10k shows dir with truncation and icons
    dir_icon = dir_cfg.get("icon", "")
    # shorten cwd for p10k: show ~ or last 3 parts
    dir_text = cwd_display
    if len(dir_text) > 30 and style != "lean":
        # keep p10k truncation: ~/.../last2
        norm = dir_text.replace("\\", "/")
        pp = [p for p in norm.split("/") if p]
        if len(pp) > 3:
            dir_text = "/".join(pp[-3:])
            if dir_text.startswith("C:"):
                dir_text = dir_text
            elif cwd_display.startswith("~"):
                dir_text = "~/" + dir_text
    parts.append(seg(dir_text, "dir", "cwd", dir_icon))

    # VCS segment
    branch, dirty, ahead = _get_git_p10k()
    # Use provided git_str if p10k git disabled? For lean, use simple branch
    if not branch and git_str:
        branch = git_str.strip("()")
        dirty = False
    if branch:
        vcs_cfg = segs.get("vcs", {})
        icon = vcs_cfg.get("icon", "")
        vcs_text = f"{icon} {branch}"
        if dirty:
            vcs_text += " ●"  # dirty marker
        if ahead:
            vcs_text += " ⇡"
        parts.append(seg(vcs_text, "vcs", "git"))

    # Status segment if last exit !=0
    if exit_code != 0:
        stat_cfg = segs.get("status", {})
        parts.append(seg(f"✘ {exit_code}", "status", "error", ""))

    # Join with powerline separators
    if use_powerline and style == "classic":
        # Classic powerline: each segment's separator colored as bg of next
        # Simplified: join with  where separator fg = current bg, bg = next bg
        prompt = ""
        for i, p in enumerate(parts):
            prompt += p
            if i < len(parts) - 1:
                # separator: fg = current bg, bg = next bg
                cur_bg = _color(segs.get(list(segs.keys())[i], {}).get("bg", "")) if i < len(segs) else ""
                nxt = list(segs.keys())[i+1] if i+1 < len(segs) else None
                nxt_bg = _color(segs.get(nxt, {}).get("bg", "")) if nxt and segs.get(nxt, {}).get("bg") else ""
                # fallback: use next segment's bg
                if cur_bg and nxt_bg:
                    prompt += f"{cur_bg}{_color(segs.get(nxt, {}).get('fg',''))}{POWERLINE_RIGHT}{R}"
                else:
                    prompt += f" {POWERLINE_RIGHT} "
        # prompt char
        tc_sym = tc.get("symbol", BR_WHITE)
        prompt_char = "❯" if exit_code == 0 else "✘"
        # For p10k, prompt char color reflects status
        col = tc.get("success", BR_GREEN) if exit_code == 0 else tc.get("error", BR_RED)
        prompt += f" {col}{prompt_char}{R} "
        return prompt
    elif use_powerline and style == "rainbow":
        # Rainbow: each segment already has distinct bg, join with 
        prompt = f" {sep} ".join(parts)  # actually parts already include bg, so just join with separator
        # Simpler: just join parts with powerline char
        # Re-build with separators
        joined = ""
        for i, p in enumerate(parts):
            joined += p
            if i < len(parts)-1:
                joined += f"{POWERLINE_RIGHT}"
        tc_sym = tc.get("symbol", BR_WHITE)
        col = tc.get("success", BR_GREEN) if exit_code == 0 else tc.get("error", BR_RED)
        joined += f" {col}❯{R} "
        return joined
    else:
        # Lean: no bg, just colored text with thin separator
        lean = f" {sep_thin} ".join(parts)
        col = tc.get("success", BR_GREEN) if exit_code == 0 else tc.get("error", BR_RED)
        lean += f" {col}❯{R} "
        return lean

# ---------------------------------------------------------------------------
# pyshell_config.json — single source for PyShell customization
# ---------------------------------------------------------------------------
DEFAULT_CONFIG: dict = {
    "prompt": {
        "format": "{user}@{host} {cwd} $> ",
        "preset": "classic",
        "color": True,
        "git_branch": False,
        "time": False,
        "custom_formats": {},
    },
    "history": {
        "file": "~/.pyshell_history",
        "max_lines": 500,
        "save_on_exit": True,
    },
    "behavior": {
        "clear_on_start": False,
        "confirm_exit": False,
        "expand_tilde": True,
    },
    "aliases": {
        "ll": "ls",
        "la": "ls -a",
        "hist": "history",
    },
    "appearance": {
        "banner": True,
        "banner_color": "cyan",
        "theme": "dark",
        "custom_colors": {},
        "custom_themes": {},
    },
    "startup": {
        "commands": [],
    },
}

# Sections that must exist and be non-empty (aliases may be empty but must be object)
REQUIRED_SECTIONS: dict[str, type] = {
    "prompt": dict,
    "history": dict,
    "behavior": dict,
    "aliases": dict,
    "appearance": dict,
    "startup": dict,
}

# Fields that must be non-empty if section exists
NON_EMPTY_FIELDS: dict[str, list[str]] = {
    "prompt": ["format"],
    "history": ["file"],
}

def get_config_path() -> Path:
    # On Linux, config lives in /home/$USER/.pyshell/pyshell-docs/pyshell_config.json (only inside pyshell-docs)
    if os.name != "nt" and platform.system() != "Windows":
        try:
            home = Path.home()
            docs_path = home / ".pyshell" / "pyshell-docs" / "pyshell_config.json"
            # Only inside pyshell-docs — always return docs_path on Linux
            if docs_path.exists() or docs_path.parent.exists() or home.exists() or (home / ".pyshell").exists():
                return docs_path
            return docs_path
        except Exception:
            pass
    return Path(__file__).parent / "pyshell_config.json"


def _ensure_linux_pyshell_dir() -> None:
    """On Linux, ensure /home/$USER/.pyshell exists and copy docs/config."""
    if os.name == "nt" or platform.system() == "Windows":
        return
    try:
        home = Path.home()
        if not str(home) or not home.exists():
            try:
                home = Path(f"/home/{username}")
            except Exception:
                home = Path("/home") / username if username else Path("/home")
        pyshell_dir = home / ".pyshell"
        pyshell_docs_dir = pyshell_dir / "pyshell-docs"
        # Only inside pyshell-docs — ensure ~/.pyshell/pyshell-docs exists
        try:
            pyshell_docs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            try:
                pyshell_dir.mkdir(parents=True, exist_ok=True)
                pyshell_docs_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        src_dir = Path(__file__).parent
        alt_dirs = [
            src_dir,
            Path("/usr/share/pyshell-docs"),
            Path("/usr/share/pyshell"),
            src_dir / "pyshell-docs",
        ]
        files = [
            "pyshell_config.json",
            "prompt_presets.txt",
            "custom_themes.txt",
            "themes.txt",
            "README.md",
        ]
        for fname in files:
            src = None
            for d in alt_dirs:
                cand = d / fname
                if cand.exists():
                    src = cand
                    break
            if src is None:
                src = src_dir / fname
                if not src.exists():
                    continue
            # Only inside pyshell-docs — copy exclusively to ~/.pyshell/pyshell-docs/
            dst = pyshell_docs_dir / fname
            try:
                # Don't overwrite existing user config
                if fname == "pyshell_config.json" and dst.exists():
                    continue
                shutil.copy2(src, dst)
            except Exception:
                try:
                    dst.write_bytes(src.read_bytes())
                except Exception:
                    pass
    except Exception:
        pass


def _is_empty_value(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, (dict, list)) and len(v) == 0:
        return True
    return False

def validate_pyshell_config(data: dict) -> list[str]:
    warnings: list[str] = []
    if not isinstance(data, dict):
        warnings.append("Config root must be a JSON object (got {}).".format(type(data).__name__))
        return warnings
    if not data:
        warnings.append("Config is empty ({}). All sections missing.".format(data))
        # also report each required section as missing
        for sec in REQUIRED_SECTIONS:
            warnings.append(f"Missing required section: '{sec}'")
        return warnings
    for sec, expected_type in REQUIRED_SECTIONS.items():
        if sec not in data:
            warnings.append(f"Missing required section: '{sec}'")
        elif not isinstance(data[sec], expected_type):
            warnings.append(f"Invalid section '{sec}': expected {expected_type.__name__}, got {type(data[sec]).__name__}")
        elif _is_empty_value(data[sec]):
            # aliases and startup.commands may be empty dict/list by design — only warn for core sections
            if sec in ("prompt", "history", "behavior", "appearance"):
                warnings.append(f"Empty section: '{sec}' is empty — needs values")
        else:
            # check required fields inside section
            for field in NON_EMPTY_FIELDS.get(sec, []):
                if field not in data[sec]:
                    warnings.append(f"Missing field '{sec}.{field}'")
                elif _is_empty_value(data[sec][field]):
                    warnings.append(f"Empty field: '{sec}.{field}' is empty")
                elif sec == "prompt" and field == "format" and not isinstance(data[sec][field], str):
                    warnings.append(f"Invalid field '{sec}.{field}': expected string")
                elif sec == "history" and field == "file" and not isinstance(data[sec][field], str):
                    warnings.append(f"Invalid field '{sec}.{field}': expected string")
            # extra type checks
            if sec == "history" and "max_lines" in data[sec] and not isinstance(data[sec]["max_lines"], int):
                warnings.append(f"Invalid field 'history.max_lines': expected int, got {type(data[sec]['max_lines']).__name__}")
            if sec == "prompt" and "color" in data[sec] and not isinstance(data[sec]["color"], bool):
                warnings.append(f"Invalid field 'prompt.color': expected bool")
            if sec == "prompt" and "time" in data[sec] and not isinstance(data[sec]["time"], bool):
                warnings.append(f"Invalid field 'prompt.time': expected bool")
            if sec == "prompt" and "preset" in data[sec]:
                if not isinstance(data[sec]["preset"], str):
                    warnings.append(f"Invalid field 'prompt.preset': expected string")
                elif data[sec]["preset"].lower() not in FORMAT_PRESETS and data[sec]["preset"].lower() != "custom":
                    # also allow custom_formats defined in this same config
                    custom_fmts = data.get("prompt", {}).get("custom_formats", {})
                    custom_keys = {k.lower() for k in custom_fmts.keys()} if isinstance(custom_fmts, dict) else set()
                    if data[sec]["preset"].lower() not in custom_keys:
                        warnings.append(f"Invalid preset '{data[sec]['preset']}': available {', '.join(FORMAT_PRESETS.keys())}, custom")
            if sec == "appearance" and "theme" in data[sec]:
                if not isinstance(data[sec]["theme"], str):
                    warnings.append(f"Invalid field 'appearance.theme': expected string")
                elif data[sec]["theme"].lower() not in THEMES:
                    # also allow custom_themes defined in this same config
                    custom_ths = data.get("appearance", {}).get("custom_themes", {})
                    custom_tkeys = {k.lower() for k in custom_ths.keys()} if isinstance(custom_ths, dict) else set()
                    if data[sec]["theme"].lower() not in custom_tkeys:
                        warnings.append(f"Invalid theme '{data[sec]['theme']}': available {', '.join(THEMES.keys())} (got '{data[sec]['theme']}')")
            if sec == "appearance" and "banner_color" in data[sec] and not isinstance(data[sec]["banner_color"], str):
                warnings.append(f"Invalid field 'appearance.banner_color': expected string")
            elif sec == "appearance" and "banner_color" in data[sec] and isinstance(data[sec]["banner_color"], str) and data[sec]["banner_color"].lower() not in COLOR_MAP:
                warnings.append(f"Invalid banner_color '{data[sec]['banner_color']}': available {', '.join(COLOR_MAP.keys())}")
            if sec == "appearance" and "custom_colors" in data[sec] and not isinstance(data[sec]["custom_colors"], dict):
                warnings.append(f"Invalid field 'appearance.custom_colors': expected object")
            elif sec == "appearance" and "custom_colors" in data[sec] and isinstance(data[sec]["custom_colors"], dict):
                for ck, cv in data[sec]["custom_colors"].items():
                    if cv.lower() not in COLOR_MAP:
                        warnings.append(f"Invalid custom_colors.{ck} '{cv}': available {', '.join(COLOR_MAP.keys())}")
    # warn about unknown top-level keys (not error, just info)
    for k in data:
        if k not in REQUIRED_SECTIONS:
            warnings.append(f"Unknown section: '{k}' (will be ignored)")
    return warnings

def _prompt_config_fix(warnings: list[str], cfg_path: Path, data: dict) -> dict:
    """Interactive warning prompt — returns corrected (or original) config dict."""
    print(f"\n{BR_YELLOW}{BOLD}⚠  pyshell_config.json — configuration issue detected{R}")
    print(f"{DIM}File: {cfg_path}{R}")
    for w in warnings:
        print(f"  {BR_YELLOW}• {w}{R}")
    print(f"{DIM}──────────────────────────────────────────────────{R}")
    # Non-interactive (piped / --help / -c) → don't block, just warn
    if not sys.stdin.isatty():
        print(f"{BR_BLACK}Non-interactive session — using defaults for missing/invalid parts.{R}")
        # merge defaults for missing/invalid
        fixed = {**DEFAULT_CONFIG}
        for k, v in data.items():
            if k in REQUIRED_SECTIONS and isinstance(v, REQUIRED_SECTIONS[k]) and not _is_empty_value(v):
                fixed[k] = v
        return fixed
    print(f"{BOLD}How to fix?{R}  [Y] Auto-repair (fill defaults)  /  [N] Continue with defaults  /  [E] Edit manually")
    try:
        ans = input(f"{BR_CYAN}Your choice [Y/n/e]: {R}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        ans = "n"
    if ans in ("", "y", "yes"):
        # auto-repair: merge defaults
        fixed = {}
        for sec, exp_type in REQUIRED_SECTIONS.items():
            if sec not in data or not isinstance(data[sec], exp_type) or _is_empty_value(data[sec]):
                if sec in ("prompt", "history", "behavior", "appearance") and _is_empty_value(data.get(sec)):
                    fixed[sec] = DEFAULT_CONFIG[sec]
                elif sec not in data:
                    fixed[sec] = DEFAULT_CONFIG[sec]
                else:
                    # invalid type → replace
                    fixed[sec] = DEFAULT_CONFIG[sec]
            else:
                # section exists and valid — merge missing fields
                merged = {**DEFAULT_CONFIG[sec], **data[sec]}
                # but if any required field empty/invalid, restore it
                for f in NON_EMPTY_FIELDS.get(sec, []):
                    if f not in data[sec] or _is_empty_value(data[sec][f]):
                        merged[f] = DEFAULT_CONFIG[sec][f]
                fixed[sec] = merged
        # keep unknown sections as-is
        for k, v in data.items():
            if k not in fixed:
                fixed[k] = v
        try:
            cfg_path.write_text(json.dumps(fixed, indent=2), encoding="utf-8")
            print(f"{BR_GREEN}✓ Config auto-repaired and saved to {cfg_path}{R}")
        except Exception as e:
            print(f"{BR_RED}Cannot write config: {e}{R}")
        return fixed
    elif ans in ("e", "edit"):
        print(f"{DIM}Opening editor for {cfg_path} ...{R}")
        try:
            if os.name == "nt":
                os.startfile(str(cfg_path))  # type: ignore[attr-defined]
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(cfg_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("open"):
                subprocess.Popen(["open", str(cfg_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                print(f"{DIM}Please edit manually: {cfg_path}{R}")
        except Exception as e:
            print(f"{BR_RED}Cannot open editor: {e}{R}")
        print(f"{DIM}Continuing with current (uncorrected) config — re-run 'pyshell config' after editing.{R}")
        return data
    else:
        print(f"{DIM}Continuing with defaults for missing parts (config not saved).{R}")
        merged = {**DEFAULT_CONFIG}
        for k, v in data.items():
            if k in REQUIRED_SECTIONS and isinstance(v, REQUIRED_SECTIONS[k]):
                merged[k] = v
        return merged

def load_pyshell_config(interactive: bool = True) -> dict:
    """Load pyshell_config.json, validate, and prompt if missing/invalid/empty."""
    cfg_path = get_config_path()
    if not cfg_path.exists():
        print(f"{BR_YELLOW}⚠ pyshell_config.json not found at {cfg_path}{R}")
        print(f"{DIM}Creating default config...{R}")
        try:
            cfg_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
            print(f"{BR_GREEN}✓ Default config created: {cfg_path}{R}")
        except Exception as e:
            print(f"{BR_RED}Cannot create config: {e}{R}")
        if interactive and sys.stdin.isatty():
            # also show that it was missing (counts as warning)
            _prompt_config_fix([f"Missing config file — created default at {cfg_path}"], cfg_path, DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    # exists → read
    try:
        raw = cfg_path.read_text(encoding="utf-8")
        if raw.strip() == "":
            raise ValueError("File is empty")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"{BR_RED}✗ pyshell_config.json is invalid JSON: {e}{R}")
        data: dict = {}
        warnings = [f"Invalid JSON: {e} (line {e.lineno}, col {e.colno})"]
        # treat as empty + invalid
        if interactive:
            return _prompt_config_fix(warnings, cfg_path, data)
        return dict(DEFAULT_CONFIG)
    except Exception as e:
        print(f"{BR_RED}✗ Cannot read config: {e}{R}")
        if interactive:
            return _prompt_config_fix([f"Cannot read config: {e}"], cfg_path, {})
        return dict(DEFAULT_CONFIG)

    warnings = validate_pyshell_config(data)
    if warnings and interactive:
        # filter out unknown-section info if that's the only warning? still show but less severe
        has_error = any(not w.startswith("Unknown section") for w in warnings)
        if has_error:
            return _prompt_config_fix(warnings, cfg_path, data)
        else:
            for w in warnings:
                print(f"{BR_BLACK}• {w}{R}")
    elif warnings:
        for w in warnings:
            print(f"{BR_YELLOW}⚠ {w}{R}")
    # merge defaults for any missing sections so runtime always has values
    merged = dict(DEFAULT_CONFIG)
    for k, v in data.items():
        merged[k] = v
    # ── sync manual edits: preset/theme changed but format/banner not updated ──
    # Prompt: if preset is a known preset (built-in or custom_formats), ensure format/git_branch match preset
    try:
        p = merged.get("prompt", {})
        preset_raw = p.get("preset", "")
        preset = str(preset_raw).lower() if isinstance(preset_raw, str) else ""
        fmt = p.get("format", "")
        # build all formats lookup from merged (built-in + custom)
        all_fmts = dict(FORMAT_PRESETS)
        cf = p.get("custom_formats", {})
        if isinstance(cf, dict):
            for k, v in cf.items():
                if isinstance(v, dict) and "format" in v:
                    all_fmts[k.lower()] = v
                elif isinstance(v, str):
                    all_fmts[k.lower()] = {"format": v, "git_branch": "{git}" in v}
        if preset in all_fmts:
            exp_fmt = all_fmts[preset]["format"]
            exp_git = all_fmts[preset].get("git_branch", "{git}" in exp_fmt)
            if fmt != exp_fmt or p.get("git_branch") != exp_git:
                p["format"] = exp_fmt
                p["git_branch"] = exp_git
                # persist corrected prompt back to file so manual edit sticks
                try:
                    data["prompt"]["format"] = exp_fmt
                    data["prompt"]["git_branch"] = exp_git
                    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                except Exception:
                    pass
        elif preset != "custom" and preset != "":
            # preset unknown but format matches a known preset -> sync preset
            for k, v in all_fmts.items():
                if v.get("format") == fmt:
                    p["preset"] = k
                    try:
                        data["prompt"]["preset"] = k
                        cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                    break
    except Exception:
        pass
    # Theme: if theme changed manually, sync banner_color to theme's banner (legacy field)
    try:
        app = merged.get("appearance", {})
        t_raw = app.get("theme", "dark")
        tname = str(t_raw).lower() if isinstance(t_raw, str) else "dark"
        all_th = dict(THEMES)
        ct = app.get("custom_themes", {})
        if isinstance(ct, dict):
            for k, v in ct.items():
                if isinstance(v, dict):
                    all_th[k.lower()] = v
        if tname in all_th:
            exp_banner = all_th[tname].get("banner", "cyan")
            if app.get("banner_color") != exp_banner:
                app["banner_color"] = exp_banner
                try:
                    if "appearance" in data and isinstance(data["appearance"], dict):
                        data["appearance"]["banner_color"] = exp_banner
                        cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                except Exception:
                    pass
    except Exception:
        pass
    return merged

# Global loaded config (initialized on startup)
PYSHELL_CONFIG: dict = dict(DEFAULT_CONFIG)

CMD_LIST = (
    "pyshell --version  # Shows current version",
    "pyshell quit       # Quits pyshell",
    "pyshell config     # Open pyshell config",
    "pyshell --refresh / -r / refresh # Reload config after manual edit (like source for pyshell_config.json)",
    "refresh / ref / reload # alias for pyshell --refresh",
    "pyshell theme [list|set <name>|preview] # Manage themes (dark, dracula, p10k, etc.)",
    "theme [list|set <name>|preview] # Manage themes — alias for pyshell theme",
    "p10k configure     # Powerlevel10k wizard — configure powerline prompt",
    "powerlevel10k configure # alias for p10k",
    "pyshell prompt [list|set <preset>|preview] # Prompt format presets (classic, pure, p10k…) ",
    "prompt [list|set <preset>|preview] # alias for pyshell prompt",
    "format [list|set <preset>|preview] # alias for prompt — presets: classic/pure/minimal/two-line/p10k",
    "pyshell format [list|set <preset>] # alias for prompt",
    "ls [path]          # List directory",
    "cd [path]          # Change directory (no args -> ~ on Linux, C:\\ on Windows; supports ~, -, /home/$USER)",
    "pwd                # Show current directory",
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
    "world / openworld [--map NAME] # CLI Open World — 6 maps unlock by LVL (plains0 desert1 islands2 forest3 mountain4 dungeon5), auto-save on Q",
    "world --list-maps  # list maps",
    "world --stats      # show saved stats",
    "world --new        # start fresh, ignore save",
    "world M/N/P/1-6    # in-game: M maps, N/P next/prev, 1-6 travel, WASD/arrows walk (right arrow fixed)",
    "cli-open-world     # alias for world",
    "ow                 # alias for world",
)
# Real .sh state
_last_exit_code: int = 0
_last_bg_pid: int | None = None
current_time = time.strftime("%H:%M:%S")
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
    # Logo — uses current theme banner color
    tc = _theme_colors()
    banner_c = tc.get("banner", BR_CYAN)
    print(banner_c + BOLD + r"   ___       __ _          _ _ " + R)
    print(banner_c + BOLD + r"  / _ \_   _/ _\ |__   ___| | |" + R)
    print(banner_c + BOLD + r" / /_)/ | | \ \| '_ \ / _ \ | |" + f"  {DIM}v{VERSION}{R}")
    print(banner_c + BOLD + r"/ ___/| |_| |\ \ | | |  __/ | |" + f"  {BR_BLACK}type 'help' for commands{R}")
    print(banner_c + BOLD + r"\/     \__, \__/_| |_|\___|_|_|" + R)
    print(banner_c + BOLD + r"       |___/ " + R)
    print(BR_BLACK + "─" * 50 + R)
    # show theme hint
    try:
        tname = _current_theme_name()
        if tname != "dark":
            print(f"{DIM}theme: {tname} ({THEMES[tname]['name']}) — try 'pyshell theme list'{R}")
    except Exception:
        pass

def cmd_version():
    print(f"{DIM}Loading PyShell version...{R}")
    time.sleep(1)
    print(f"PyShell Version: {BOLD}{VERSION}{R}")
    print(f"Python {sys.version.split()[0]} on {os.name} ({socket.gethostname()})")
    return VERSION

def cmd_ls(arg: str):
    if not arg.strip():
        target = Path.cwd()
    else:
        # Support flags like -a, -l, -la (ignore for now, just show all including hidden)
        try:
            tokens = _shell_split(arg.strip())
            filtered = [t for t in tokens if not t.startswith("-")]
            path_str = filtered[0] if filtered else ""
            target = expand_pyshell_path(path_str) if path_str else Path.cwd()
        except ValueError:
            path_str = arg.strip()
            target = expand_pyshell_path(path_str) if path_str and not path_str.startswith("-") else Path.cwd()
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
            tokens = _shell_split(raw)
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
        tokens = _shell_split(arg.strip())
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
    # Use Windows-aware split to preserve C:\ paths
    try:
        tokens = _shell_split(arg)
        # _shell_split on Windows with posix=True via doubling already preserves "" -> [''] ?
        # Ensure empty string "" is kept as '' token (shlex does); our helper does too for normal, but test
        if tokens == [] and '""' in arg:
            tokens = ['']
    except ValueError:
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
    OG echo — like GNU coreutils echo / bash builtin.
    Usage: echo [-neE] [--] [STRING...]
      -n  no trailing newline
      -e  enable backslash escapes
      -E  disable escapes (default)
      --  end of options
    Prints arguments as-is (quotes are stripped by the shell). Empty or no args -> blank line.
    Escapes (with -e): \a \b \c \e \f \n \r \t \v \\ \0NNN \xHH
    """
    raw_arg = arg.strip()
    if not raw_arg:
        # echo with no args -> blank line (GNU behavior, not PowerShell InputObject prompt)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return

    # Now we know there is at least one "" — extract quoted strings like OG shell does
    # Use Windows-aware split to respect quoting like the real shell
    try:
        tokens = _shell_split(arg)
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
        tokens = _shell_split(arg)
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
        tokens = _shell_split(arg.strip())
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
        tokens = _shell_split(arg)
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
        tokens = _shell_split(arg)
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
        tokens = _shell_split(arg.strip())
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
        tokens = _shell_split(arg)
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
        tokens = _shell_split(arg)
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
        tokens = _shell_split(arg.strip())
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

def cmd_world(arg: str = ""):
    """CLI Open World — open world CLI adventure (Builtin/cli-open-world.py)."""
    global _last_exit_code
    try:
        import importlib.util
        world_path = Path(__file__).parent / "Builtin" / "cli-open-world.py"
        if not world_path.exists():
            # fallback without hyphen? try cli_open_world.py
            alt = Path(__file__).parent / "Builtin" / "cli_open_world.py"
            if alt.exists():
                world_path = alt
            else:
                print(f"{BR_RED}world: missing {world_path}{R}")
                _last_exit_code = 1
                return
        spec = importlib.util.spec_from_file_location("Builtin.cli_open_world", world_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {world_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Handle args like rps: pass through to cli-open-world argparse
        orig_argv = sys.argv[:]
        try:
            if arg.strip():
                try:
                    parts = _shell_split(arg)
                except ValueError:
                    parts = arg.split()
                sys.argv = [str(world_path)] + parts
            else:
                sys.argv = [str(world_path)]
            # Call main — it handles --help/--stats/name internally
            mod.main()
            _last_exit_code = 0
        except SystemExit as e:
            # argparse --help exits with 0, game exit with 0
            code = e.code
            _last_exit_code = code if isinstance(code, int) else 0
        except (KeyboardInterrupt, EOFError):
            print(f"\n{BR_BLACK}world exited{R}")
            _last_exit_code = 0
        finally:
            sys.argv = orig_argv
    except Exception as e:
        print(f"{BR_RED}world: {e}{R}")
        _last_exit_code = 1

def cmd_help(_arg: str = ""):
    print(f"{BOLD}Available commands:{R}")
    for c in CMD_LIST:
        print(f"  {BR_CYAN}{c}{R}")
    print(f"{DIM}Config: pyshell_config.json in script dir. Run 'pyshell config' to open it.{R}")

def cmd_pyshell_config(_arg: str = ""):
    """Open pyshell_config.json, validate, and warn/prompt if missing/invalid/empty."""
    global PYSHELL_CONFIG
    cfg_path = get_config_path()
    # ensure file exists (create default if missing)
    if not cfg_path.exists():
        print(f"{BR_YELLOW}⚠ pyshell_config.json not found — creating default at {cfg_path}{R}")
        try:
            cfg_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
            print(f"{BR_GREEN}✓ Created {cfg_path}{R}")
        except Exception as e:
            print(f"{BR_RED}Cannot create config: {e}{R}")
            return
    print(f"{BOLD}Config file:{R} {cfg_path}")
    # try read + validate
    try:
        raw = cfg_path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(f"{BR_RED}✗ Invalid JSON: {e}{R}")
        print(f"{DIM}──────────────────────────────────────────────────{R}")
        PYSHELL_CONFIG = _prompt_config_fix([f"Invalid JSON: {e}"], cfg_path, {})
        return
    except Exception as e:
        print(f"{BR_RED}Cannot read config: {e}{R}")
        return

    warnings = validate_pyshell_config(data)
    if warnings:
        print(f"{BR_YELLOW}{BOLD}⚠ Configuration warnings:{R}")
        for w in warnings:
            # unknown section is info, others are warnings
            col = BR_BLACK if w.startswith("Unknown section") else BR_YELLOW
            print(f"  {col}• {w}{R}")
        has_error = any(not w.startswith("Unknown section") for w in warnings)
        if has_error:
            print(f"{DIM}──────────────────────────────────────────────────{R}")
            PYSHELL_CONFIG = _prompt_config_fix(warnings, cfg_path, data)
            return
    else:
        print(f"{BR_GREEN}✓ Config looks good — no warnings.{R}")

    try:
        print(f"{DIM}{'─' * 50}{R}")
        print(cfg_path.read_text(encoding="utf-8")[:3000])
        print(f"{DIM}{'─' * 50}{R}")
    except Exception as e:
        print(f"{BR_RED}cannot read: {e}{R}")

    # update global
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    PYSHELL_CONFIG = merged

    # try open with OS
    try:
        if os.name == "nt":
            os.startfile(str(cfg_path))  # type: ignore[attr-defined]
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(cfg_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("open"):
            subprocess.Popen(["open", str(cfg_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def cmd_refresh(_arg: str = ""):
    """Refresh/reload pyshell_config.json without restart — like `source` for config."""
    global PYSHELL_CONFIG
    cfg_path = get_config_path()
    print(f"{DIM}↻ Refreshing {cfg_path}...{R}")
    try:
        # reload with validation + sync (handles manual preset/theme edits)
        new_cfg = load_pyshell_config(interactive=False)
        PYSHELL_CONFIG = new_cfg
        tname = new_cfg.get("appearance", {}).get("theme", "dark")
        preset = new_cfg.get("prompt", {}).get("preset", "classic")
        fmt = new_cfg.get("prompt", {}).get("format", "")
        print(f"{BR_GREEN}✓ Config reloaded{R}  {DIM}theme:{R} {BR_CYAN}{tname}{R}  {DIM}preset:{R} {BR_CYAN}{preset}{R}  {DIM}format:{R} {repr(fmt)}{R}")
        # preview current theme/prompt
        try:
            tc = _theme_colors()
            th = _all_themes().get(tname, THEMES.get("dark"))
            if new_cfg.get("prompt", {}).get("format", "").strip() == "{p10k}" or "{p10k}" in fmt:
                print(_render_p10k_prompt(username, computer, Path.cwd().name, "(main)", _last_exit_code, tc, th).rstrip() + f" {DIM}# p10k{R}")
            else:
                git_str = "(main)" if new_cfg.get("prompt", {}).get("git_branch") else ""
                rep_user = f"{tc.get('user', BR_GREEN)}{username}{R}"
                rep_host = f"{tc.get('host', BR_CYAN)}{computer}{R}"
                rep_cwd = f"{tc.get('cwd', DIM)}~/cwd{R}"
                rep_git = f"{tc.get('git', BR_YELLOW)}{git_str}{R}" if git_str else ""
                rendered = fmt.replace("{user}", rep_user).replace("{host}", rep_host).replace("{cwd}", rep_cwd).replace("{git}", rep_git).replace("{p10k}", " p10k ")
                print(f"{DIM}prompt:{R} {rendered}{R}")
        except Exception:
            pass
        _last_exit_code = 0
    except Exception as e:
        print(f"{BR_RED}refresh failed: {e}{R}")
        _last_exit_code = 1

def cmd_theme(arg: str = ""):
    """Theme manager — list/set/preview themes for pyshell."""
    global PYSHELL_CONFIG
    arg = arg.strip()
    # parse subcommand
    try:
        parts = _shell_split(arg) if arg else []
    except Exception:
        parts = arg.split()
    sub = parts[0].lower() if parts else "list"
    if sub in ("list", "ls", ""):
        all_th = _all_themes()
        print(f"{BOLD}Available themes:{R} ({len(all_th)} presets — {len([k for k,v in all_th.items() if v.get('p10k')])} powerlevel10k, {len(all_th)-len(THEMES)} custom)")
        cur = _current_theme_name()
        for key, th in all_th.items():
            marker = f"{BR_GREEN}●{R}" if key == cur else " "
            tc = _theme_colors(key)
            # preview line: banner color sample + p10k powerline if applicable
            if th.get("p10k"):
                segs = th.get("segments", {})
                os_bg = _color(segs.get("os", {}).get("bg", "")) if segs.get("os", {}).get("bg") else ""
                dir_bg = _color(segs.get("dir", {}).get("bg", "")) if segs.get("dir", {}).get("bg") else ""
                p10k_sample = f"{os_bg}{tc['user']}  {R}{POWERLINE_RIGHT if th.get('style')!='lean' else ''}{dir_bg}{tc['cwd']}  ~/cwd {R}{POWERLINE_RIGHT if th.get('style')!='lean' else ''}"
                sample = p10k_sample
                p10k_tag = f"{BR_YELLOW}⚡p10k {th.get('style','')}{R}"
                if key not in THEMES:
                    p10k_tag += f" {BR_MAGENTA}(custom){R}"
            else:
                sample = f"{tc['banner']}{BOLD}██{R} {tc['user']}user{R}@{tc['host']}host{R} {tc['cwd']}~/cwd{R}"
                p10k_tag = f" {BR_MAGENTA}(custom){R}" if key not in THEMES else ""
            print(f" {marker} {BR_CYAN}{key:14}{R} {th['name']:18} {DIM}{th['description']}{R}{p10k_tag}")
            print(f"    {sample}  {DIM}banner:{th['banner']} user:{th['user']} host:{th['host']} cwd:{th['cwd']}{R}")
        print(f"\n{DIM}Current: {cur} — use 'theme set <name>' or 'pyshell theme set <name>'{R}")
        print(f"{DIM}Create your own: theme create <name> [base]  — copies base (default dark) to custom_themes{R}")
        print(f"{DIM}Custom: set 'appearance.custom_colors' or 'appearance.custom_themes.{{name}}' in pyshell_config.json{R}")
        print(f"{DIM}Powerlevel10k: p10k/p10k_lean/p10k_rainbow — run 'theme configure' for wizard{R}")
        print(f"{DIM}Valid colors: {', '.join(sorted(COLOR_MAP.keys()))}{R}")
        _last_exit_code = 0
        return
    elif sub in ("current", "show", "get"):
        cur = _current_theme_name()
        th = THEMES[cur]
        tc = _theme_colors(cur)
        print(f"{BOLD}Current theme: {BR_CYAN}{cur}{R} — {th['name']} — {th['description']}")
        print(f"  banner={th['banner']} user={th['user']} host={th['host']} cwd={th['cwd']} git={th['git']}")
        # show preview banner
        print(f"  Preview: {tc['banner']}{BOLD}   ___       __ _          _ _ {R}")
        _last_exit_code = 0
        return
    elif sub in ("preview", "test", "demo"):
        name = parts[1].lower() if len(parts) > 1 else _current_theme_name()
        if name not in _all_themes():
            print(f"{BR_RED}Unknown theme '{name}': available {', '.join(_all_themes().keys())}{R}")
            _last_exit_code = 1
            return
        tc = _theme_colors(name)
        th = _all_themes()[name]
        print(f"{BOLD}Preview: {name} — {th['name']}{R} {DIM}{th['description']}{R}")
        if name not in THEMES:
            print(f"{BR_MAGENTA}Custom theme — edit appearance.custom_themes.{name} in pyshell_config.json{R}")
        # full banner — fixed cut off (was 2 lines, now 5+ separator like print_banner)
        banner_c = tc['banner']
        print(banner_c + BOLD + r"   ___       __ _          _ _ " + R)
        print(banner_c + BOLD + r"  / _ \_   _/ _\ |__   ___| | |" + R)
        print(banner_c + BOLD + r" / /_)/ | | \ \| '_ \ / _ \ | |" + f"  {DIM}v{VERSION}{R}")
        print(banner_c + BOLD + r"/ ___/| |_| |\ \ | | |  __/ | |" + f"  {BR_BLACK}type 'help' for commands{R}")
        print(banner_c + BOLD + r"\/     \__, \__/_| |_|\___|_|_|" + R)
        print(banner_c + BOLD + r"       |___/ " + R)
        print(BR_BLACK + "─" * 50 + R)
        # sample prompt line separate from logo
        print(f"  {tc['user']}{username}{R}@{tc['host']}{computer}{R} {tc['cwd']}{Path.cwd().name}{R} $>  {DIM}# preview prompt{R}")
        print(f"{tc['user']}user{R} {tc['host']}host{R} {tc['cwd']}cwd{R} {tc['git']}git{R} {tc['error']}error{R} {tc['success']}success{R}")
        # p10k powerline preview
        if th.get("p10k"):
            print(f"\n{DIM}─ powerlevel10k prompt preview ─{R}")
            p10k_prompt = _render_p10k_prompt(username, computer, Path.cwd().name, "(main)", 0, tc, th)
            print(p10k_prompt.rstrip())
            p10k_err = _render_p10k_prompt(username, computer, Path.cwd().name, "(main ●)", 1, tc, th)
            print(p10k_err.rstrip() + f" {DIM}# with error + dirty{R}")
            if th.get("style") == "lean":
                print(f"{DIM}lean: no bg,  separators — fallback if Nerd Font missing, uses ❯{R}")
            else:
                print(f"{DIM}classic/rainbow: powerline  separators — requires Nerd Font, fallback is >{R}")
        _last_exit_code = 0
        return
    elif sub in ("set", "use", "switch"):
        if len(parts) < 2:
            print(f"{BR_YELLOW}Usage: theme set <name>  — available: {', '.join(_all_themes().keys())}{R}")
            _last_exit_code = 1
            return
        name = parts[1].lower()
        if name not in _all_themes():
            print(f"{BR_RED}Unknown theme '{name}': available {', '.join(_all_themes().keys())}{R}")
            _last_exit_code = 1
            return
        cfg_path = get_config_path()
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else dict(DEFAULT_CONFIG)
        except Exception:
            data = dict(DEFAULT_CONFIG)
        if "appearance" not in data or not isinstance(data["appearance"], dict):
            data["appearance"] = dict(DEFAULT_CONFIG["appearance"])
        data["appearance"]["theme"] = name
        data["appearance"]["banner_color"] = _all_themes()[name].get("banner", "cyan")
        try:
            cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            th = _all_themes()[name]
            print(f"{BR_GREEN}✓ Theme set to '{name}' — {th['name']}{R}")
            print(f"{DIM}Saved to {cfg_path} — restart or new prompt will use it. Preview above.{R}")
            PYSHELL_CONFIG["appearance"]["theme"] = name
            PYSHELL_CONFIG["appearance"]["banner_color"] = th.get("banner", "cyan")
            tc = _theme_colors(name)
            # full banner — fixed cut off (was 1 line)
            banner_c = tc['banner']
            print(banner_c + BOLD + r"   ___       __ _          _ _ " + R)
            print(banner_c + BOLD + r"  / _ \_   _/ _\ |__   ___| | |" + R)
            print(banner_c + BOLD + r" / /_)/ | | \ \| '_ \ / _ \ | |" + f"  {DIM}v{VERSION}{R}")
            print(banner_c + BOLD + r"/ ___/| |_| |\ \ | | |  __/ | |" + f"  {BR_BLACK}type 'help' for commands{R}")
            print(banner_c + BOLD + r"\/     \__, \__/_| |_|\___|_|_|" + R)
            print(banner_c + BOLD + r"       |___/ " + R)
            print(BR_BLACK + "─" * 50 + R)
            if th.get("p10k"):
                print(_render_p10k_prompt(username, computer, Path.cwd().name, "(main)", 0, tc, th).rstrip())
            else:
                # non-p10k sample prompt
                print(f"  {tc['user']}{username}{R}@{tc['host']}{computer}{R} {tc['cwd']}{Path.cwd().name}{R} $>")
        except Exception as e:
            print(f"{BR_RED}Cannot save theme: {e}{R}")
            _last_exit_code = 1
            return
        _last_exit_code = 0
        return
    elif sub in ("create", "new", "clone", "copy", "save"):
        # theme create <new_name> [base_theme] — create custom theme
        if len(parts) < 2:
            print(f"{BR_YELLOW}Usage: theme create <new_name> [base_theme]{R}")
            print(f"{DIM}Example: theme create mytheme dracula  — copies dracula to custom_themes.mytheme{R}")
            print(f"{DIM}Then edit pyshell_config.json appearance.custom_themes.mytheme or appearance.custom_colors{R}")
            _last_exit_code = 1
            return
        new_name = parts[1].lower()
        if not re.match(r'^[a-z0-9_-]+$', new_name):
            print(f"{BR_RED}Invalid name '{new_name}': use a-z, 0-9, -, _{R}")
            _last_exit_code = 1
            return
        if new_name in THEMES:
            print(f"{BR_RED}Cannot overwrite built-in theme '{new_name}'{R}")
            _last_exit_code = 1
            return
        base_name = parts[2].lower() if len(parts) > 2 else _current_theme_name()
        if base_name not in _all_themes():
            print(f"{BR_RED}Unknown base theme '{base_name}': available {', '.join(_all_themes().keys())}{R}")
            _last_exit_code = 1
            return
        base = _all_themes()[base_name]
        cfg_path = get_config_path()
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else dict(DEFAULT_CONFIG)
        except Exception:
            data = dict(DEFAULT_CONFIG)
        if "appearance" not in data or not isinstance(data["appearance"], dict):
            data["appearance"] = dict(DEFAULT_CONFIG["appearance"])
        if "custom_themes" not in data["appearance"] or not isinstance(data["appearance"]["custom_themes"], dict):
            data["appearance"]["custom_themes"] = {}
        # copy base (deep)
        import copy
        new_th = copy.deepcopy(base)
        new_th["name"] = new_name.capitalize()
        new_th["description"] = f"Custom — copied from {base_name}"
        data["appearance"]["custom_themes"][new_name] = new_th
        try:
            cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"{BR_GREEN}✓ Created custom theme '{new_name}' from '{base_name}'{R}")
            print(f"{DIM}Saved to {cfg_path} → appearance.custom_themes.{new_name}{R}")
            print(f"{DIM}Edit it: pyshell config  or  theme set {new_name} to activate{R}")
            # update in-memory
            if "custom_themes" not in PYSHELL_CONFIG["appearance"]:
                PYSHELL_CONFIG["appearance"]["custom_themes"] = {}
            PYSHELL_CONFIG["appearance"]["custom_themes"][new_name] = new_th
        except Exception as e:
            print(f"{BR_RED}Cannot save custom theme: {e}{R}")
            _last_exit_code = 1
            return
        _last_exit_code = 0
        return
    elif sub in ("delete", "remove", "rm", "del"):
        if len(parts) < 2:
            print(f"{BR_YELLOW}Usage: theme delete <custom_name>{R}")
            _last_exit_code = 1
            return
        name = parts[1].lower()
        if name in THEMES:
            print(f"{BR_RED}Cannot delete built-in theme '{name}'{R}")
            _last_exit_code = 1
            return
        cfg_path = get_config_path()
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
            ct = data.get("appearance", {}).get("custom_themes", {})
            if name not in ct:
                print(f"{BR_RED}Custom theme '{name}' not found{R}")
                _last_exit_code = 1
                return
            del ct[name]
            # if current theme was this, revert to dark
            if data.get("appearance", {}).get("theme") == name:
                data["appearance"]["theme"] = "dark"
                PYSHELL_CONFIG["appearance"]["theme"] = "dark"
            cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            if "custom_themes" in PYSHELL_CONFIG.get("appearance", {}):
                PYSHELL_CONFIG["appearance"]["custom_themes"].pop(name, None)
            print(f"{BR_GREEN}✓ Deleted custom theme '{name}'{R}")
        except Exception as e:
            print(f"{BR_RED}Cannot delete: {e}{R}")
            _last_exit_code = 1
            return
        _last_exit_code = 0
        return
    elif sub in ("configure", "wizard", "p10k", "powerlevel10k"):
        # p10k configure wizard — like `p10k configure`
        print(f"{BOLD}{BR_CYAN} Powerlevel10k wizard — configure your prompt{R}")
        print(f"{DIM}This will ask a few questions and set a p10k theme. Press Ctrl+C to abort.{R}")
        try:
            # 1. powerline?
            q1 = input(f"{BOLD}Does your terminal support Nerd Fonts / powerline  ? [Y/n]: {R}").strip().lower()
            has_powerline = q1 not in ("n", "no")
            # 2. style
            print(f"{DIM}Styles: classic (bg powerline), lean (no bg), rainbow (colorful){R}")
            q2 = input(f"{BOLD}Prompt style [classic/lean/rainbow] (classic): {R}").strip().lower()
            style = q2 if q2 in ("classic", "lean", "rainbow") else "classic"
            # 3. icons
            q3 = input(f"{BOLD}Enable Nerd Font icons (  ) ? [Y/n]: {R}").strip().lower()
            icons = q3 not in ("n", "no")
            # choose theme
            mapping = {"classic": "p10k", "lean": "p10k_lean", "rainbow": "p10k_rainbow"}
            chosen = mapping.get(style, "p10k")
            # if user wants no powerline but chose classic, fallback to lean
            if not has_powerline and style == "classic":
                print(f"{BR_YELLOW}No powerline → switching to lean (no ){R}")
                chosen = "p10k_lean"
            # optionally disable icons by switching to custom_colors override? For now icons are per-segment, we can keep but user can disable via config
            print(f"{DIM}Setting theme to {chosen}…{R}")
            # call set
            return cmd_theme(f"set {chosen}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Wizard cancelled{R}")
            _last_exit_code = 1
            return
    elif sub in ("help", "?", "h"):
        print(f"{BOLD}theme — manage pyshell themes{R}")
        print(f"  {BR_CYAN}theme list{R}              # list all presets (incl. custom & powerlevel10k)")
        print(f"  {BR_CYAN}theme set <name>{R}        # set theme (dark, light, dracula, ..., p10k*, or custom)")
        print(f"  {BR_CYAN}theme preview [name]{R}    # preview theme (p10k shows powerline prompt)")
        print(f"  {BR_CYAN}theme current{R}           # show current")
        print(f"  {BR_CYAN}theme create <name> [base]{R}  # create custom theme by copying base (default dark)")
        print(f"  {BR_CYAN}theme delete <name>{R}     # delete custom theme")
        print(f"  {BR_CYAN}theme configure{R}         # p10k wizard — like `p10k configure`")
        print(f"  {BR_CYAN}pyshell theme ...{R}       # same via pyshell prefix")
        print(f"{DIM}Custom: edit pyshell_config.json appearance.custom_themes.<name> or appearance.custom_colors{R}")
        print(f"{DIM}Example: theme create mytheme dracula  →  edit custom_themes.mytheme banner/user/host{R}")
        print(f"{DIM}Powerlevel10k: themes p10k*, prompt with , git ●⇡, ❯, icons  (needs Nerd Font){R}")
        _last_exit_code = 0
        return
    else:
        # treat arg as theme name directly: theme dracula => set
        if sub in _all_themes():
            # shortcut: theme <name> sets
            parts = ["set", sub]
            return cmd_theme(" ".join(parts))
        print(f"{BR_YELLOW}Unknown theme command '{sub}': try 'theme list' or 'theme help'{R}")
        _last_exit_code = 1
        return

def cmd_format(arg: str = ""):
    """Format/prompt presets — manage prompt.format like themes."""
    global PYSHELL_CONFIG
    arg = arg.strip()
    try:
        parts = _shell_split(arg) if arg else []
    except Exception:
        parts = arg.split()
    sub = parts[0].lower() if parts else "list"
    # allow `format set classic` or `prompt set classic` or `format classic` shortcut
    if sub in FORMAT_PRESETS and len(parts) == 1:
        # shortcut: format <preset> => set
        sub = "set"
        parts = ["set", arg.strip().lower()]

    if sub in ("list", "ls", ""):
        all_fmt = _all_formats()
        print(f"{BOLD}Available format presets:{R} ({len(all_fmt)} — {len(FORMAT_PRESETS)} built-in, {len(all_fmt)-len(FORMAT_PRESETS)} custom)")
        cur = _current_format_preset()
        cur_fmt = PYSHELL_CONFIG.get("prompt", {}).get("format", "")
        for key, fp in all_fmt.items():
            marker = f"{BR_GREEN}●{R}" if key == cur else " "
            preview = fp["format"].replace("{current_time}", _get_time_str("%H:%M:%S")).replace("{time}", _get_time_str("%H:%M:%S")).replace("{date}", _get_time_str("%Y-%m-%d")).replace("{user}", username).replace("{host}", computer).replace("{cwd}", "~/repo").replace("{git}", "(main)").replace("{p10k}", " p10k ")
            custom_tag = f" {BR_MAGENTA}(custom){R}" if key not in FORMAT_PRESETS else ""
            print(f" {marker} {BR_CYAN}{key:14}{R} {fp['name']:18} {DIM}{fp['description']}{R}{custom_tag}")
            print(f"    {BR_BLACK}format:{R} {repr(fp['format']):30} {DIM}→{R} {preview} {DIM}git_branch={fp['git_branch']}{R}")
        print(f"\n{DIM}Current: {cur} — {repr(cur_fmt)} — use 'format set <name>' or 'prompt set <name>'{R}")
        print(f"{DIM}Create: format create <name> \"<format>\"  — saves to prompt.custom_formats{R}")
        print(f"{DIM}Placeholders: {{user}} {{host}} {{cwd}} {{git}} {{p10k}} {{current_time}} {{time}} {{date}}  |  use 'format preview <name>'{R}")
        _last_exit_code = 0
        return
    elif sub in ("current", "show", "get"):
        cur = _current_format_preset()
        fmt = PYSHELL_CONFIG.get("prompt", {}).get("format", "")
        print(f"{BOLD}Current format preset: {BR_CYAN}{cur}{R}")
        print(f"  format={repr(fmt)}")
        print(f"  git_branch={PYSHELL_CONFIG.get('prompt', {}).get('git_branch')}")
        if cur != "custom":
            print(f"  → {FORMAT_PRESETS[cur]['description']}")
        _last_exit_code = 0
        return
    elif sub in ("preview", "test", "demo"):
        name = parts[1].lower() if len(parts) > 1 else _current_format_preset()
        if name not in _all_formats() and name != "custom":
            print(f"{BR_RED}Unknown format preset '{name}': available {', '.join(_all_formats().keys())}{R}")
            _last_exit_code = 1
            return
        if name == "custom":
            fmt = PYSHELL_CONFIG.get("prompt", {}).get("format", "")
            fp = {"name": "Custom", "description": "Current custom format", "format": fmt, "git_branch": PYSHELL_CONFIG.get("prompt", {}).get("git_branch", False)}
        else:
            fp = _all_formats()[name]
        print(f"{BOLD}Preview: {name} — {fp['name']}{R} {DIM}{fp['description']}{R}")
        print(f"  format={repr(fp['format'])}  git_branch={fp['git_branch']}")
        # render preview with theme colors
        tc = _theme_colors()
        # show full banner before preview — fixed logo cut off
        banner_c = tc.get("banner", BR_CYAN)
        print(banner_c + BOLD + r"   ___       __ _          _ _ " + R)
        print(banner_c + BOLD + r"  / _ \_   _/ _\ |__   ___| | |" + R)
        print(banner_c + BOLD + r" / /_)/ | | \ \| '_ \ / _ \ | |" + f"  {DIM}v{VERSION}{R}")
        print(banner_c + BOLD + r"/ ___/| |_| |\ \ | | |  __/ | |" + f"  {BR_BLACK}type 'help' for commands{R}")
        print(banner_c + BOLD + r"\/     \__, \__/_| |_|\___|_|_|" + R)
        print(banner_c + BOLD + r"       |___/ " + R)
        print(BR_BLACK + "─" * 50 + R)
        fmt = fp["format"]
        if "{p10k}" in fmt:
            # p10k preview — use p10k theme segments even if current theme is not p10k
            th = THEMES.get("p10k", THEMES["dark"])
            if _is_p10k_theme():
                th = THEMES.get(_current_theme_name(), th)
            p = _render_p10k_prompt(username, computer, "~/repo", "(main)", 0, tc, th)
            print(f"  {DIM}rendered (p10k):{R}")
            print(f"  {p.rstrip()}")
        else:
            # classic rendering
            git_str = "(main)" if fp["git_branch"] else ""
            rep_user = f"{tc.get('user', BR_GREEN)}{username}{R}"
            rep_host = f"{tc.get('host', BR_CYAN)}{computer}{R}"
            rep_cwd = f"{tc.get('cwd', DIM)}~/repo{R}"
            rep_git = f"{tc.get('git', BR_YELLOW)}{git_str}{R}" if git_str else ""
            rep_time = f"{DIM}{_get_time_str('%H:%M:%S')}{R}"
            rep_date = f"{DIM}{_get_time_str('%Y-%m-%d')}{R}"
            rendered = fmt.replace("{current_time}", rep_time).replace("{time}", rep_time).replace("{date}", rep_date).replace("{user}", rep_user).replace("{host}", rep_host).replace("{cwd}", rep_cwd).replace("{git}", rep_git).replace("{p10k}", f"{tc.get('user', BR_GREEN)} p10k {R}")
            print(f"  {DIM}rendered:{R}")
            print(f"  {rendered}{R}  {DIM}(sample){R}")
        _last_exit_code = 0
        return
    elif sub in ("set", "use", "switch"):
        if len(parts) < 2:
            print(f"{BR_YELLOW}Usage: format set <preset>  — available: {', '.join(FORMAT_PRESETS.keys())}{R}")
            print(f"{DIM}Or: format set \"{{user}}@{{host}} {{cwd}} $> \" for custom{R}")
            _last_exit_code = 1
            return
        # check if second arg is a preset or raw format with spaces
        # If parts[1] is a preset name, use it; else treat remainder as custom format
        cand = parts[1].lower()
        if cand in _all_formats():
            fp = _all_formats()[cand]
            new_fmt = fp["format"]
            new_git = fp["git_branch"]
            name = cand
        else:
            # custom format: extract raw after "set" preserving spaces
            try:
                lower = arg.lower()
                set_pos = lower.find("set")
                if set_pos != -1:
                    custom_fmt = arg[set_pos+3:].strip()
                    if len(custom_fmt) >= 2 and ((custom_fmt[0]=='"' and custom_fmt[-1]=='"') or (custom_fmt[0]=="'" and custom_fmt[-1]=="'")):
                        custom_fmt = custom_fmt[1:-1]
                    new_fmt = custom_fmt
                else:
                    new_fmt = " ".join(parts[1:])
            except Exception:
                new_fmt = " ".join(parts[1:])
            new_git = "{git}" in new_fmt
            name = "custom"
        cfg_path = get_config_path()
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else dict(DEFAULT_CONFIG)
        except Exception:
            data = dict(DEFAULT_CONFIG)
        if "prompt" not in data or not isinstance(data["prompt"], dict):
            data["prompt"] = dict(DEFAULT_CONFIG["prompt"])
        data["prompt"]["format"] = new_fmt
        data["prompt"]["preset"] = name
        data["prompt"]["git_branch"] = new_git
        try:
            cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            desc = _all_formats().get(name, {}).get("name", "Custom") if name != "custom" else "Custom"
            print(f"{BR_GREEN}✓ Format set to '{name}' — {desc}{R}")
            print(f"  format={repr(new_fmt)} preset={name} git_branch={new_git}")
            print(f"{DIM}Saved to {cfg_path}{R}")
            PYSHELL_CONFIG["prompt"]["format"] = new_fmt
            PYSHELL_CONFIG["prompt"]["preset"] = name
            PYSHELL_CONFIG["prompt"]["git_branch"] = new_git
            # preview
            tc = _theme_colors()
            git_str = "(main)" if new_git else ""
            if "{p10k}" in new_fmt:
                th = THEMES.get("p10k", THEMES["dark"])
                if _is_p10k_theme():
                    th = THEMES.get(_current_theme_name(), th)
                print(_render_p10k_prompt(username, computer, "~/repo", git_str or "(main)", 0, tc, th).rstrip())
            else:
                rep_user = f"{tc.get('user', BR_GREEN)}{username}{R}"
                rep_host = f"{tc.get('host', BR_CYAN)}{computer}{R}"
                rep_cwd = f"{tc.get('cwd', DIM)}~/repo{R}"
                rep_git = f"{tc.get('git', BR_YELLOW)}{git_str}{R}" if git_str else ""
                rep_time2 = f"{DIM}{_get_time_str('%H:%M:%S')}{R}"
                rep_date2 = f"{DIM}{_get_time_str('%Y-%m-%d')}{R}"
                rendered = new_fmt.replace("{current_time}", rep_time2).replace("{time}", rep_time2).replace("{date}", rep_date2).replace("{user}", rep_user).replace("{host}", rep_host).replace("{cwd}", rep_cwd).replace("{git}", rep_git).replace("{p10k}", " p10k ")
                print(f"  Preview: {rendered}{R}")
        except Exception as e:
            print(f"{BR_RED}Cannot save format: {e}{R}")
            _last_exit_code = 1
            return
        _last_exit_code = 0
        return
    elif sub in ("create", "new", "save", "add", "clone"):
        if len(parts) < 3:
            print(f"{BR_YELLOW}Usage: format create <new_name> \"<format>\"  e.g. format create myprompt \"{{user}}@{{host}} {{cwd}} ❯ \"{R}")
            print(f"{DIM}Then edit prompt.custom_formats.<name> in pyshell_config.json{R}")
            _last_exit_code = 1
            return
        new_name = parts[1].lower()
        if not re.match(r'^[a-z0-9_-]+$', new_name):
            print(f"{BR_RED}Invalid name '{new_name}': use a-z, 0-9, -, _{R}")
            _last_exit_code = 1
            return
        if new_name in FORMAT_PRESETS:
            print(f"{BR_RED}Cannot overwrite built-in preset '{new_name}'{R}")
            _last_exit_code = 1
            return
        # format is remainder after new_name — preserve inner trailing space
        try:
            lower = arg.lower()
            name_pos = lower.find(new_name)
            raw_rem = arg[name_pos+len(new_name):].strip()
            # strip outer quotes only, keep inner trailing space
            if len(raw_rem) >= 2 and ((raw_rem[0]=='"' and raw_rem[-1]=='"') or (raw_rem[0]=="'" and raw_rem[-1]=="'")):
                fmt_str = raw_rem[1:-1]
            else:
                fmt_str = raw_rem.strip('"').strip("'")
            if not fmt_str:
                fmt_str = " ".join(parts[2:])
                # parts[2:] already stripped outer quotes by _shell_split, keep as is (may have trailing space)
                # don't strip trailing space that is part of format
                if fmt_str.startswith('"') and fmt_str.endswith('"'):
                    fmt_str = fmt_str[1:-1]
        except Exception:
            fmt_str = " ".join(parts[2:])
            if len(fmt_str) >=2 and ((fmt_str[0]=='"' and fmt_str[-1]=='"') or (fmt_str[0]=="'" and fmt_str[-1]=="'")):
                fmt_str = fmt_str[1:-1]
        if not fmt_str:
            print(f"{BR_RED}Missing format string{R}")
            _last_exit_code = 1
            return
        cfg_path = get_config_path()
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else dict(DEFAULT_CONFIG)
        except Exception:
            data = dict(DEFAULT_CONFIG)
        if "prompt" not in data or not isinstance(data["prompt"], dict):
            data["prompt"] = dict(DEFAULT_CONFIG["prompt"])
        if "custom_formats" not in data["prompt"] or not isinstance(data["prompt"]["custom_formats"], dict):
            data["prompt"]["custom_formats"] = {}
        data["prompt"]["custom_formats"][new_name] = {"name": new_name.capitalize(), "description": f"Custom — {fmt_str}", "format": fmt_str, "git_branch": "{git}" in fmt_str}
        try:
            cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"{BR_GREEN}✓ Created custom format '{new_name}' → {repr(fmt_str)}{R}")
            print(f"{DIM}Saved to {cfg_path} → prompt.custom_formats.{new_name}{R}")
            print(f"{DIM}Use: format set {new_name}  or  prompt set {new_name}{R}")
            if "custom_formats" not in PYSHELL_CONFIG.get("prompt", {}):
                PYSHELL_CONFIG["prompt"]["custom_formats"] = {}
            PYSHELL_CONFIG["prompt"]["custom_formats"][new_name] = {"name": new_name.capitalize(), "description": f"Custom — {fmt_str}", "format": fmt_str, "git_branch": "{git}" in fmt_str}
        except Exception as e:
            print(f"{BR_RED}Cannot save: {e}{R}")
            _last_exit_code = 1
            return
        _last_exit_code = 0
        return
    elif sub in ("delete", "remove", "rm", "del"):
        if len(parts) < 2:
            print(f"{BR_YELLOW}Usage: format delete <custom_name>{R}")
            _last_exit_code = 1
            return
        name = parts[1].lower()
        if name in FORMAT_PRESETS:
            print(f"{BR_RED}Cannot delete built-in preset '{name}'{R}")
            _last_exit_code = 1
            return
        cfg_path = get_config_path()
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
            cf = data.get("prompt", {}).get("custom_formats", {})
            if name not in cf:
                print(f"{BR_RED}Custom format '{name}' not found{R}")
                _last_exit_code = 1
                return
            del cf[name]
            if data.get("prompt", {}).get("preset") == name:
                data["prompt"]["preset"] = "classic"
                data["prompt"]["format"] = FORMAT_PRESETS["classic"]["format"]
                PYSHELL_CONFIG["prompt"]["preset"] = "classic"
                PYSHELL_CONFIG["prompt"]["format"] = FORMAT_PRESETS["classic"]["format"]
            cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            PYSHELL_CONFIG.get("prompt", {}).get("custom_formats", {}).pop(name, None)
            print(f"{BR_GREEN}✓ Deleted custom format '{name}'{R}")
        except Exception as e:
            print(f"{BR_RED}Cannot delete: {e}{R}")
            _last_exit_code = 1
            return
        _last_exit_code = 0
        return
    elif sub in ("help", "?", "h"):
        print(f"{BOLD}format / prompt — manage prompt format presets{R}")
        print(f"  {BR_CYAN}format list{R}                 # list presets (incl. custom)")
        print(f"  {BR_CYAN}format set <name>{R}           # set preset (classic, pure, minimal, two-line, git, nerd, compact, full, p10k, powerline, or custom)")
        print(f"  {BR_CYAN}format preview [name]{R}       # preview")
        print(f"  {BR_CYAN}format create <name> \"<format>\"{R}  # create custom preset, e.g. format create myprompt \"{{user}}:{{cwd}} $> \"")
        print(f"  {BR_CYAN}format delete <name>{R}        # delete custom preset")
        print(f"  {BR_CYAN}format set \"{{user}}@{{host}} {{cwd}} $> \"{R}  # ad-hoc custom (preset=custom)")
        print(f"  {BR_CYAN}prompt ...{R}                  # alias for format")
        print(f"  {BR_CYAN}pyshell prompt ...{R}          # same via pyshell prefix")
        print(f"{DIM}Placeholders: {{user}} {{host}} {{cwd}} {{git}} {{p10k}}  — {{p10k}} triggers powerlevel10k rendering{R}")
        print(f"{DIM}Custom stored in prompt.custom_formats.<name> in pyshell_config.json{R}")
        _last_exit_code = 0
        return
    else:
        if sub in _all_formats():
            return cmd_format(f"set {sub}")
        print(f"{BR_YELLOW}Unknown format command '{sub}': try 'format list' or 'format help'{R}")
        _last_exit_code = 1
        return

def cmd_prompt(arg: str = ""):
    return cmd_format(arg)

# ---------------------------------------------------------------------------
# Real .sh engine — expansion, redirections, pipes, chaining
# ---------------------------------------------------------------------------

BUILTINS = {"ls","cd","pwd","pyfetch","time","clear","cls","cat","echo","cp","mv","mkdir","rm","rmdir","touch","grep","export","unset","env","source",".","history","whoami","hostname","help","rps","world","openworld","cli-open-world","ow","quit","exit","q","pyshell","theme","p10k","powerlevel10k","format","prompt","refresh","ref","reload"}

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

def _shell_split(s: str) -> list[str]:
    """Windows-aware shlex split: preserves Windows backslashes as path separators."""
    # On Windows, shlex posix=True treats \ as escape and mangles C:\path -> C:Path
    # Fix by doubling backslashes before split on Windows.
    if os.name == "nt":
        s_protected = s.replace("\\", "\\\\")
        try:
            return shlex.split(s_protected, posix=True)
        except ValueError:
            try:
                return shlex.split(s_protected, posix=False)
            except ValueError:
                return s.split()
    else:
        try:
            return shlex.split(s, posix=True)
        except ValueError:
            try:
                return shlex.split(s, posix=False)
            except ValueError:
                return s.split()

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
        parts = _shell_split(raw)
    except ValueError:
        try:
            parts = shlex.split(raw, posix=False)
        except ValueError:
            parts = raw.split()
    if not parts:
        _last_exit_code = 0
        return True
    cmd = parts[0].lower()
    # alias expansion from pyshell_config.json
    try:
        aliases = PYSHELL_CONFIG.get("aliases", {}) if isinstance(PYSHELL_CONFIG, dict) else {}
        if cmd in aliases and isinstance(aliases[cmd], str) and aliases[cmd].strip():
            alias_val = aliases[cmd].strip()
            rest = " ".join(shlex.quote(p) for p in parts[1:])
            raw = alias_val + (" " + rest if rest else "")
            # re-parse after alias
            try:
                parts = _shell_split(raw)
            except ValueError:
                try:
                    parts = shlex.split(raw, posix=False)
                except ValueError:
                    parts = raw.split()
            if parts:
                cmd = parts[0].lower()
                # also need to keep raw expanded for later split
                try:
                    _, arg = raw.split(None, 1)
                    arg = arg.strip()
                except ValueError:
                    arg = ""
                # store expanded raw for later use — update raw to alias-expanded
                raw = raw
                # need to handle arg variable already set later? We'll let later code re-split arg
                # To avoid double split, set a flag; simpler: let later code re-derive arg from raw
                # So we update raw and continue — later `_, arg = raw.split(None,1)` will be re-done
                pass
    except Exception:
        pass
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
        elif sub in ("theme", "themes"):
            t_arg = " ".join(parts[2:]) if len(parts) > 2 else ""
            cmd_theme(t_arg)
        elif sub in ("p10k", "powerlevel10k"):
            t_arg = " ".join(parts[2:]) if len(parts) > 2 else "configure"
            # p10k configure is the wizard
            if not t_arg:
                t_arg = "configure"
            cmd_theme(t_arg)
        elif sub in ("prompt", "format", "formats"):
            t_arg = " ".join(parts[2:]) if len(parts) > 2 else ""
            # pyshell prompt == prompt, pyshell format == format
            if sub in ("format", "formats"):
                cmd_format(t_arg)
            else:
                cmd_format(t_arg)
        elif sub in ("refresh", "--refresh", "-r", "reload", "ref"):
            cmd_refresh(" ".join(parts[2:]) if len(parts) > 2 else "")
        else:
            print(f"{BR_YELLOW}usage: pyshell --version | pyshell quit | pyshell config | pyshell theme [list|set <name>|preview] | pyshell prompt [list|set] | pyshell p10k configure | pyshell --refresh/-r{R}")
            _last_exit_code = 1
        return True

    # refresh aliases (like `source` for config) — reload without restart
    if cmd in ("refresh", "ref", "reload"):
        cmd_refresh(arg)
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
        print("Unknown command: pyfetch")
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
    elif cmd == "theme":
        cmd_theme(arg)
    elif cmd in ("p10k", "powerlevel10k"):
        # p10k configure wizard — like `p10k configure`
        if not arg.strip():
            cmd_theme("configure")
        elif arg.strip().lower() in ("configure", "wizard"):
            cmd_theme("configure")
        else:
            cmd_theme(arg)
    elif cmd in ("prompt", "format", "formats"):
        cmd_format(arg)
    elif cmd in ("help", "?", "h"):
        cmd_help(arg)
        _last_exit_code = 0
    elif cmd == "rps":
        try:
            # Robust import: works when run as `python pyshell.py` (no parent package)
            # and when run as module. Also avoids executing top-level loop in
            # RockPaperScissors.py by ensuring that file is guarded with
            # `if __name__ == "__main__":`.
            RockPaperScissors = None
            try:
                from Builtin import RockPaperScissors as _rps_mod
                RockPaperScissors = _rps_mod
            except ImportError:
                try:
                    from .Builtin import RockPaperScissors as _rps_mod  # type: ignore
                    RockPaperScissors = _rps_mod
                except ImportError:
                    # Fallback: load directly from file next to pyshell.py
                    import importlib.util

                    rps_path = Path(__file__).parent / "Builtin" / "RockPaperScissors.py"
                    spec = importlib.util.spec_from_file_location(
                        "Builtin.RockPaperScissors", rps_path
                    )
                    if spec is None or spec.loader is None:
                        raise ImportError(f"cannot load {rps_path}")
                    _mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(_mod)
                    RockPaperScissors = _mod
            # Infinite play until player exits (quit/exit/q or Ctrl+C/EOF)
            print(f"{DIM}RPS started — type rock/paper/scissors, 'quit' to exit{R}")
            while True:
                try:
                    RockPaperScissors.rock_paper_scissors()
                except SystemExit:
                    # quit/exit command
                    break
                except (KeyboardInterrupt, EOFError):
                    print(f"\n{DIM}RPS exited{R}")
                    break
            _last_exit_code = 0
        except Exception as e:
            print(f"{BR_RED}rps: {e}{R}")
            _last_exit_code = 1
    elif cmd in ("world", "openworld", "cli-open-world", "ow"):
        cmd_world(arg)
        _last_exit_code = 0
    else:
        # external command — support pipe stdin_data via input, and capture when piped/redirected (bugfix: fortune | cowsay)
        try:
            # Detect if stdout/stderr are being captured (pipe/redirection via _run_single_with_redirects)
            is_captured = isinstance(sys.stdout, io.StringIO) or isinstance(sys.stderr, io.StringIO)
            need_capture = is_captured or (stdin_data is not None)
            if need_capture:
                # capture_output so output can be piped or redirected via StringIO
                result = subprocess.run(raw, shell=True, input=stdin_data, text=True, capture_output=True, errors="replace")
                if result.stdout:
                    sys.stdout.write(result.stdout)
                if result.stderr:
                    sys.stderr.write(result.stderr)
                _last_exit_code = result.returncode if result.returncode is not None else 0
            else:
                if stdin_data is not None:
                    result = subprocess.run(raw, shell=True, input=stdin_data, text=True)
                else:
                    result = subprocess.run(raw, shell=True)
                _last_exit_code = result.returncode if result.returncode is not None else 0
            if _last_exit_code is None:
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
    global PYSHELL_CONFIG, HISTORY_FILE
    # On Linux, ensure /home/$USER/.pyshell exists and copy docs/config there
    _ensure_linux_pyshell_dir()
    # --- load & validate pyshell_config.json (warns if missing/invalid/empty) ---
    # For --version/--help we still validate but don't block on prompt if non-interactive
    PYSHELL_CONFIG = load_pyshell_config(interactive=True)
    # Apply history file from config
    try:
        hist_file = PYSHELL_CONFIG.get("history", {}).get("file", str(HISTORY_FILE))
        # expand ~ and env
        hist_file = os.path.expandvars(os.path.expanduser(hist_file))
        HISTORY_FILE = Path(hist_file)
        # ensure parent exists
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        # apply max_lines to readline if present
        max_lines = PYSHELL_CONFIG.get("history", {}).get("max_lines", 500)
        try:
            import readline  # type: ignore
            readline.set_history_length(int(max_lines))
        except Exception:
            pass
    except Exception:
        pass

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

    # Handle Open in terminal (right-click) — respect directory where user clicked
    # Linux/macOS/Windows: terminal launches shell with cwd = clicked folder, or passes folder as arg
    try:
        if len(sys.argv) > 1:
            # check if first arg is a directory (Open in terminal may pass folder path)
            cand = sys.argv[1]
            # ignore known flags and script files already handled above
            if cand not in ("--version", "-v", "version", "--help", "-h", "help", "-c", "--command") and not cand.endswith((".sh", ".bash")):
                p = expand_pyshell_path(cand) if isinstance(cand, str) and cand.startswith("~") else Path(cand)
                # also try raw path
                if not p.exists():
                    p = Path(cand)
                if p.exists() and p.is_dir():
                    os.chdir(p)
                    # handled — don't also treat as home
                elif p.exists() and p.is_file():
                    # if it's a file, cd to its parent (common for right-click on file's folder)
                    try:
                        os.chdir(p.parent)
                    except Exception:
                        pass
    except Exception:
        pass
    # Start in OS-specific home only if not already in a user directory (respect Open in terminal)
    try:
        home = get_pyshell_home()
        cwd = Path.cwd()
        script_dir = Path(__file__).parent.resolve()
        try:
            cwd_res = cwd.resolve()
        except Exception:
            cwd_res = cwd
        try:
            home_res = home.resolve()
        except Exception:
            home_res = home
        # keep cwd if it was set by Open in terminal (right-click) — not home, not script dir, valid dir
        keep_cwd = False
        try:
            if cwd.exists() and cwd.is_dir() and cwd_res != home_res and cwd_res != script_dir:
                # on Linux/macOS, also not root; on Windows, not System32
                if os.name == "nt":
                    # Windows: keep if not home (C:\) and not System32
                    keep_cwd = True
                    # but if cwd is Windows System32 (login shell edge), don't keep
                    try:
                        if "system32" in str(cwd_res).lower():
                            keep_cwd = False
                    except Exception:
                        pass
                else:
                    keep_cwd = cwd_res != Path("/").resolve() and cwd != Path.home()
                # if keep_cwd, don't chdir to home
            else:
                keep_cwd = False
        except Exception:
            keep_cwd = False
        if not keep_cwd and home.exists():
            os.chdir(home)
    except Exception:
        try:
            home = get_pyshell_home()
            if home.exists():
                os.chdir(home)
        except Exception:
            pass
    # behavior: clear_on_start
    try:
        if PYSHELL_CONFIG.get("behavior", {}).get("clear_on_start"):
            clear_screen()
    except Exception:
        pass
    # appearance: banner
    try:
        if PYSHELL_CONFIG.get("appearance", {}).get("banner", True):
            print_banner()
        else:
            print(f"{DIM}PyShell {VERSION} — type 'help' for commands{R}")
    except Exception:
        print_banner()
    # startup commands from config
    try:
        for cmd in PYSHELL_CONFIG.get("startup", {}).get("commands", []):
            if isinstance(cmd, str) and cmd.strip():
                print(f"{DIM}▶ startup: {cmd}{R}")
                dispatch(cmd)
    except Exception as e:
        print(f"{BR_YELLOW}startup commands error: {e}{R}")
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
        cmds = ["ls", "cd", "pwd", "pyfetch", "time", "clear", "cls", "cat", "echo", "cp", "mv", "mkdir", "rm", "rmdir", "touch", "grep", "export", "unset", "env", "source", ".", "history", "whoami", "hostname", "help", "rps", "world", "openworld", "cli-open-world", "ow", "quit", "exit", "pyshell"]
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
            # Shorten very long cwd to avoid prompt glitch (input overwriting when prompt too long)
            try:
                if len(cwd_display) > 35:
                    norm = cwd_display.replace("\\", "/")
                    parts = [p for p in norm.split("/") if p]
                    if len(parts) > 2:
                        if cwd_display.startswith("C:"):
                            cwd_display = "C:.../" + "/".join(parts[-2:])
                        elif cwd_display.startswith("~"):
                            cwd_display = "~/.../" + "/".join(parts[-2:])
                        else:
                            cwd_display = ".../" + "/".join(parts[-2:])
                    elif len(cwd_display) > 40:
                        cwd_display = "..." + cwd_display[-32:]
            except Exception:
                pass
            # prompt from config — fixed glitch where input overwrote prompt (readline ANSI miscount + replace bug)
            try:
                p_cfg = PYSHELL_CONFIG.get("prompt", {})
                fmt = p_cfg.get("format", "{user}@{host} {cwd} $> ")
                use_color = p_cfg.get("color", True)
                # handle time:true flag — auto-inject current_time if placeholder not present
                if p_cfg.get("time", False) and "{current_time}" not in fmt and "{time}" not in fmt and "{date}" not in fmt:
                    fmt = "{current_time} " + fmt
                # git branch string
                git_str = ""
                if p_cfg.get("git_branch"):
                    try:
                        br = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
                        if br:
                            git_str = f"({br})"
                    except Exception:
                        git_str = ""
                # Build prompt — p10k powerline if format contains {p10k}, else classic
                # Fix: previously checked only theme, so `format set pure` while on p10k theme didn't change prompt
                if use_color and "{p10k}" in fmt:
                    tc = _theme_colors()
                    th = THEMES.get(_current_theme_name(), THEMES["dark"])
                    # if theme is not p10k but format is {p10k}, still render p10k with current theme's colors
                    # ensure p10k theme fallback has segments
                    if not th.get("p10k"):
                        th = THEMES.get("p10k", th)
                    prompt = _render_p10k_prompt(username, computer, cwd_display, git_str, _last_exit_code, tc, th)
                elif use_color:
                    tc = _theme_colors()
                    rep_user = f"{tc.get('user', BR_GREEN)}{username}{R}"
                    rep_host = f"{tc.get('host', BR_CYAN)}{computer}{R}"
                    rep_cwd = f"{tc.get('cwd', DIM)}{cwd_display}{R}"
                    rep_git = f"{tc.get('git', BR_YELLOW)}{git_str}{R}" if git_str else ""
                    _now = _get_time_str("%H:%M:%S")
                    rep_time = f"{DIM}{_now}{R}"
                    prompt = fmt.replace("{current_time}", rep_time).replace("{time}", rep_time).replace("{date}", f"{DIM}{_get_time_str('%Y-%m-%d')}{R}").replace("{user}", rep_user).replace("{host}", rep_host).replace("{cwd}", rep_cwd).replace("{git}", rep_git)
                    if not prompt.endswith(R):
                        prompt = prompt + R + " "
                    else:
                        prompt = prompt + " "
                else:
                    _now_plain = _get_time_str("%H:%M:%S")
                    prompt = fmt.replace("{current_time}", _now_plain).replace("{time}", _now_plain).replace("{date}", _get_time_str("%Y-%m-%d")).replace("{user}", username).replace("{host}", computer).replace("{cwd}", cwd_display).replace("{git}", git_str)
                    prompt = prompt + (" " if not prompt.endswith(" ") else "")
                # Wrap ANSI sequences with \x01\x02 so readline doesn't count them toward prompt length
                # Without this, input() with readline overwrites prompt when typing (glitchy)
                try:
                    import readline  # type: ignore
                    # Only wrap if readline is actually active (isatty)
                    if sys.stdin.isatty():
                        prompt = re.sub(r'\x1b\[[0-9;]*m', lambda m: '\x01' + m.group(0) + '\x02', prompt)
                except Exception:
                    pass
            except Exception:
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
            should_quit = not dispatch(line)
            if should_quit:
                if PYSHELL_CONFIG.get("behavior", {}).get("confirm_exit"):
                    try:
                        ans = input(f"{BR_YELLOW}Really exit? [y/N]: {R}").strip().lower()
                        if ans not in ("y", "yes"):
                            print(f"{DIM}exit cancelled{R}")
                            continue
                    except (EOFError, KeyboardInterrupt):
                        print()
                        continue
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
    time.sleep(1)

if __name__ == "__main__":
    main()
