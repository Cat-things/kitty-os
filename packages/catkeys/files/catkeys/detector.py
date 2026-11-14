"""The cat detection heuristics. Pure logic, no I/O, so it is easy to test.

Three things give a cat away:

smash  A paw (or a whole cat) lands: several touching keys go down at the
       same instant, across more than one row. Fingers hit one key at a time.
loaf   A group of touching keys stays held down. The cat has sat down.
walk   Paw-sized blobs of keys land one after another. The cat is on tour.

Modifier keys are ignored everywhere: humans hold those all day.
"""

from dataclasses import dataclass

from .layout import MODIFIERS, clusters, rows_spanned

KEY_UP, KEY_DOWN, KEY_REPEAT = 0, 1, 2


@dataclass(frozen=True)
class Tuning:
    smash_keys: int = 4          # touching keys landing together
    smash_spread: float = 0.15   # ... within this many seconds
    pile_keys: int = 6           # this many keys held at once, anywhere
    loaf_keys: int = 3           # touching keys held ...
    loaf_seconds: float = 2.0    # ... for this long
    step_keys: int = 3           # one paw step: touching keys ...
    step_spread: float = 0.06    # ... landing within this many seconds
    steps: int = 2               # steps needed ...
    walk_window: float = 4.0     # ... within this many seconds


SENSITIVITY = {
    "low": Tuning(smash_keys=5, pile_keys=7, loaf_keys=4, loaf_seconds=3.0,
                  step_keys=4, steps=3),
    "medium": Tuning(),
    "high": Tuning(smash_keys=3, pile_keys=5, loaf_seconds=1.0, steps=1),
}


class Detector:
    def __init__(self, tuning=None):
        self.tuning = tuning or Tuning()
        self.held = {}        # key code -> time it went down
        self.steps = []       # times of recent paw steps
        self._last_step = frozenset()

    def reset(self):
        self.held.clear()
        self.steps.clear()
        self._last_step = frozenset()

    def feed(self, code, value, now):
        """Process one key event. Returns the reason if a cat was detected."""
        if code in MODIFIERS:
            return None
        if value == KEY_UP:
            self.held.pop(code, None)
            return None
        if value == KEY_REPEAT:
            self.held.setdefault(code, now)
            return self.tick(now)
        self.held[code] = now
        return self._check_landing(now) or self.tick(now)

    def tick(self, now):
        """Time-based checks. Call it periodically even without key events."""
        t = self.tuning
        for group in clusters(self.held):
            if len(group) >= t.loaf_keys and all(
                    now - self.held[c] >= t.loaf_seconds for c in group):
                return "loaf"
        return None

    def _check_landing(self, now):
        t = self.tuning
        if len(self.held) >= t.pile_keys:
            return "smash"
        for group in clusters(self.held):
            times = [self.held[c] for c in group]
            spread = max(times) - min(times)
            if (len(group) >= t.smash_keys and spread <= t.smash_spread
                    and rows_spanned(group) >= 2):
                return "smash"
            if len(group) >= t.step_keys and spread <= t.step_spread:
                # One landing grows key by key; count it as a single step.
                if not (self._last_step and self._last_step <= group):
                    self.steps.append(now)
                self._last_step = frozenset(group)
        self.steps = [s for s in self.steps if now - s <= t.walk_window]
        if len(self.steps) >= t.steps:
            return "walk"
        return None
