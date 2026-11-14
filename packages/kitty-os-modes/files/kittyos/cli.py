"""Entry points for catmode, catfact, catsay and pspsps."""

import argparse
import json
import random
import sys
import time

from . import art, modes


def _fail(error):
    print(f"error: {error}", file=sys.stderr)
    return 1


def catmode(argv=None):
    parser = argparse.ArgumentParser(
        prog="catmode",
        description="Show or switch the cat mode. 'catmode salma' is short for 'catmode set salma'.")
    parser.add_argument("action", nargs="?", default="show",
                        help="show, list, set NAME, next, greet, waybar, or a mode name")
    parser.add_argument("name", nargs="?")
    parser.add_argument("--no-apply", action="store_true",
                        help="switch without reloading the desktop")
    args = parser.parse_args(argv)
    apply = not args.no_apply
    try:
        if args.action == "show":
            mode = modes.current()
            print(f"{mode.icon} {mode.name} - {mode.title}")
            if mode.description:
                print(mode.description)
        elif args.action == "list":
            now = modes.current_name()
            for name, mode in modes.available().items():
                marker = "*" if name == now else " "
                print(f"{marker} {name:<10} {mode.icon} {mode.description}")
        elif args.action == "next":
            mode = modes.next_mode(apply)
            print(f"{mode.icon} {mode.title}")
        elif args.action == "greet":
            mode = modes.current()
            greeting = mode.text("greeting.txt").rstrip("\n")
            if greeting:
                print(art.paint(greeting, mode.accent))
            print(f"{mode.icon} {mode.fact()}")
        elif args.action == "waybar":
            mode = modes.current()
            print(json.dumps({
                "text": f"{mode.icon} {mode.label}",
                "tooltip": f"{mode.title}\n{mode.fact()}\n\nClick to switch mode",
                "class": mode.name,
            }, ensure_ascii=False))
        else:
            name = args.name if args.action == "set" else args.action
            if not name:
                return _fail("which mode? try: catmode list")
            mode = modes.set_mode(name, apply)
            print(f"{mode.icon} {mode.title}")
    except modes.ModeError as error:
        return _fail(error)
    return 0


def catfact(argv=None):
    parser = argparse.ArgumentParser(
        prog="catfact", description="Print a fact from the current cat mode.")
    parser.add_argument("-m", "--mode", help="use this mode instead of the current one")
    parser.add_argument("-a", "--all", action="store_true", help="print every fact")
    parser.add_argument("-s", "--say", action="store_true", help="let a cat say it")
    args = parser.parse_args(argv)
    try:
        mode = modes.get(args.mode) if args.mode else modes.current()
    except modes.ModeError as error:
        return _fail(error)
    if args.all:
        print("\n".join(mode.lines("facts.txt")))
    elif args.say:
        print(art.catsay(mode.fact()))
    else:
        print(mode.fact())
    return 0


def catsay(argv=None):
    parser = argparse.ArgumentParser(prog="catsay", description="A cat says things.")
    parser.add_argument("words", nargs="*", help="what to say (default: read stdin)")
    args = parser.parse_args(argv)
    text = " ".join(args.words) if args.words else sys.stdin.read().strip()
    print(art.catsay(text or "meow"))
    return 0


PSPSPS = (
    (5, "A cat appears. It looks at you. It needed nothing.", art.CAT),
    (3, "The cat heard you. The cat is choosing not to come.", None),
    (3, "One ear rotates in your direction. That is all you get.", None),
    (2, "zzz... the cat is asleep and you are not important enough.", art.SLEEPING_CAT),
    (1, "The cat sprints in from another room at full speed, then leaves.", art.CAT),
)


def pspsps(argv=None):
    argparse.ArgumentParser(
        prog="pspsps", description="Call a cat. Results not guaranteed.").parse_args(argv)
    if sys.stdout.isatty():
        for _ in range(3):
            print("ps", end="", flush=True)
            time.sleep(0.25)
        print("...")
        time.sleep(0.6)
    _, line, picture = random.choices(PSPSPS, weights=[w for w, _, _ in PSPSPS])[0]
    if picture:
        print(art.paint(picture, modes.current().accent))
    print(line)
    return 0
