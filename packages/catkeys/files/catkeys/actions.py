"""Side effects: locking the keyboard in the compositor and notifying."""

import os
import random
import shutil
import subprocess

# How to stop the compositor from listening to keyboards. Disabling the
# device in libinput also releases any keys that were held, so nothing gets
# stuck repeating while the cat is parked on it.
_AUTO = {
    "sway": ("swaymsg input type:keyboard events disabled",
             "swaymsg input type:keyboard events enabled"),
}

REASONS = {
    "smash": "paw smash",
    "loaf": "cat loaf",
    "walk": "cat walk",
    "test": "test run",
}


def _compositor():
    if os.environ.get("SWAYSOCK") and shutil.which("swaymsg"):
        return "sway"
    return None


def resolve(command, index):
    """Turn the 'auto' setting into a real command ('' means notify only)."""
    if command != "auto":
        return command
    pair = _AUTO.get(_compositor())
    return pair[index] if pair else ""


def run(command):
    if not command:
        return True
    try:
        return subprocess.run(command, shell=True, timeout=5,
                              stdout=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def notify(title, body, urgency="normal", timeout_ms=5000):
    if not shutil.which("notify-send"):
        return
    try:
        subprocess.run(
            ["notify-send", "-a", "catkeys", "-u", urgency, "-t", str(timeout_ms),
             "-h", "string:x-canonical-private-synchronous:catkeys", title, body],
            timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


class Actions:
    def __init__(self, config):
        self.config = config

    def lock(self, reason):
        run(resolve(self.config.lock_command, 0))
        if self.config.notify:
            hint = (f"Type “{self.config.unlock_word}” or just wait for the cat to leave."
                    if self.config.unlock_word else "Unlocks when the cat leaves.")
            notify(f"🐾 {random.choice(self.config.messages())}",
                   f"{REASONS.get(reason, reason)} — {hint}",
                   urgency="critical", timeout_ms=0)

    def unlock(self):
        ok = run(resolve(self.config.unlock_command, 1))
        if self.config.notify:
            notify("⌨️ Keyboard unlocked", "The coast is clear.")
        return ok
