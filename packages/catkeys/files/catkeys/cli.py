"""catkeys command line."""

import argparse
import json
import os
import signal
import sys
import time

from . import __version__, config as config_mod
from .actions import REASONS, Actions
from .daemon import Daemon, read_json, running_pid, state_file, stats_file


def _state():
    pid = running_pid()
    state = read_json(state_file(), {}) if pid else {}
    return pid, state


def _signal_daemon(signum):
    pid = running_pid()
    if not pid:
        print("catkeys is not running. Start it with: catkeys daemon", file=sys.stderr)
        return 1
    os.kill(pid, signum)
    return 0


def cmd_daemon(_args):
    if running_pid():
        print("catkeys is already running.", file=sys.stderr)
        return 1
    try:
        Daemon(config_mod.load()).run()
    except ModuleNotFoundError:
        print("catkeys needs the python-evdev package.", file=sys.stderr)
        return 1
    return 0


def cmd_status(_args):
    pid, state = _state()
    if not pid:
        print("catkeys: not running")
        return 1
    if state.get("locked"):
        what = f"LOCKED ({REASONS.get(state.get('reason'), 'cat')})"
    elif state.get("paused"):
        what = "paused"
    else:
        what = "watching"
    print(f"catkeys: {what}, {state.get('keyboards', 0)} keyboard(s), pid {pid}")
    return 0


def cmd_stats(_args):
    stats = read_json(stats_file(), {})
    count = stats.get("detections", 0)
    print(f"Cats caught on the keyboard: {count}")
    if count:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(stats.get("last_time", 0)))
        print(f"Last one: {REASONS.get(stats.get('last_reason'), 'cat')} at {when}")
    return 0


def cmd_waybar(_args):
    pid, state = _state()
    stats = read_json(stats_file(), {})
    caught = f"Cats caught: {stats.get('detections', 0)}"
    if not pid:
        out = {"text": "⌨️ off", "class": "off", "tooltip": "catkeys is not running"}
    elif state.get("locked"):
        out = {"text": "🐾 LOCKED", "class": "locked",
               "tooltip": f"Cat on the keyboard! Click to unlock.\n{caught}"}
    elif state.get("paused"):
        out = {"text": "⌨️ paused", "class": "paused",
               "tooltip": f"Cat detection paused. Right-click to resume.\n{caught}"}
    else:
        out = {"text": "⌨️", "class": "watching",
               "tooltip": f"Watching for cats. Right-click to pause.\n{caught}"}
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_test(args):
    actions = Actions(config_mod.load())
    print(f"Pretending a cat landed. Keyboard locks for {args.seconds:g}s...")
    actions.lock("test")
    try:
        time.sleep(args.seconds)
    finally:
        ok = actions.unlock()
    print("Unlocked." if ok else "The unlock command failed!")
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="catkeys",
        description="Detects a cat on the keyboard and locks it until the cat leaves.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.add_parser("daemon", help="watch the keyboards (runs in the foreground)")
    sub.add_parser("status", help="show what the daemon is doing")
    sub.add_parser("unlock", help="unlock the keyboard right now")
    sub.add_parser("pause", help="pause or resume detection (for games)")
    sub.add_parser("stats", help="how many cats have been caught")
    sub.add_parser("waybar", help="status as JSON for a waybar module")
    test = sub.add_parser("test", help="lock and unlock once to try your setup")
    test.add_argument("seconds", nargs="?", type=float, default=3.0)
    args = parser.parse_args(argv)

    try:
        if args.command == "daemon":
            return cmd_daemon(args)
        if args.command == "unlock":
            return _signal_daemon(signal.SIGUSR1)
        if args.command == "pause":
            return _signal_daemon(signal.SIGUSR2)
        if args.command == "stats":
            return cmd_stats(args)
        if args.command == "waybar":
            return cmd_waybar(args)
        if args.command == "test":
            return cmd_test(args)
        return cmd_status(args)
    except ValueError as error:  # bad config
        print(f"catkeys: {error}", file=sys.stderr)
        return 2
