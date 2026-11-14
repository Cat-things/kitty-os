"""salma - the command line side of Salma mode."""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from kittyos import art, modes

ACCENT = "#fab387"
NAME_CALL = "meo-meo-meow"
FILES_NAME = "The Salma Files"
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic", ".bmp"}

SALMA = r"""
 /\_/\
( ^.^ )
 > ^ <
""".strip("\n")

# What is on the menu. Everything else gets refused too, just less firmly.
GOOD_FOOD = {"croquettes", "croquette", "kibble"}
BAD_FOOD = {"tuna", "pate", "pâté", "paté", "pâte"}

TOYS = {
    "wand": "the wand toy with the bird wings",
    "flower": "the dusty crochet flower",
}

NAP_SPOTS = (
    (7, "on the bed"),
    (3, "on the cat tree next to the TV"),
)

ANSWERS = (
    "Mrrp? Salma looks up.",
    "Salma answers with a small meow and trots over.",
    "Salma's ears turn. She heard her name.",
    "Meow! Salma is on her way.",
)


def state_file():
    return modes.state_dir() / "salma.json"


def load_state():
    try:
        state = json.loads(state_file().read_text())
    except (OSError, ValueError):
        state = {}
    state.setdefault("under_couch", [])
    state.setdefault("fed", 0)
    return state


def save_state(state):
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))


def pictures_dir():
    base = os.environ.get("XDG_PICTURES_DIR")
    if not base and shutil.which("xdg-user-dir"):
        try:
            base = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True,
                                  text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            base = ""
    home = os.path.expanduser("~")
    if not base or os.path.realpath(base) == os.path.realpath(home):
        base = os.path.join(home, "Pictures")
    return Path(base)


def files_dir():
    path = pictures_dir() / FILES_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def pictures():
    return sorted(p for p in files_dir().iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_TYPES)


def say(text):
    print(art.paint(SALMA, ACCENT))
    print(text)


# --- commands ---------------------------------------------------------------

def cmd_status(_args):
    state = load_state()
    spot = random.choices([s for _, s in NAP_SPOTS], [w for w, _ in NAP_SPOTS])[0]
    print(art.paint(SALMA, ACCENT))
    print(art.paint("Salma", ACCENT, bold=True))
    print(f"  answers to   {NAME_CALL}")
    print("  eats         croquettes only (no tuna, no pâté)")
    print(f"  napping      probably {spot}")
    print(f"  top toy      {TOYS['wand']}")
    lost = [TOYS[t] for t in state["under_couch"] if t in TOYS]
    print(f"  under couch  {', '.join(lost) if lost else 'nothing, for once'}")
    print(f"  pictures     {len(pictures())} in “{FILES_NAME}”")
    if modes.current_name() != "salma":
        print("\nSalma mode is off. Turn it on with: catmode salma")
    return 0


def cmd_call(args):
    name = " ".join(args.name).strip().lower() if args.name else NAME_CALL
    if name == NAME_CALL:
        line = random.choice(ANSWERS)
        code = 0
    else:
        line = f"Nothing. She does not answer to “{name}”. Try {NAME_CALL}."
        code = 1
    if args.quiet:
        print(line)
    else:
        say(line)
    return code


def cmd_feed(args):
    food = " ".join(args.food).strip().lower() if args.food else "croquettes"
    if food in GOOD_FOOD:
        state = load_state()
        state["fed"] += 1
        save_state(state)
        say(f"Crunch crunch. Croquettes served ({state['fed']} bowls so far).")
        return 0
    if food in BAD_FOOD:
        say(f"No {food} for Salma. It makes her sick. Croquettes only.")
        return 1
    say(f"“{food}” is not on Salma's menu. Croquettes only.")
    return 1


def _animate(frames, delay=0.12):
    if not sys.stdout.isatty():
        return
    height = frames[0].count("\n") + 1
    try:
        for i, frame in enumerate(frames):
            if i:
                print(f"\033[{height}A", end="")
            print("\n".join(f"\033[2K{line}" for line in frame.split("\n")))
            time.sleep(delay)
    except KeyboardInterrupt:
        print()


def _wand_frames():
    frames = []
    for position in list(range(0, 22, 2)) + list(range(20, -1, -2)):
        wings = r"\v/" if position % 4 == 0 else "/^\\"
        string = " " * position + "|"
        bird = " " * max(position - 1, 0) + wings
        eyes = "o.o" if position % 8 else "O.O"
        cat = " " * (position // 2) + rf" /\_/\  " + "\n" + " " * (position // 2) + f"( {eyes} )"
        frames.append(f"{string}\n{bird}\n\n{cat}")
    return frames


def _flower_frames():
    frames = []
    for i in range(14):
        offset = (0, 1, 2, 3, 2, 1)[i % 6]
        flower = " " * (12 + offset) + "@}-,-"
        paw = " /\\_/\\ " + ("  __/" if i % 2 else "  __")
        frames.append(f"{flower}\n{paw}\n( o.o )")
    return frames


def cmd_play(args):
    toy = args.toy
    state = load_state()
    if toy is None:
        free = [t for t in TOYS if t not in state["under_couch"]]
        if not free:
            say("Every toy is under the couch. Rescue them: salma couch --rescue")
            return 1
        toy = free[0]
    if toy in state["under_couch"]:
        say(f"{TOYS[toy].capitalize()} is under the couch. Rescue it: salma couch --rescue")
        return 1
    _animate(_wand_frames() if toy == "wand" else _flower_frames())
    if random.random() < 1 / 3:
        state["under_couch"].append(toy)
        save_state(state)
        say(f"Salma played with {TOYS[toy]}... and knocked it under the couch. D:")
    else:
        say(f"Salma played with {TOYS[toy]}. 10/10, would pounce again.")
    return 0


def cmd_couch(args):
    state = load_state()
    lost = [t for t in state["under_couch"] if t in TOYS]
    if not lost:
        print("Nothing under the couch right now. Give it a minute.")
        return 0
    if args.rescue:
        state["under_couch"] = []
        save_state(state)
        for toy in lost:
            print(f"Rescued {TOYS[toy]}.")
        print("Salma is already eyeing the couch.")
        return 0
    print("Under the couch:")
    for toy in lost:
        print(f"  - {TOYS[toy]}")
    print("Get them back with: salma couch --rescue")
    return 0


def _open(path):
    for opener in ("xdg-open", "thunar", "imv"):
        if shutil.which(opener):
            subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            return True
    return False


def cmd_files(args):
    folder = files_dir()
    action = args.action
    if action == "path":
        print(folder)
    elif action == "count":
        print(len(pictures()))
    elif action == "add":
        if not args.paths:
            print("usage: salma files add PICTURE...", file=sys.stderr)
            return 2
        added = 0
        for source in map(Path, args.paths):
            if not source.is_file():
                print(f"skipped {source}: not a file", file=sys.stderr)
                continue
            target = folder / source.name
            number = 1
            while target.exists():
                target = folder / f"{source.stem}-{number}{source.suffix}"
                number += 1
            shutil.copy2(source, target)
            added += 1
        print(f"Added {added} to “{FILES_NAME}” ({len(pictures())} total).")
        return 0 if added else 1
    elif action in ("random", "wallpaper"):
        found = pictures()
        if not found:
            print(f"“{FILES_NAME}” is empty. Add some: salma files add PICTURE...",
                  file=sys.stderr)
            return 1
        choice = random.choice(found)
        if action == "random":
            print(choice)
            if sys.stdout.isatty() and os.environ.get("TERM") == "xterm-kitty":
                subprocess.run(["kitty", "+kitten", "icat", str(choice)], check=False)
        elif not os.environ.get("SWAYSOCK"):
            print("Setting the wallpaper needs a running sway session.", file=sys.stderr)
            return 1
        else:
            subprocess.run(["swaymsg", "output", "*", "bg", str(choice), "fill"],
                           check=False, stdout=subprocess.DEVNULL)
            print(f"Wallpaper: {choice.name}")
    else:  # open
        print(folder)
        if not _open(folder):
            print("No file manager found to open it.", file=sys.stderr)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="salma", description="All things Salma.")
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.add_parser("status", help="how Salma is doing (the default)")
    call = sub.add_parser("call", help=f"call her (she answers to {NAME_CALL})")
    call.add_argument("name", nargs="*")
    call.add_argument("-q", "--quiet", action="store_true", help="just the answer, no art")
    feed = sub.add_parser("feed", help="feed her (croquettes only)")
    feed.add_argument("food", nargs="*")
    play = sub.add_parser("play", help="play with a toy")
    play.add_argument("toy", nargs="?", choices=sorted(TOYS))
    couch = sub.add_parser("couch", help="see which toys ended up under the couch")
    couch.add_argument("-r", "--rescue", action="store_true", help="fish them out")
    files = sub.add_parser("files", help=f"“{FILES_NAME}”: every picture of her")
    files.add_argument("action", nargs="?", default="open",
                       choices=("open", "add", "random", "wallpaper", "count", "path"))
    files.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    handler = {
        "call": cmd_call, "feed": cmd_feed, "play": cmd_play,
        "couch": cmd_couch, "files": cmd_files,
    }.get(args.command, cmd_status)
    return handler(args)


def name_call(argv=None):
    """The meo-meo-meow command."""
    argparse.ArgumentParser(
        prog=NAME_CALL, description="Call Salma by the name she answers to.").parse_args(argv)
    return main(["call"])
