# kitty-os

```
 /\_/\
( o.o )  a Linux distro for people who live with cats
 > ^ <
```

kitty-os is an Arch-based distro with a riced sway desktop, a cat keyboard
detector, its own package repository, and cat modes: a general **cat mode**
that is on by default, and **Salma mode**, which is about one cat in particular.

| | |
|---|---|
| ![cat mode wallpaper](packages/kitty-os-rice/files/wallpapers/cat.png) | ![Salma mode wallpaper](packages/kitty-os-rice/files/wallpapers/salma.png) |
| cat mode (default) | Salma mode |

## What you get

- **Base:** Arch Linux. Rolling, pacman, the AUR, the Arch wiki all apply.
- **Desktop:** sway with gaps, a floating pill-style waybar, the kitty
  terminal with fish, fuzzel launcher, mako notifications, swaylock, starship
  prompt and fastfetch, all in Catppuccin Mocha with an accent colour that follows the
  cat mode.
- **catkeys:** notices when a cat is on the keyboard and locks it.
- **Cat modes:** switch what the whole desktop is about with one command.
- **SalmaGPT:** a coding assistant in your terminal, with a built-in model that
  runs on your own hardware.
- **`[kitty-os]` repository:** everything above is ordinary pacman packages.

## Get it

**ISO.** Download `kitty-os-*.iso` from the
[`iso` release](https://github.com/cat-things/kitty-os/releases/tag/iso), write
it to a USB stick and boot it. You land in the desktop as the live user. To
install to disk, open a terminal (`Super+Return`) and run:

```bash
sudo archinstall
```

When archinstall finishes and asks whether to chroot into the new system, say
no, then:

```bash
sudo kittyfy /mnt
```

**Already on Arch?** Turn the install you have into kitty-os:

```bash
curl -fsSLO https://raw.githubusercontent.com/cat-things/kitty-os/HEAD/scripts/kittyfy
```

```bash
sudo bash kittyfy
```

Log in on the first console (tty1) and the desktop starts. (Don't want that?
`touch ~/.config/kitty-os/no-autostart`.)

CI rebuilds the ISO and the package repository on every push to the default
branch and publishes them as the `iso` and `repo` releases.

## Keys

| Keys | What |
|---|---|
| `Super+Return` | terminal |
| `Super+D` | app launcher |
| `Super+B` / `Super+E` | browser / files |
| `Super+Shift+M` | next cat mode |
| `Super+C` | cat fact |
| `Super+G` | SalmaGPT |
| `Super+U` / `Super+Shift+U` | unlock keyboard / pause cat detection |
| `Super+Shift+S` / `Print` | screenshot of a region / everything |
| `Super+Escape` | lock screen |
| `Super+Shift+Q` | close window |
| `Super+Shift+E` | log out, reboot, power off |
| `Super+1…9` | workspaces (`Shift` moves the window there) |

Salma mode adds `Super+P` (open The Salma Files), `Super+Shift+P` (random
Salma picture as wallpaper) and `Super+M` (call her).

## catkeys, the cat keyboard detector

catkeys watches your keyboards and looks for things only a cat does:

| | What it sees |
|---|---|
| **smash** | several touching keys going down at the same instant across rows: a paw, or a whole cat, landing |
| **loaf** | a group of touching keys staying held: the cat sat down |
| **walk** | paw-sized blobs of keys landing one after another |

When it sees one, the keyboard stops reaching your programs and you get a
notification. It unlocks by itself a few seconds after the cat leaves, or
right away when you type `human`, click the keyboard icon in the bar, or press
`Super+U` on a keyboard the cat is not on.

```bash
catkeys status     # what it is doing
catkeys test       # lock and unlock once, to see it work
catkeys pause      # pause / resume, for games
catkeys stats      # how many cats it has caught
```

Settings live in `/etc/catkeys.conf` (or `~/.config/catkeys/catkeys.conf`):
sensitivity (`low`, `medium`, `high`), the unlock word, and the lock commands.
Locking works out of the box on sway; on other compositors set `lock_command`
and `unlock_command`, or leave them empty to only get the notification.

Good to know: catkeys reads key events from `/dev/input`, which needs your
user in the `input` group (`kittyfy` does this). It only looks at which keys
are down and never stores or sends what you type. Modifier keys are ignored,
and normal typing and gaming do not trigger it, but if it ever does:
`catkeys pause`.

## Cat modes

```bash
catmode            # which mode is on
catmode list
catmode salma      # switch (also: catmode cat, catmode next)
```

A mode changes the accent colour, wallpaper, cat facts, terminal greeting, bar
badge, catkeys messages and can add its own key bindings.

**Cat mode** (default) is about cats in general:

```bash
catfact            # a cat fact (-s lets a cat say it)
catsay hello       # a cat says things
pspsps             # call a cat. results not guaranteed
```

**Salma mode** is about Salma:

```bash
meo-meo-meow       # call her by the name she answers to
salma              # how she is doing
salma feed         # croquettes only; try 'salma feed tuna'
salma play wand    # the wand toy with the bird wings (or: flower)
salma couch        # which toys ended up under the couch (--rescue gets them)
salma files        # open "The Salma Files" (add, random, wallpaper, count)
```

"The Salma Files" is a folder in your pictures directory. Pictures stay on
your machine; nothing in this repository contains any.

### Make a mode for your own cat

Copy a mode and edit it:

```bash
mkdir -p ~/.local/share/kitty-os/modes
```

```bash
cp -r /usr/share/kitty-os/modes/cat ~/.local/share/kitty-os/modes/mycat
```

Then change `mode.conf` (name, icon, accent colour), `facts.txt`,
`catkeys.txt`, `greeting.txt` and the colour in `sway.conf`, `kitty.conf` and
`waybar.css`, and switch to it with `catmode mycat`.

## SalmaGPT

A coding assistant that lives in your terminal (`Super+G`, or run `salmagpt`).
You talk to it, and it reads, searches, edits and runs things in the directory
you started it in. Every file change and command is shown to you first; answer
`y`, `a` (always, for this session), `n`, or just type what it should do instead.

```bash
salmagpt                     # chat
salmagpt -p "why does the build fail?"    # one answer, then exit
salmagpt --yolo              # never ask before changing files or running commands
```

**The built-in model** is called `salmagpt` and is free forever because it runs
on your own hardware: no account, no key, and nothing you type leaves the
machine. Get it once with `/setup` (or `salmagpt setup`). What that does: it
downloads an open-weights coding model (Qwen2.5-Coder, Apache 2.0) through
[Ollama](https://ollama.com) and gives it SalmaGPT's settings. Setup picks the
7B model (4.7 GB) on machines with 12 GB of memory or more and the 1.5B model
(1 GB) otherwise; set `SALMAGPT_BASE_MODEL` to choose another. A local model of
this size is slower and makes more mistakes than the big hosted ones,
especially without a GPU, so check its work.

**Connect more AIs** with `/connect`: Claude (Anthropic), OpenAI, OpenRouter,
Groq, or any OpenAI-compatible server such as llama.cpp, LM Studio or another
Ollama. Switch between them mid-conversation with `/model`, and the
conversation carries over.

| Command | What |
|---|---|
| `/connect` | add an AI: pick the service, paste a key (or use an environment variable), pick models |
| `/models`, `/model NAME` | list models, switch model |
| `/setup` | download or update the built-in model |
| `/yolo` | toggle approving everything automatically |
| `/clear` | new conversation |
| `/disconnect NAME` | remove a connection |

Keys you paste are stored in `~/.config/salmagpt/config.json`, readable only by
you. Claude needs the Anthropic Python SDK (`pip install anthropic`). Hosted models are billed by
whoever runs them; only the built-in one is free.

## The package repository

```ini
[kitty-os]
SigLevel = Optional TrustAll
Server = https://github.com/cat-things/kitty-os/releases/download/repo
```

| Package | What |
|---|---|
| `kitty-os-desktop` | everything; install this one |
| `catkeys` | the cat keyboard detector (works on any Arch system) |
| `salmagpt` | the coding assistant (works on any Arch system) |
| `kitty-os-modes` | `catmode`, `catfact`, `catsay`, `pspsps`, cat mode |
| `kitty-os-salma-mode` | Salma mode |
| `kitty-os-rice` | desktop configs and wallpapers |
| `kitty-os-release` | distro identity and repository setup |

The packages are not signed yet, which is why the repository uses
`SigLevel = Optional TrustAll`.

## Build it yourself

On Arch:

```bash
sudo pacman -S --needed base-devel archiso
```

```bash
scripts/build-repo.sh
```

```bash
sudo iso/build.sh
```

The packages land in `out/repo`, the ISO in `out/iso`. The ISO is the
official Arch `releng` live medium with `iso/overlay` and `iso/packages.x86_64`
on top, so it keeps every Arch install tool.

Tests need only Python:

```bash
python3 -m unittest discover -s tests
```

## Layout

```
packages/   one directory per package: PKGBUILD + files/
iso/        ISO build script, overlay and package list
scripts/    build-repo.sh, kittyfy (installer), make-wallpapers.py
tests/      unit tests for catkeys, the modes, Salma mode and SalmaGPT
```

## Licence

MIT. Colours are from the [Catppuccin](https://github.com/catppuccin/catppuccin)
Mocha palette.
