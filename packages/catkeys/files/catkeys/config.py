"""Configuration: /etc/catkeys.conf, then ~/.config/catkeys/catkeys.conf."""

import configparser
import os
from dataclasses import dataclass, replace
from pathlib import Path

from .detector import SENSITIVITY, Tuning

SYSTEM_CONFIG = Path("/etc/catkeys.conf")

DEFAULT_MESSAGES = (
    "Cat detected on the keyboard. Input paused.",
    "Paws off! Keyboard locked until the cat moves along.",
    "That was not typing. That was a cat.",
)


def user_config():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "catkeys" / "catkeys.conf"


def runtime_dir():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/catkeys-{os.getuid()}"
    return Path(base) / "catkeys"


def state_dir():
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "catkeys"


@dataclass(frozen=True)
class Config:
    sensitivity: str = "medium"
    unlock_word: str = "human"
    quiet_seconds: float = 4.0
    lock_command: str = "auto"
    unlock_command: str = "auto"
    notify: bool = True
    messages_file: str = "~/.config/kitty-os/current/catkeys.txt"

    @property
    def tuning(self) -> Tuning:
        return SENSITIVITY[self.sensitivity]

    def messages(self):
        path = Path(os.path.expanduser(self.messages_file))
        try:
            lines = [line.strip() for line in path.read_text().splitlines()]
        except OSError:
            lines = []
        lines = [line for line in lines if line and not line.startswith("#")]
        return lines or list(DEFAULT_MESSAGES)


def load(paths=None):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(paths if paths is not None else [SYSTEM_CONFIG, user_config()])
    if not parser.has_section("catkeys"):
        return Config()
    section = parser["catkeys"]
    config = Config()
    config = replace(
        config,
        sensitivity=section.get("sensitivity", config.sensitivity).strip().lower(),
        unlock_word=section.get("unlock_word", config.unlock_word).strip().lower(),
        quiet_seconds=section.getfloat("quiet_seconds", config.quiet_seconds),
        lock_command=section.get("lock_command", config.lock_command).strip(),
        unlock_command=section.get("unlock_command", config.unlock_command).strip(),
        notify=section.getboolean("notify", config.notify),
        messages_file=section.get("messages_file", config.messages_file).strip(),
    )
    if config.sensitivity not in SENSITIVITY:
        raise ValueError(
            f"sensitivity must be one of {', '.join(SENSITIVITY)}, "
            f"not {config.sensitivity!r}")
    return config
