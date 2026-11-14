"""The catkeys daemon: watches keyboards through evdev."""

import json
import os
import select
import signal
import sys
import time

from . import config as config_mod
from .actions import Actions
from .detector import Detector
from .guard import Guard

RESCAN_SECONDS = 5.0
TICK_SECONDS = 0.25
EV_KEY = 1
KEY_A, KEY_Z, KEY_Q = 30, 44, 16


def pid_file():
    return config_mod.runtime_dir() / "pid"


def state_file():
    return config_mod.runtime_dir() / "state.json"


def stats_file():
    return config_mod.state_dir() / "stats.json"


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


class Keyboards:
    """Tracks every keyboard in /dev/input, including hotplugged ones."""

    def __init__(self):
        import evdev  # imported late so the rest works without python-evdev
        self._evdev = evdev
        self.devices = {}
        self.denied = 0

    def rescan(self):
        self.denied = 0
        for path in self._evdev.list_devices():
            if path in self.devices:
                continue
            try:
                device = self._evdev.InputDevice(path)
            except PermissionError:
                self.denied += 1
                continue
            except OSError:
                continue
            keys = device.capabilities().get(EV_KEY, ())
            if all(code in keys for code in (KEY_A, KEY_Z, KEY_Q)):
                self.devices[path] = device
            else:
                device.close()

    def read(self, timeout):
        """Yield (code, value) for key events, waiting up to timeout seconds."""
        if not self.devices:
            time.sleep(timeout)
            return
        by_fd = {dev.fd: (path, dev) for path, dev in self.devices.items()}
        ready, _, _ = select.select(list(by_fd), [], [], timeout)
        for fd in ready:
            path, device = by_fd[fd]
            try:
                for event in device.read():
                    if event.type == EV_KEY:
                        yield event.code, event.value
            except OSError:  # unplugged
                self.devices.pop(path, None)
                yield None, None


class Daemon:
    def __init__(self, config):
        self.config = config
        self.guard = Guard(Detector(config.tuning), config.unlock_word,
                           config.quiet_seconds)
        self.actions = Actions(config)
        self.keyboards = Keyboards()
        self.running = True
        self._wanted = set()

    def _on_signal(self, signum, _frame):
        self._wanted.add(signum)

    def _handle_signals(self):
        wanted, self._wanted = self._wanted, set()
        if signal.SIGUSR1 in wanted:
            self._apply(self.guard.unlock())
        if signal.SIGUSR2 in wanted:
            self.guard.paused = not self.guard.paused
            self._publish()
        if wanted & {signal.SIGTERM, signal.SIGINT, signal.SIGHUP}:
            self.running = False

    def _apply(self, outcome):
        if outcome == "lock":
            stats = read_json(stats_file(), {})
            stats["detections"] = stats.get("detections", 0) + 1
            stats["last_reason"] = self.guard.reason
            stats["last_time"] = int(time.time())
            write_json(stats_file(), stats)
            self.actions.lock(self.guard.reason)
        elif outcome == "unlock":
            self.actions.unlock()
        if outcome:
            self._publish()

    def _publish(self):
        write_json(state_file(), {
            "locked": self.guard.locked,
            "paused": self.guard.paused,
            "reason": self.guard.reason,
            "keyboards": len(self.keyboards.devices),
        })

    def run(self):
        for signum in (signal.SIGUSR1, signal.SIGUSR2, signal.SIGTERM,
                       signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, self._on_signal)
        pid_file().parent.mkdir(parents=True, exist_ok=True)
        pid_file().write_text(str(os.getpid()))
        last_scan = 0.0
        try:
            while self.running:
                now = time.monotonic()
                if now - last_scan >= RESCAN_SECONDS:
                    before = len(self.keyboards.devices)
                    self.keyboards.rescan()
                    if last_scan == 0.0 or before != len(self.keyboards.devices):
                        self._report_keyboards()
                        self._publish()
                    last_scan = now
                for code, value in self.keyboards.read(TICK_SECONDS):
                    if code is None:
                        self.guard.forget_keys()
                        continue
                    self._apply(self.guard.feed(code, value, time.monotonic()))
                self._apply(self.guard.tick(time.monotonic()))
                self._handle_signals()
        finally:
            if self.guard.locked:  # never leave the keyboard dead behind us
                self.guard.unlock()
                self.actions.unlock()
            for path in (pid_file(), state_file()):
                try:
                    path.unlink()
                except OSError:
                    pass

    def _report_keyboards(self):
        count = len(self.keyboards.devices)
        print(f"catkeys: watching {count} keyboard(s)", file=sys.stderr, flush=True)
        if not count and self.keyboards.denied:
            print("catkeys: no permission to read /dev/input. Add yourself to "
                  "the 'input' group (sudo usermod -aG input $USER) and log "
                  "in again.", file=sys.stderr, flush=True)


def running_pid():
    try:
        pid = int(pid_file().read_text())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None
