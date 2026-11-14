import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages/catkeys/files"))

from catkeys import config as config_mod
from catkeys.detector import SENSITIVITY, Detector
from catkeys.guard import Guard
from catkeys.layout import LETTERS, adjacent, clusters

CODE = {letter: code for code, letter in LETTERS.items()}
SPACE, LSHIFT = 57, 42


def type_text(target, text, start=0.0, interval=0.12, hold=0.08):
    """A human typing: one key at a time. Returns every outcome seen."""
    outcomes, now = [], start
    for char in text:
        code = SPACE if char == " " else CODE[char]
        outcomes.append(target.feed(code, 1, now))
        outcomes.append(target.feed(code, 0, now + hold))
        now += interval
    return [o for o in outcomes if o]


def land(target, letters, now, spread=0.0):
    """A paw: keys going down together and staying down."""
    outcomes = []
    for i, letter in enumerate(letters):
        outcomes.append(target.feed(CODE[letter], 1, now + i * spread))
    return [o for o in outcomes if o]


def lift(target, letters, now):
    for letter in letters:
        target.feed(CODE[letter], 0, now)


class LayoutTest(unittest.TestCase):
    def test_adjacency(self):
        self.assertTrue(adjacent(CODE["f"], CODE["g"]))
        self.assertTrue(adjacent(CODE["s"], CODE["w"]))
        self.assertTrue(adjacent(CODE["s"], CODE["x"]))
        self.assertTrue(adjacent(CODE["v"], SPACE))
        self.assertFalse(adjacent(CODE["a"], CODE["d"]))
        self.assertFalse(adjacent(CODE["q"], CODE["s"]))
        self.assertFalse(adjacent(CODE["d"], SPACE))
        self.assertFalse(adjacent(CODE["q"], CODE["p"]))

    def test_clusters(self):
        groups = clusters([CODE[c] for c in "fgvpo"])
        self.assertEqual(sorted(len(g) for g in groups), [2, 3])


class DetectorTest(unittest.TestCase):
    def test_normal_typing_is_fine(self):
        text = "the quick brown fox jumps over the lazy dog asdf were power"
        self.assertEqual(type_text(Detector(), text * 3), [])

    def test_fast_rollover_typing_is_fine(self):
        # 40ms between keys, each held 100ms: lots of overlap, still a human.
        text = "we were pretty sure the weather was better over there " * 3
        self.assertEqual(type_text(Detector(), text, interval=0.04, hold=0.10), [])

    def test_gaming_is_fine(self):
        detector = Detector()
        self.assertIsNone(detector.feed(LSHIFT, 1, 0.0))
        self.assertIsNone(detector.feed(CODE["w"], 1, 0.1))
        self.assertIsNone(detector.feed(CODE["d"], 1, 0.9))
        self.assertIsNone(detector.feed(SPACE, 1, 1.5))
        for step in range(40):  # held for 20 seconds
            self.assertIsNone(detector.tick(2.0 + step * 0.5))

    def test_paw_smash(self):
        self.assertEqual(land(Detector(), "fgvb", 1.0, spread=0.01), ["smash"])

    def test_single_row_roll_is_not_a_smash(self):
        detector = Detector()
        self.assertEqual(land(detector, "asdf", 1.0, spread=0.03), [])

    def test_pile_of_keys(self):
        self.assertEqual(land(Detector(), "qzpmgt", 1.0, spread=0.3), ["smash"])

    def test_loaf(self):
        detector = Detector()
        self.assertEqual(land(detector, "jkl", 1.0, spread=0.3), [])
        self.assertIsNone(detector.tick(2.0))
        self.assertEqual(detector.tick(4.0), "loaf")

    def test_loaf_seen_through_key_repeat(self):
        detector = Detector()
        land(detector, "jkl", 1.0, spread=0.3)
        self.assertEqual(detector.feed(CODE["l"], 2, 4.0), "loaf")

    def test_walk(self):
        detector = Detector()
        self.assertEqual(land(detector, "qwe", 1.0, spread=0.02), [])
        lift(detector, "qwe", 1.3)
        self.assertEqual(land(detector, "iop", 2.0, spread=0.02), ["walk"])

    def test_one_step_is_not_a_walk(self):
        detector = Detector()
        self.assertEqual(land(detector, "qwe", 1.0, spread=0.02), [])
        lift(detector, "qwe", 1.3)
        self.assertEqual(land(detector, "iop", 9.0, spread=0.02), [])

    def test_modifiers_never_count(self):
        detector = Detector()
        for code in (29, 42, 56, 125, 54, 97, 100):
            self.assertIsNone(detector.feed(code, 1, 1.0))
        self.assertIsNone(detector.tick(60.0))

    def test_sensitivity_levels(self):
        self.assertEqual(land(Detector(SENSITIVITY["low"]), "fgvb", 1.0), [])
        self.assertEqual(land(Detector(SENSITIVITY["low"]), "fgvbh", 1.0), ["smash"])
        self.assertEqual(land(Detector(SENSITIVITY["high"]), "fgv", 1.0), ["smash"])


class GuardTest(unittest.TestCase):
    def locked_guard(self):
        guard = Guard(quiet_seconds=4.0)
        self.assertEqual(land(guard, "fgvb", 1.0), ["lock"])
        return guard

    def test_unlocks_after_quiet(self):
        guard = self.locked_guard()
        self.assertIsNone(guard.tick(10.0))  # cat is still sitting on it
        lift(guard, "fgvb", 10.0)
        self.assertIsNone(guard.tick(12.0))
        self.assertEqual(guard.tick(14.0), "unlock")
        self.assertFalse(guard.locked)

    def test_key_repeat_keeps_it_locked(self):
        guard = self.locked_guard()
        guard.feed(CODE["f"], 2, 20.0)
        self.assertIsNone(guard.tick(21.0))

    def test_unlock_word(self):
        guard = self.locked_guard()
        lift(guard, "fgvb", 2.0)
        self.assertEqual(type_text(guard, "xhuman", start=3.0), ["unlock"])

    def test_wrong_word_stays_locked(self):
        guard = self.locked_guard()
        lift(guard, "fgvb", 2.0)
        self.assertEqual(type_text(guard, "hu man kitten", start=3.0), [])
        self.assertTrue(guard.locked)

    def test_no_new_lock_events_while_locked(self):
        guard = self.locked_guard()
        self.assertEqual(land(guard, "uijk", 2.0), [])

    def test_relocks_after_unlock(self):
        guard = self.locked_guard()
        lift(guard, "fgvb", 2.0)
        self.assertEqual(guard.tick(7.0), "unlock")
        self.assertEqual(land(guard, "uijk", 8.0), ["lock"])

    def test_paused(self):
        guard = Guard()
        guard.paused = True
        self.assertEqual(land(guard, "fgvb", 1.0), [])
        self.assertIsNone(guard.tick(30.0))

    def test_manual_unlock(self):
        guard = self.locked_guard()
        self.assertEqual(guard.unlock(), "unlock")
        self.assertIsNone(guard.unlock())


class ConfigTest(unittest.TestCase):
    def test_defaults(self):
        config = config_mod.load([])
        self.assertEqual(config.sensitivity, "medium")
        self.assertEqual(config.unlock_word, "human")

    def test_shipped_config_parses(self):
        shipped = Path(__file__).parent.parent / "packages/catkeys/files/catkeys.conf"
        self.assertEqual(config_mod.load([shipped]), config_mod.Config())

    def test_bad_sensitivity(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".conf") as handle:
            handle.write("[catkeys]\nsensitivity = feral\n")
            handle.flush()
            with self.assertRaises(ValueError):
                config_mod.load([handle.name])


if __name__ == "__main__":
    unittest.main()
