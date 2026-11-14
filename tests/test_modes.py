import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "packages/kitty-os-modes/files"))
sys.path.insert(0, str(ROOT / "packages/kitty-os-salma-mode/files"))

import salma
from kittyos import cli, modes

MODE_FILES = ("mode.conf", "facts.txt", "catkeys.txt", "greeting.txt",
              "sway.conf", "kitty.conf", "waybar.css")


def run(function, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = function(list(argv))
    return code, out.getvalue(), err.getvalue()


class SandboxTest(unittest.TestCase):
    """Runs with a throwaway home and both shipped modes installed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        installed = self.tmp / "modes"
        shutil.copytree(ROOT / "packages/kitty-os-modes/files/modes/cat", installed / "cat")
        shutil.copytree(ROOT / "packages/kitty-os-salma-mode/files/mode", installed / "salma")
        env = {
            "HOME": str(self.tmp / "home"),
            "KITTY_OS_MODES_DIR": str(installed),
            "XDG_CONFIG_HOME": str(self.tmp / "config"),
            "XDG_STATE_HOME": str(self.tmp / "state"),
            "XDG_PICTURES_DIR": str(self.tmp / "Pictures"),
            "PATH": os.environ["PATH"],
        }
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)


class ModesTest(SandboxTest):
    def test_shipped_modes_are_complete(self):
        available = modes.available()
        self.assertEqual(list(available), ["cat", "salma"])
        for mode in available.values():
            for name in MODE_FILES:
                self.assertTrue((mode.path / name).is_file(), f"{mode.name}/{name}")
            self.assertRegex(mode.accent, r"^#[0-9a-f]{6}$")
            self.assertGreaterEqual(len(mode.lines("facts.txt")), 5)
            self.assertTrue(mode.lines("catkeys.txt"))
            self.assertIn(mode.accent, mode.text("sway.conf"))
            self.assertIn(mode.accent, mode.text("kitty.conf"))
            self.assertIn(mode.accent, mode.text("waybar.css"))

    def test_cat_mode_is_the_default(self):
        self.assertEqual(modes.current_name(), "cat")
        self.assertEqual(run(cli.catmode)[1].splitlines()[0], "🐱 cat - Cat mode")

    def test_switching(self):
        code, out, _ = run(cli.catmode, "salma", "--no-apply")
        self.assertEqual((code, out), (0, "🧡 Salma mode\n"))
        self.assertEqual(modes.current_name(), "salma")
        link = modes.config_dir() / "current"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (self.tmp / "modes/salma").resolve())
        run(cli.catmode, "set", "cat", "--no-apply")
        self.assertEqual(link.resolve(), (self.tmp / "modes/cat").resolve())

    def test_next_cycles(self):
        run(cli.catmode, "next", "--no-apply")
        self.assertEqual(modes.current_name(), "salma")
        run(cli.catmode, "next", "--no-apply")
        self.assertEqual(modes.current_name(), "cat")

    def test_unknown_mode(self):
        code, _, err = run(cli.catmode, "dog", "--no-apply")
        self.assertEqual(code, 1)
        self.assertIn("no such mode: dog", err)
        self.assertEqual(modes.current_name(), "cat")

    def test_removed_mode_falls_back_to_default(self):
        run(cli.catmode, "salma", "--no-apply")
        shutil.rmtree(self.tmp / "modes/salma")
        self.assertEqual(modes.current_name(), "cat")

    def test_waybar_json(self):
        data = json.loads(run(cli.catmode, "waybar")[1])
        self.assertEqual((data["text"], data["class"]), ("🐱 cat", "cat"))

    def test_catfact_follows_the_mode(self):
        self.assertIn(run(cli.catfact)[1].strip(), modes.get("cat").lines("facts.txt"))
        run(cli.catmode, "salma", "--no-apply")
        self.assertIn(run(cli.catfact)[1].strip(), modes.get("salma").lines("facts.txt"))
        self.assertEqual(len(run(cli.catfact, "--all", "-m", "cat")[1].splitlines()),
                         len(modes.get("cat").lines("facts.txt")))

    def test_catsay(self):
        out = run(cli.catsay, "hi")[1]
        self.assertIn("< hi >", out)
        self.assertIn("( o.o )", out)


class SalmaTest(SandboxTest):
    def test_answers_to_her_name_only(self):
        self.assertEqual(run(salma.main, "call")[0], 0)
        self.assertEqual(run(salma.main, "call", "meo-meo-meow")[0], 0)
        self.assertEqual(run(salma.name_call)[0], 0)
        code, out, _ = run(salma.main, "call", "kitty")
        self.assertEqual(code, 1)
        self.assertIn("does not answer", out)

    def test_croquettes_only(self):
        code, out, _ = run(salma.main, "feed")
        self.assertEqual(code, 0)
        self.assertIn("Croquettes served (1 bowls", out)
        for food in ("tuna", "pâté", "pate", "Tuna"):
            code, out, _ = run(salma.main, "feed", food)
            self.assertEqual(code, 1, food)
            self.assertIn("makes her sick", out)
        self.assertEqual(run(salma.main, "feed", "salmon")[0], 1)

    def test_toys_end_up_under_the_couch(self):
        with mock.patch("salma.random.random", return_value=0.0):
            self.assertEqual(run(salma.main, "play", "wand")[0], 0)
        self.assertIn("bird wings", run(salma.main, "couch")[1])
        self.assertEqual(run(salma.main, "play", "wand")[0], 1)
        with mock.patch("salma.random.random", return_value=0.9):
            code, out, _ = run(salma.main, "play")  # picks the toy that is left
        self.assertEqual(code, 0)
        self.assertIn("crochet flower", out)
        self.assertIn("Rescued", run(salma.main, "couch", "--rescue")[1])
        self.assertIn("Nothing under the couch", run(salma.main, "couch")[1])

    def test_the_salma_files(self):
        folder = self.tmp / "Pictures" / "The Salma Files"
        self.assertEqual(run(salma.main, "files", "path")[1].strip(), str(folder))
        self.assertTrue(folder.is_dir())
        picture = self.tmp / "nap.jpg"
        picture.write_bytes(b"jpeg")
        (self.tmp / "notes.txt").write_text("not a picture")
        run(salma.main, "files", "add", str(picture), str(self.tmp / "notes.txt"))
        run(salma.main, "files", "add", str(picture))  # same name: kept, not overwritten
        self.assertEqual(run(salma.main, "files", "count")[1].strip(), "2")
        self.assertEqual(sorted(p.name for p in salma.pictures()), ["nap-1.jpg", "nap.jpg"])
        self.assertEqual(run(salma.main, "files", "random")[0], 0)

    def test_status(self):
        code, out, _ = run(salma.main)
        self.assertEqual(code, 0)
        self.assertIn("croquettes only", out)
        self.assertIn("Salma mode is off", out)

    def test_animation_frames_are_even(self):
        for frames in (salma._wand_frames(), salma._flower_frames()):
            self.assertEqual(len({frame.count("\n") for frame in frames}), 1)


if __name__ == "__main__":
    unittest.main()
