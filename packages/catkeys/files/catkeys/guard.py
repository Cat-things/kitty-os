"""Lock state machine: decides when the keyboard is locked and unlocked."""

from .detector import KEY_DOWN, KEY_UP, Detector
from .layout import LETTERS


class Guard:
    """Feeds key events to a Detector and tracks the locked state.

    feed() and tick() return "lock", "unlock" or None so the caller can run
    the side effects. While locked the keyboard unlocks again when either the
    unlock word is typed, or nothing has touched it for quiet_seconds.
    """

    def __init__(self, detector=None, unlock_word="human", quiet_seconds=4.0):
        self.detector = detector or Detector()
        self.unlock_word = unlock_word.lower()
        self.quiet_seconds = quiet_seconds
        self.locked = False
        self.paused = False
        self.reason = None
        self._down = set()
        self._typed = ""
        self._last_event = 0.0

    def feed(self, code, value, now):
        self._last_event = now
        if value == KEY_UP:
            self._down.discard(code)
        else:
            self._down.add(code)
        if self.locked:
            if value == KEY_DOWN and self.unlock_word:
                self._typed = (self._typed + LETTERS.get(code, " "))[-len(self.unlock_word):]
                if self._typed == self.unlock_word:
                    return self.unlock()
            return None
        if self.paused:
            return None
        reason = self.detector.feed(code, value, now)
        return self._lock(reason) if reason else None

    def tick(self, now):
        if self.locked:
            if not self._down and now - self._last_event >= self.quiet_seconds:
                return self.unlock()
            return None
        if self.paused:
            return None
        reason = self.detector.tick(now)
        return self._lock(reason) if reason else None

    def forget_keys(self):
        """Drop held-key state, e.g. when a keyboard is unplugged."""
        self._down.clear()
        self.detector.reset()

    def _lock(self, reason):
        self.locked = True
        self.reason = reason
        self._typed = ""
        return "lock"

    def unlock(self):
        if not self.locked:
            return None
        self.locked = False
        self.reason = None
        self._typed = ""
        self.detector.reset()
        return "unlock"
