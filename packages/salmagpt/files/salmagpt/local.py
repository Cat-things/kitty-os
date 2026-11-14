"""The built-in SalmaGPT model.

It runs on your own machine through Ollama, so it costs nothing and nothing
you type leaves the computer. Under the hood it is an open-weights coding
model (Qwen2.5-Coder, Apache 2.0) with SalmaGPT's settings on top; setup
picks a size that fits your memory and downloads it once.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

MODEL = "salmagpt"
# (minimum GiB of memory, base model, download size)
BASES = (
    (12, "qwen2.5-coder:7b", "4.7 GB"),
    (0, "qwen2.5-coder:1.5b", "1 GB"),
)

MODELFILE = """FROM {base}
PARAMETER num_ctx 8192
PARAMETER temperature 0.2
SYSTEM You are SalmaGPT, a coding assistant that runs locally on the user's computer.
"""


class LocalError(Exception):
    pass


def ollama_url():
    host = os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434"
    if "://" not in host:
        host = "http://" + host
    return host.rstrip("/")


def _get(path, timeout=3):
    with urllib.request.urlopen(ollama_url() + path, timeout=timeout) as response:
        return json.load(response)


def server_running():
    try:
        _get("/api/version")
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def installed():
    return shutil.which("ollama") is not None


def model_ready():
    try:
        names = [item.get("name", "") for item in _get("/api/tags").get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return any(name.split(":")[0] == MODEL for name in names)


def start_server(wait=20):
    """Start Ollama in the background if it is not already running."""
    if server_running():
        return
    if not installed():
        raise LocalError("Ollama is not installed. Install it with: sudo pacman -S ollama")
    subprocess.Popen(["ollama", "serve"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if server_running():
            return
        time.sleep(0.3)
    raise LocalError("Ollama did not start. Try running 'ollama serve' in another terminal.")


def memory_gib():
    try:
        with open("/proc/meminfo") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 / 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def pick_base(memory=None):
    override = os.environ.get("SALMAGPT_BASE_MODEL")
    if override:
        return override, "unknown size"
    memory = memory_gib() if memory is None else memory
    for minimum, base, size in BASES:
        if memory >= minimum:
            return base, size
    return BASES[-1][1:]


def setup(base=None, say=print):
    """Download the weights and create the salmagpt model. Safe to re-run."""
    start_server()
    size = ""
    if base is None:
        base, size = pick_base()
    say(f"Downloading {base}{f' ({size})' if size else ''}. This happens once.")
    if subprocess.run(["ollama", "pull", base]).returncode != 0:
        raise LocalError(f"could not download {base}. Check your internet connection.")
    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False) as handle:
        handle.write(MODELFILE.format(base=base))
    try:
        done = subprocess.run(["ollama", "create", MODEL, "-f", handle.name],
                              capture_output=True, text=True)
    finally:
        os.unlink(handle.name)
    if done.returncode != 0:
        raise LocalError(f"could not create the model: {done.stderr.strip()[-300:]}")
    say("The SalmaGPT model is ready.")


def ensure_ready():
    """Called before chatting with the built-in model."""
    if not installed() and not server_running():
        raise LocalError("The built-in model needs Ollama: sudo pacman -S ollama, "
                         "then run /setup")
    start_server()
    if not model_ready():
        raise LocalError("The built-in model is not downloaded yet. Run /setup "
                         "(one-time download).")
