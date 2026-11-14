"""The tools the model can use to work on your code."""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_OUTPUT = 30_000
MAX_READ_LINES = 2000
MAX_MATCHES = 200
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "target",
             "dist", "build", ".cache"}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict   # JSON schema
    function: callable
    needs_approval: bool = False

    def summary(self, args):
        """One line describing a call, for the screen."""
        first = next(iter(self.parameters["properties"]), None)
        value = str(args.get(first, "")) if first else ""
        value = value.replace("\n", " ")
        return f"{self.name}({value[:80]}{'…' if len(value) > 80 else ''})"


class ToolError(Exception):
    """Something the model should be told about and can react to."""


def clip(text, limit=MAX_OUTPUT):
    if len(text) <= limit:
        return text
    head, tail = text[: limit // 4], text[-(limit * 3 // 4):]
    dropped = len(text) - len(head) - len(tail)
    return f"{head}\n[... {dropped} characters left out ...]\n{tail}"


def _path(value):
    return Path(os.path.expanduser(value))


def read_file(path, offset=1, limit=MAX_READ_LINES):
    target = _path(path)
    try:
        text = target.read_text(errors="replace")
    except IsADirectoryError:
        raise ToolError(f"{path} is a directory; use list_dir") from None
    except OSError as error:
        raise ToolError(f"cannot read {path}: {error.strerror}") from None
    lines = text.splitlines()
    offset, limit = max(int(offset), 1), max(int(limit), 1)
    chunk = lines[offset - 1: offset - 1 + limit]
    if not lines:
        return "(empty file)"
    if not chunk:
        raise ToolError(f"{path} has only {len(lines)} lines")
    body = "\n".join(f"{offset + i:>5}  {line}" for i, line in enumerate(chunk))
    last = offset + len(chunk) - 1
    if last < len(lines):
        body += f"\n[showing lines {offset}-{last} of {len(lines)}; pass offset to read more]"
    return clip(body)


def write_file(path, content):
    target = _path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_text(content)
    except OSError as error:
        raise ToolError(f"cannot write {path}: {error.strerror}") from None
    return f"{'Overwrote' if existed else 'Created'} {path} ({len(content.splitlines())} lines)"


def edit_file(path, old_text, new_text, replace_all=False):
    target = _path(path)
    try:
        text = target.read_text()
    except OSError as error:
        raise ToolError(f"cannot read {path}: {error.strerror}") from None
    if not old_text:
        raise ToolError("old_text is empty; use write_file to create a file")
    count = text.count(old_text)
    if count == 0:
        raise ToolError(f"old_text was not found in {path}. Read the file and copy "
                        "the text exactly, including indentation.")
    if count > 1 and not replace_all:
        raise ToolError(f"old_text appears {count} times in {path}. Add surrounding "
                        "lines to make it unique, or set replace_all.")
    target.write_text(text.replace(old_text, new_text) if replace_all
                      else text.replace(old_text, new_text, 1))
    return f"Edited {path} ({count if replace_all else 1} replacement(s))"


def list_dir(path="."):
    target = _path(path)
    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as error:
        raise ToolError(f"cannot list {path}: {error.strerror}") from None
    if not entries:
        return "(empty directory)"
    lines = [f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries[:500]]
    if len(entries) > 500:
        lines.append(f"[... and {len(entries) - 500} more]")
    return "\n".join(lines)


def search(pattern, path=".", glob="*"):
    try:
        regex = re.compile(pattern)
    except re.error as error:
        raise ToolError(f"bad regular expression: {error}") from None
    root = _path(path)
    if not root.exists():
        raise ToolError(f"{path} does not exist")
    files = [root] if root.is_file() else _walk(root, glob)
    matches = []
    for file in files:
        try:
            with open(file, errors="strict") as handle:
                for number, line in enumerate(handle, 1):
                    if regex.search(line):
                        matches.append(f"{file}:{number}: {line.rstrip()[:300]}")
                        if len(matches) >= MAX_MATCHES:
                            matches.append(f"[stopped at {MAX_MATCHES} matches; narrow the search]")
                            return "\n".join(matches)
        except (OSError, UnicodeDecodeError):
            continue  # unreadable or binary
    return "\n".join(matches) if matches else "No matches."


def _walk(root, glob):
    for directory, subdirs, names in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if d not in SKIP_DIRS)
        for name in sorted(names):
            path = Path(directory) / name
            if path.match(glob):
                yield path


def run_command(command, timeout=120):
    try:
        done = subprocess.run(command, shell=True, capture_output=True, text=True,
                              errors="replace", timeout=min(max(int(timeout), 1), 600),
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise ToolError(f"the command was stopped after {timeout} seconds") from None
    output = (done.stdout + done.stderr).strip() or "(no output)"
    return clip(f"{output}\n[exit code {done.returncode}]")


def _schema(properties, required):
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


_STR = {"type": "string"}

TOOLS = [
    Tool("read_file", "Read a text file. Lines come back numbered.",
         _schema({"path": _STR,
                  "offset": {"type": "integer", "description": "First line to read, from 1."},
                  "limit": {"type": "integer", "description": "How many lines to read."}},
                 ["path"]), read_file),
    Tool("list_dir", "List the files and directories in a directory.",
         _schema({"path": {"type": "string", "description": "Defaults to the working directory."}},
                 []), list_dir),
    Tool("search", "Search file contents with a regular expression. Returns file:line: text.",
         _schema({"pattern": _STR,
                  "path": {"type": "string", "description": "File or directory to search. Default: ."},
                  "glob": {"type": "string", "description": "Only files matching this, e.g. *.py"}},
                 ["pattern"]), search),
    Tool("write_file", "Create a file or replace its whole contents.",
         _schema({"path": _STR, "content": _STR}, ["path", "content"]),
         write_file, needs_approval=True),
    Tool("edit_file", "Replace an exact piece of text in a file. old_text must match "
         "the file exactly and be unique unless replace_all is set.",
         _schema({"path": _STR, "old_text": _STR, "new_text": _STR,
                  "replace_all": {"type": "boolean"}},
                 ["path", "old_text", "new_text"]), edit_file, needs_approval=True),
    Tool("run_command", "Run a shell command in the working directory and return its "
         "output and exit code. Not interactive: commands cannot ask for input.",
         _schema({"command": _STR,
                  "timeout": {"type": "integer", "description": "Seconds, default 120."}},
                 ["command"]), run_command, needs_approval=True),
]

_TYPES = {"string": str, "integer": int, "boolean": bool}


def call(tool, args):
    """Check the arguments against the schema, then run the tool."""
    if not isinstance(args, dict):
        raise ToolError("the arguments must be a JSON object")
    properties = tool.parameters["properties"]
    for name in tool.parameters["required"]:
        if name not in args:
            raise ToolError(f"missing argument: {name}")
    for name, value in args.items():
        if name not in properties:
            raise ToolError(f"unknown argument: {name}")
        expected = _TYPES[properties[name]["type"]]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise ToolError(f"argument {name} must be a {properties[name]['type']}")
    return tool.function(**args)
