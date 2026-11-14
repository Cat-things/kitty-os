"""Terminal art helpers."""

import os
import sys
import textwrap

CAT = r"""
 /\_/\
( o.o )
 > ^ <
""".strip("\n")

SLEEPING_CAT = r"""
      |\      _,,,---,,_
ZZZzz /,`.-'`'    -.  ;-;;,_
     |,4-  ) )-,_. ,\ (  `'-'
    '---''(_/--'  `-'\_)
""".strip("\n")


def use_color(stream=None):
    stream = stream or sys.stdout
    return stream.isatty() and "NO_COLOR" not in os.environ


def paint(text, hex_color, bold=False):
    """Colour text with a #rrggbb colour when writing to a terminal."""
    if not use_color():
        return text
    value = hex_color.lstrip("#")
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return text
    return f"\033[{'1;' if bold else ''}38;2;{r};{g};{b}m{text}\033[0m"


def bubble(text, width=40):
    lines = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width) or [""])
    size = max(len(line) for line in lines)
    out = [" " + "_" * (size + 2)]
    if len(lines) == 1:
        out.append(f"< {lines[0].ljust(size)} >")
    else:
        for i, line in enumerate(lines):
            left, right = ("/", "\\") if i == 0 else ("\\", "/") if i == len(lines) - 1 else ("|", "|")
            out.append(f"{left} {line.ljust(size)} {right}")
    out.append(" " + "-" * (size + 2))
    return "\n".join(out)


def catsay(text, cat=CAT):
    tail = "    \\\n     \\"
    body = "\n".join("      " + line for line in cat.splitlines())
    return f"{bubble(text)}\n{tail}\n{body}"
