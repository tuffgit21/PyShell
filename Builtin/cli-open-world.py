import argparse
import base64
import hashlib
import json
import os
import random
import shutil
import sys
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import termios
    import tty

NAME = "John doe"
CLEAR = "cls" if os.name == "nt" else "clear"
SAVE_FILE = Path(__file__).parent / "world_save.dat"
_LEGACY_SAVE = Path(__file__).parent / "world_save.json"
_SAVE_KEY = b"PyShellWorld2026!Key#42"
_SAVE_MAGIC = "PYSHELLWORLD:"

# --- Maps: more worlds ---
MAPS = {
    "plains":   {"w": 8,  "h": 6,  "treasures": 6,  "monsters": 8,  "desc": "Plains — balanced 8×6"},
    "desert":   {"w": 12, "h": 7,  "treasures": 8,  "monsters": 12, "desc": "Desert — vast 12×7, scorching"},
    "forest":   {"w": 10, "h": 10, "treasures": 10, "monsters": 10, "desc": "Forest — dense 10×10"},
    "dungeon":  {"w": 6,  "h": 6,  "treasures": 4,  "monsters": 14, "desc": "Dungeon — 6×6 monster-heavy"},
    "islands":  {"w": 14, "h": 6,  "treasures": 7,  "monsters": 9,  "desc": "Islands — scattered 14×6"},
    "mountain": {"w": 9,  "h": 8,  "treasures": 5,  "monsters": 11, "desc": "Mountain — 9×8, tricky terrain"},
}
DEFAULT_MAP = "plains"
# legacy globals for backward compat (used as default)
WORLD_W = MAPS[DEFAULT_MAP]["w"]
WORLD_H = MAPS[DEFAULT_MAP]["h"]

# --- Unlock system: maps unlock as you level up ---
UNLOCK_AT = {"plains": 0, "desert": 1, "islands": 2, "forest": 3, "mountain": 4, "dungeon": 5}
def get_unlocked(lvl: int):
    return [k for k, req in sorted(UNLOCK_AT.items(), key=lambda x: x[1]) if lvl >= req]
def next_unlocked(current: str, lvl: int, direction: int = 1):
    unlocked = get_unlocked(lvl)
    if current not in unlocked:
        return unlocked[0] if unlocked else current
    idx = unlocked.index(current)
    return unlocked[(idx + direction) % len(unlocked)]


def get_key():
    if not sys.stdin.isatty():
        return (input().strip().lower() or " ")[0]

    if os.name == "nt":
        ch = msvcrt.getwch().lower()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch().lower()
            # arrows: H=up, P=down, K=left, M=right (was buggy M->g)
            return {"h": "w", "p": "s", "k": "a", "m": "d"}.get(ch2, ch2)
        return ch

    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
        tty.setraw(fd)
        try:
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        return (input().strip().lower() or " ")[0]

    if ch == "\x1b":
        seq = sys.stdin.read(2)
        return {
            "[A": "w", "[B": "s", "[C": "d", "[D": "a",
            "OA": "w", "OB": "s", "OC": "d", "OD": "a",
        }.get(seq, " ")
    return ch.lower()


def term_size():
    size = shutil.get_terminal_size((80, 24))
    return size.columns, size.lines


def hbar(width, left="+", mid="-", right="+"):
    return left + mid * (width - 2) + right


def bar(label, value, maximum, width):
    inner = max(0, width - len(label) - 4)
    maximum = max(1, maximum)
    filled = int(max(0, min(1, value / maximum)) * inner)
    return f"{label} [{'#' * filled}{'-' * (inner - filled)}]"


def cline(text, cols):
    content = (cols - 2)
    return "|" + text.ljust(content)[:content] + "|"


class PlayerStat:
    def __init__(self):
        self.health = 100
        self.max_health = 100
        self.attack = 15
        self.lvl = 0
        self.xp = 0
        self.x = 0
        self.y = 0

    def gain_xp(self, amount):
        old_lvl = self.lvl
        self.xp += amount
        unlocked_now = []
        while self.xp >= (self.lvl + 1) * 100:
            self.lvl += 1
            self.attack += 10
            self.max_health += 20
            self.health = self.max_health
            # check unlocks
            for k, req in UNLOCK_AT.items():
                if req == self.lvl and req != 0:
                    unlocked_now.append(k)
        return unlocked_now

    def show(self, cols):
        print(bar(" HP", self.health, self.max_health, cols))
        print(f"ATK {self.attack} | LVL {self.lvl} | XP {self.xp}")

    def to_dict(self):
        return {"health": self.health, "max_health": self.max_health, "attack": self.attack, "lvl": self.lvl, "xp": self.xp, "x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.health = int(d.get("health", 100))
        p.max_health = int(d.get("max_health", 100))
        p.attack = int(d.get("attack", 15))
        p.lvl = int(d.get("lvl", 0))
        p.xp = int(d.get("xp", 0))
        p.x = int(d.get("x", 0))
        p.y = int(d.get("y", 0))
        return p


class Monster:
    def __init__(self, health, attack, xp, name):
        self.health = health
        self.attack = attack
        self.xp = xp
        self.name = name


MONSTERS = [
    ("Goblin", 60, 8, 20),
    ("Wolf", 80, 12, 30),
    ("Orc", 120, 18, 50),
    ("Wraith", 100, 22, 70),
]


def roll_monster():
    name, h, a, x = random.choice(MONSTERS)
    return Monster(h, a, x, name)


class World:
    def __init__(self, map_name=DEFAULT_MAP):
        cfg = MAPS.get(map_name, MAPS[DEFAULT_MAP])
        self.map_name = map_name if map_name in MAPS else DEFAULT_MAP
        self.w = cfg["w"]
        self.h = cfg["h"]
        self.treasures = cfg["treasures"]
        self.monsters = cfg["monsters"]
        self.tiles = {}
        for y in range(self.h):
            for x in range(self.w):
                self.tiles[(x, y)] = {
                    "type": "empty",
                    "seen": False,
                    "cleared": False,
                }
        self.tiles[(0, 0)]["type"] = "town"
        self.tiles[(self.w - 1, self.h - 1)]["type"] = "town"
        for _ in range(self.treasures):
            x, y = random.randrange(self.w), random.randrange(self.h)
            if self.tiles[(x, y)]["type"] == "empty":
                self.tiles[(x, y)]["type"] = "treasure"
        for _ in range(self.monsters):
            x, y = random.randrange(self.w), random.randrange(self.h)
            if self.tiles[(x, y)]["type"] == "empty":
                self.tiles[(x, y)]["type"] = "monster"

    def symbol(self, x, y, player):
        t = self.tiles[(x, y)]
        if player.x == x and player.y == y:
            return "@"
        if not t["seen"]:
            return "?"
        if t["type"] == "town":
            return "T"
        if t["type"] == "treasure" and not t["cleared"]:
            return "$"
        if t["type"] == "monster" and not t["cleared"]:
            return "M"
        return "."

    def to_dict(self):
        # tiles keys as "x,y"
        tiles_d = {f"{x},{y}": v for (x, y), v in self.tiles.items()}
        return {"map_name": self.map_name, "w": self.w, "h": self.h, "tiles": tiles_d}

    @classmethod
    def from_dict(cls, d):
        map_name = d.get("map_name", DEFAULT_MAP)
        w = World(map_name)
        # override tiles if saved
        tiles_d = d.get("tiles")
        if isinstance(tiles_d, dict):
            restored = {}
            for k, v in tiles_d.items():
                try:
                    x_s, y_s = k.split(",")
                    restored[(int(x_s), int(y_s))] = v
                except Exception:
                    continue
            # keep dimensions from saved w/h if present
            w.w = int(d.get("w", w.w))
            w.h = int(d.get("h", w.h))
            w.tiles = restored
        return w


def get_save_path():
    return SAVE_FILE


def _hide_file(path: Path):
    try:
        if os.name == "nt":
            import ctypes
            # FILE_ATTRIBUTE_HIDDEN=0x2 | SYSTEM=0x4
            try:
                ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02 | 0x04)
            except Exception:
                try:
                    os.system(f'attrib +h +s "{path}" >nul 2>&1')
                except Exception:
                    pass
        else:
            # 0o600 owner only
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
    except Exception:
        pass


def _encode_save(plain: str) -> str:
    data = plain.encode("utf-8")
    ch = hashlib.sha256(data).hexdigest()[:16]
    key = _SAVE_KEY
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    b64 = base64.b64encode(xored).decode("ascii")
    # reverse + magic for obfuscation
    return _SAVE_MAGIC + ch + ":" + b64[::-1]


def _decode_save(encoded: str) -> str:
    if not encoded.startswith(_SAVE_MAGIC):
        raise ValueError("invalid save header")
    body = encoded[len(_SAVE_MAGIC):]
    if ":" not in body:
        raise ValueError("corrupt save")
    ch, b64_rev = body.split(":", 1)
    b64 = b64_rev[::-1]
    xored = base64.b64decode(b64.encode("ascii"))
    key = _SAVE_KEY
    data = bytes(b ^ key[i % len(key)] for i, b in enumerate(xored))
    if hashlib.sha256(data).hexdigest()[:16] != ch:
        raise ValueError("save tampered — checksum mismatch")
    return data.decode("utf-8")


def _migrate_legacy():
    try:
        if _LEGACY_SAVE.exists() and not SAVE_FILE.exists():
            # remove old plain json save — force new encoded format only game can create
            try:
                _LEGACY_SAVE.unlink()
            except Exception:
                pass
        elif _LEGACY_SAVE.exists():
            try:
                _LEGACY_SAVE.unlink()
            except Exception:
                pass
    except Exception:
        pass


def save_game(player, world):
    try:
        _migrate_legacy()
        data = {"player": player.to_dict(), "world": world.to_dict(), "map_name": world.map_name}
        plain = json.dumps(data, separators=(",", ":"))
        encoded = _encode_save(plain)
        p = get_save_path()
        # temporarily clear hidden to allow write
        try:
            if p.exists() and os.name == "nt":
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
        except Exception:
            pass
        p.write_text(encoded, encoding="utf-8")
        _hide_file(p)
        return True
    except Exception as e:
        print(f"save failed: {e}")
        return False


def load_game(map_name=None):
    try:
        _migrate_legacy()
        p = get_save_path()
        if not p.exists():
            return None, None
        raw = p.read_text(encoding="utf-8").strip()
        if not raw:
            return None, None
        # only game-encoded saves are valid — plain JSON is rejected as tampered
        if not raw.startswith(_SAVE_MAGIC):
            # legacy/tampered — delete to enforce game-only access
            try:
                p.unlink()
            except Exception:
                pass
            return None, None
        plain = _decode_save(raw)
        data = json.loads(plain)
        # if map requested differs from save, don't load save unless --map not specified?
        saved_map = data.get("map_name", DEFAULT_MAP)
        if map_name and map_name != saved_map:
            # map switch requested → ignore save, start fresh on new map
            return None, None
        player = PlayerStat.from_dict(data.get("player", {}))
        world = World.from_dict(data.get("world", {}))
        # clamp player inside world bounds
        player.x = max(0, min(player.x, world.w - 1))
        player.y = max(0, min(player.y, world.h - 1))
        return player, world
    except Exception:
        # tampered/corrupt — delete to prevent manual editing
        try:
            p = get_save_path()
            if p.exists():
                if os.name == "nt":
                    try:
                        import ctypes
                        ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
                    except Exception:
                        pass
                p.unlink()
        except Exception:
            pass
        return None, None


def delete_save():
    try:
        _migrate_legacy()
        p = get_save_path()
        ok = False
        if p.exists():
            try:
                if os.name == "nt":
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
            except Exception:
                pass
            p.unlink()
            ok = True
        # also ensure legacy is gone
        if _LEGACY_SAVE.exists():
            try:
                _LEGACY_SAVE.unlink()
                ok = True
            except Exception:
                pass
        return ok
    except Exception:
        pass
    return False


def render(world, player, cols, lines, msg=""):
    cols = max(20, cols)
    os.system(CLEAR)
    content = cols - 2
    out = []
    out.append(hbar(cols))
    title = f" CLI OPEN WORLD [{world.map_name}] "
    out.append("|" + title.center(content)[:content] + "|")
    out.append(hbar(cols, "+", "=", "+"))
    cw = 3 if world.w * 3 + 3 <= cols else 1
    for y in range(world.h):
        row = ""
        for x in range(world.w):
            sym = world.symbol(x, y, player)
            row += f"[{sym}]" if cw == 3 else sym
        row = row[:content - 1]
        out.append("| " + row.ljust(content - 1) + "|")
    out.append(hbar(cols, "+", "=", "+"))
    out.append(cline(bar(" HP", player.health, player.max_health, content), cols))
    out.append(cline(f" ATK {player.attack}  LVL {player.lvl}  XP {player.xp}", cols))
    out.append(hbar(cols))
    if msg:
        for line in (msg.splitlines() or [""]):
            out.append(cline(line, cols))
    out.append(hbar(cols))
    print("\n".join(out))


def combat(player, monster, world, cols, lines):
    msg = f"A {monster.name} appears! (f=attack g=dodge r=run)"
    while monster.health > 0:
        render(world, player, cols, lines, msg)
        msg = ""
        cmd = get_key()
        if cmd == "f":
            monster.health -= player.attack
            msg = f"You hit {monster.name} for {player.attack}!"
            if monster.health <= 0:
                msg = f"You defeated {monster.name}! +{monster.xp} xp."
                newly = player.gain_xp(monster.xp)
                if newly:
                    msg += f" Unlocked: {', '.join(newly)}! Press M for maps."
        elif cmd == "g":
            msg = "You dodged!"
        elif cmd == "r":
            msg = "You fled!"
            break
        else:
            player.health -= monster.attack
            msg = f"{monster.name} hits you! HP left: {player.health}"
            if player.health <= 0:
                # keep progress: respawn at town, keep LVL/ATK, small XP penalty, save intact
                player.health = player.max_health
                player.xp = max(0, player.xp - 20)
                player.x, player.y = 0, 0
                world.tiles[(0, 0)]["seen"] = True
                save_game(player, world)
                render(world, player, cols, lines, "You died! Respawning at town... (-20 XP) Press any key.")
                get_key()
                return True
    world.tiles[(player.x, player.y)]["cleared"] = True
    return False


def move(player, world, dx, dy, cols, lines):
    nx, ny = player.x + dx, player.y + dy
    if not (0 <= nx < world.w and 0 <= ny < world.h):
        unlocked = get_unlocked(player.lvl)
        if len(unlocked) > 1:
            nxt = next_unlocked(world.map_name, player.lvl, 1)
            return f"Edge of {world.map_name}. Press N→{nxt} or M for maps."
        return "You can't go that way."
    player.x, player.y = nx, ny
    t = world.tiles[(nx, ny)]
    t["seen"] = True
    if t["type"] == "town":
        player.health = player.max_health
        return "You rest at the town. HP fully restored."
    if t["type"] == "treasure" and not t["cleared"]:
        gold = random.randint(20, 60)
        t["cleared"] = True
        newly = player.gain_xp(gold)
        msg = f"You found treasure! +{gold} xp."
        if newly:
            msg += f" Unlocked: {', '.join(newly)}!"
        return msg
    if t["type"] == "monster" and not t["cleared"]:
        died = combat(player, roll_monster(), world, cols, lines)
        if died:
            return "You died and respawned at town (-20 XP). Progress saved."
        return "The area is clear now."
    return "You explore the wilderness..."


def travel_to(player, new_map_name):
    unlocked = get_unlocked(player.lvl)
    if new_map_name not in unlocked:
        return None, f"Map {new_map_name} locked! Need LVL {UNLOCK_AT[new_map_name]} (you {player.lvl}). Unlock by gaining XP."
    # create new world, keep player stats, reset position
    new_world = World(new_map_name)
    new_world.tiles[(0, 0)]["seen"] = True
    player.x, player.y = 0, 0
    save_game(player, new_world)
    return new_world, f"Traveled to [{new_map_name}] — {MAPS[new_map_name]['desc']}"


def show_map_menu(player, world):
    cols, _ = term_size()
    unlocked = get_unlocked(player.lvl)
    locked = [k for k in MAPS if k not in unlocked]
    lines = []
    lines.append(f"Maps — LVL {player.lvl} | Current [{world.map_name}]")
    for i, k in enumerate(sorted(MAPS.keys(), key=lambda x: UNLOCK_AT[x])):
        mark = "●" if k == world.map_name else " "
        if k in unlocked:
            lines.append(f" {mark} {i+1}. {k:10} {MAPS[k]['w']}x{MAPS[k]['h']}  {MAPS[k]['desc']}")
        else:
            lines.append(f"   {i+1}. {k:10} LOCKED (need LVL {UNLOCK_AT[k]})")
    lines.append("Press 1-6 to travel, N/P next/prev, M/Q to close")
    msg = "\n".join(lines)
    # render menu as overlay
    cols, lines_n = term_size()
    render(world, player, cols, lines_n, msg)
    # wait for selection
    while True:
        c = get_key()
        if c in ("m", "q"):
            return None, "Map menu closed."
        if c in ("n",):
            nxt = next_unlocked(world.map_name, player.lvl, 1)
            return nxt, None
        if c in ("p",):
            prv = next_unlocked(world.map_name, player.lvl, -1)
            return prv, None
        if c in [str(i) for i in range(1, 7)]:
            idx = int(c) - 1
            keys = sorted(MAPS.keys(), key=lambda x: UNLOCK_AT[x])
            if 0 <= idx < len(keys):
                chosen = keys[idx]
                if chosen in unlocked:
                    return chosen, None
                else:
                    return None, f"{chosen} locked — need LVL {UNLOCK_AT[chosen]}"
        if c in ("w", "a", "s", "d"):
            # arrow/WASD also cycles maps
            if c in ("d", "s"):
                nxt = next_unlocked(world.map_name, player.lvl, 1)
                return nxt, None
            else:
                prv = next_unlocked(world.map_name, player.lvl, -1)
                return prv, None
        return None, "Invalid key — 1-6, N/P, M/Q"


def play(name=NAME, map_name=DEFAULT_MAP, new_game=False):
    # try load save unless new_game or map mismatch
    player = None
    world = None
    loaded_msg = ""
    if not new_game:
        player, world = load_game(map_name)
        if player and world:
            loaded_msg = f"Loaded save [{world.map_name}] — LVL {player.lvl} XP {player.xp} ATK {player.attack}"
        else:
            player = None
            world = None
    if player is None or world is None:
        player = PlayerStat()
        world = World(map_name)
        world.tiles[(0, 0)]["seen"] = True
        if not new_game and load_game()[0] is not None:
            # was map switch, inform
            loaded_msg = f"New map [{world.map_name}] — {MAPS[world.map_name]['desc']}"
        else:
            loaded_msg = f"New game [{world.map_name}] — {MAPS[world.map_name]['desc']}"
    moves = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
    # map hotkeys: numbers 1-6 direct, n/p next/prev, m menu
    msg = f"{loaded_msg} | WASD/arrows walk | J stats L look M maps N/P 1-6 Q quit"
    try:
        while True:
            cols, lines = term_size()
            render(world, player, cols, lines, msg)
            msg = ""
            cmd = get_key()
            if cmd in moves:
                dx, dy = moves[cmd]
                msg = move(player, world, dx, dy, cols, lines)
            elif cmd == "l":
                unlocked = ", ".join(get_unlocked(player.lvl))
                msg = f"[{world.map_name}] {MAPS[world.map_name]['desc']} — Towns T $ monsters M. Unlocked: {unlocked} (M for maps)"
            elif cmd == "j":
                cols, _ = term_size()
                player.show(cols)
                # also show unlocked
                print(f"Unlocked maps: {', '.join(get_unlocked(player.lvl))}")
                get_key()
            elif cmd == "m":
                chosen, menu_msg = show_map_menu(player, world)
                if chosen:
                    new_world, travel_msg = travel_to(player, chosen)
                    if new_world:
                        world = new_world
                        msg = travel_msg + " | WASD/arrows walk"
                    else:
                        msg = travel_msg
                else:
                    msg = menu_msg
            elif cmd == "n":
                nxt = next_unlocked(world.map_name, player.lvl, 1)
                new_world, travel_msg = travel_to(player, nxt)
                if new_world:
                    world = new_world
                    msg = travel_msg
                else:
                    msg = travel_msg
            elif cmd == "p":
                prv = next_unlocked(world.map_name, player.lvl, -1)
                new_world, travel_msg = travel_to(player, prv)
                if new_world:
                    world = new_world
                    msg = travel_msg
                else:
                    msg = travel_msg
            elif cmd in [str(i) for i in range(1, 7)]:
                keys = sorted(MAPS.keys(), key=lambda x: UNLOCK_AT[x])
                idx = int(cmd) - 1
                if 0 <= idx < len(keys):
                    chosen = keys[idx]
                    new_world, travel_msg = travel_to(player, chosen)
                    if new_world:
                        world = new_world
                        msg = travel_msg
                    else:
                        msg = travel_msg
                else:
                    msg = "Invalid map number."
            elif cmd == "q":
                save_game(player, world)
                msg = f"Saved [{world.map_name}] LVL {player.lvl} XP {player.xp} — bye!"
                cols, lines = term_size()
                render(world, player, cols, lines, msg)
                break
            else:
                msg = "Use WASD/arrows walk, J stats, L look, M maps, N/P next/prev, 1-6 travel, Q quit."
    finally:
        # also save on exit via finally (covers quit loop break)
        try:
            if player.health > 0:
                save_game(player, world)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        prog="cli-open-world", description="CLI OPEN WORLD - an open world CLI adventure.")
    parser.add_argument("-n", "--name", default=NAME,
                        help=f"name to greet (default: {NAME})")
    parser.add_argument("--stats", action="store_true",
                        help="show default player stats and exit")
    parser.add_argument("--map", choices=list(MAPS.keys()), default=None,
                        help="choose map: " + ", ".join(f"{k} ({v['desc']})" for k, v in MAPS.items()))
    parser.add_argument("--list-maps", action="store_true",
                        help="list all maps and exit")
    parser.add_argument("--new", "--reset", dest="new", action="store_true",
                        help="start new game, ignore saved progress")
    parser.add_argument("--delete-save", action="store_true",
                        help="delete saved game and exit")
    args = parser.parse_args()

    if args.list_maps:
        for k, v in MAPS.items():
            print(f"{k:10} {v['w']}x{v['h']}  {v['desc']}  treasures={v['treasures']} monsters={v['monsters']}")
        return

    if args.delete_save:
        if delete_save():
            print("Save deleted.")
        else:
            print("No save to delete.")
        return

    if args.stats:
        # show saved stats if exists, else default
        p, w = load_game(args.map)
        target = p if p else PlayerStat()
        cols, _ = term_size()
        if p:
            print(f"Saved [{w.map_name}] — ", end="")
        target.show(cols)
        return

    try:
        play(args.name, map_name=args.map or DEFAULT_MAP, new_game=args.new)
    except KeyboardInterrupt:
        # save on Ctrl+C as well
        try:
            p, w = load_game()
            # play's finally already saves, but if interrupted before play, just exit
            pass
        except Exception:
            pass
        os.system(CLEAR)
        print("Quitting... (progress saved)")
        sys.exit(0)


if __name__ == "__main__":
    main()
