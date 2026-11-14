"""Cat modes.

A mode is a directory holding everything that changes with it:

    mode.conf    NAME, DESCRIPTION, ICON, LABEL, ACCENT  (key = value)
    facts.txt    one line each, shown by catfact, the greeting and the bar
    catkeys.txt  notification texts for the keyboard detector
    greeting.txt art printed when a terminal opens
    sway.conf    included by the sway config (accent colour, wallpaper, keys)
    kitty.conf   included by the terminal config
    waybar.css   imported by the bar style

Modes live in /usr/share/kitty-os/modes, and your own go in
~/.local/share/kitty-os/modes. The active one is the symlink
~/.config/kitty-os/current, which is what all the configs point at.
"""

import os
import random
import shutil
import subprocess
from pathlib import Path

DEFAULT_MODE = "cat"
SYSTEM_MODES = Path("/usr/share/kitty-os/modes")


class ModeError(Exception):
    pass


def _xdg(variable, fallback):
    return Path(os.environ.get(variable) or os.path.expanduser(fallback))


def config_dir():
    return _xdg("XDG_CONFIG_HOME", "~/.config") / "kitty-os"


def state_dir():
    return _xdg("XDG_STATE_HOME", "~/.local/state") / "kitty-os"


def mode_dirs():
    override = os.environ.get("KITTY_OS_MODES_DIR")
    if override:
        return [Path(override)]
    return [_xdg("XDG_DATA_HOME", "~/.local/share") / "kitty-os" / "modes", SYSTEM_MODES]


class Mode:
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        self.settings = {}
        try:
            lines = (self.path / "mode.conf").read_text().splitlines()
        except OSError:
            lines = []
        for line in lines:
            key, sep, value = line.partition("=")
            if sep and not key.lstrip().startswith("#"):
                self.settings[key.strip().upper()] = value.strip()

    @property
    def title(self):
        return self.settings.get("NAME", self.name)

    @property
    def description(self):
        return self.settings.get("DESCRIPTION", "")

    @property
    def icon(self):
        return self.settings.get("ICON", "🐱")

    @property
    def label(self):
        return self.settings.get("LABEL", self.name)

    @property
    def accent(self):
        return self.settings.get("ACCENT", "#cba6f7")

    def lines(self, filename):
        try:
            text = (self.path / filename).read_text()
        except OSError:
            return []
        return [line.strip() for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")]

    def text(self, filename):
        try:
            return (self.path / filename).read_text()
        except OSError:
            return ""

    def fact(self):
        facts = self.lines("facts.txt")
        return random.choice(facts) if facts else "Cats are great."


def available():
    """All installed modes by name. Your own modes win over system ones."""
    found = {}
    for directory in reversed(mode_dirs()):
        if directory.is_dir():
            for path in sorted(directory.iterdir()):
                if (path / "mode.conf").is_file():
                    found[path.name] = Mode(path)
    return dict(sorted(found.items(), key=lambda item: (item[0] != DEFAULT_MODE, item[0])))


def get(name):
    modes = available()
    if name not in modes:
        raise ModeError(f"no such mode: {name} (have: {', '.join(modes) or 'none'})")
    return modes[name]


def current_name():
    try:
        name = (config_dir() / "mode").read_text().strip()
    except OSError:
        name = ""
    return name if name in available() else DEFAULT_MODE


def current():
    return get(current_name())


def set_mode(name, apply=True):
    mode = get(name)
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    link, tmp = directory / "current", directory / ".current.tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    tmp.symlink_to(mode.path)
    tmp.replace(link)
    (directory / "mode").write_text(mode.name + "\n")
    if apply:
        reload_desktop(mode)
    return mode


def next_mode(apply=True):
    names = list(available())
    if not names:
        raise ModeError("no modes installed")
    now = current_name()
    following = names[(names.index(now) + 1) % len(names)] if now in names else names[0]
    return set_mode(following, apply)


def _quiet(*command):
    if not shutil.which(command[0]):
        return
    try:
        subprocess.run(command, timeout=5, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        pass


def reload_desktop(mode):
    """Make running programs pick up the new mode."""
    if os.environ.get("SWAYSOCK"):
        _quiet("swaymsg", "reload")          # sway, wallpaper and the bar
    _quiet("pkill", "-USR1", "-x", "kitty")  # every open terminal
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
        _quiet("notify-send", "-a", "catmode", "-t", "3000",
               f"{mode.icon} {mode.title}", mode.description)
