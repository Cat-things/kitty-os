#!/usr/bin/env python3
"""Draws the kitty-os wallpapers as SVG.

    scripts/make-wallpapers.py
    rsvg-convert -o cat.png cat.svg      # or any other SVG renderer

The PNGs next to the SVGs are what the desktop uses.
"""

import random
from pathlib import Path

OUT = Path(__file__).parent.parent / "packages/kitty-os-rice/files/wallpapers"
W, H = 2560, 1440
CRUST, MANTLE, BASE, SURFACE = "#11111b", "#181825", "#1e1e2e", "#313244"


def stars(seed, count=170):
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        x, y = rng.uniform(0, W), rng.uniform(0, H * 0.72)
        r = rng.choice((1.2, 1.5, 1.5, 2.0, 2.6))
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#cdd6f4" '
                   f'opacity="{rng.uniform(0.25, 0.9):.2f}"/>')
    return "\n".join(out)


def cat(x, y, scale=1.0, fill=CRUST):
    """A cat sitting with its back to us. (x, y) is where it sits."""
    return f'''<g transform="translate({x} {y}) scale({scale})" fill="{fill}">
  <path d="M -95 0 C -120 -150 -70 -250 0 -250 C 70 -250 120 -150 95 0 Z"/>
  <circle cx="0" cy="-285" r="72"/>
  <path d="M -68 -310 L -62 -392 L -8 -345 Z"/>
  <path d="M 68 -310 L 62 -392 L 8 -345 Z"/>
  <path d="M 70 -20 C 190 -10 250 -60 228 -128 C 222 -146 196 -140 202 -122
           C 214 -84 170 -52 80 -58 Z"/>
</g>'''


def page(accent, glow, seed, scene):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{CRUST}"/>
    <stop offset="0.6" stop-color="{BASE}"/>
    <stop offset="1" stop-color="{glow}"/>
  </linearGradient>
  <radialGradient id="halo">
    <stop offset="0.35" stop-color="{accent}" stop-opacity="0.35"/>
    <stop offset="1" stop-color="{accent}" stop-opacity="0"/>
  </radialGradient>
</defs>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
{stars(seed)}
{scene}
</svg>
'''


def moon(x, y, r, accent):
    return f'''<circle cx="{x}" cy="{y}" r="{r * 2.3}" fill="url(#halo)"/>
<circle cx="{x}" cy="{y}" r="{r}" fill="{accent}"/>
<circle cx="{x - r * 0.3}" cy="{y - r * 0.25}" r="{r * 0.16}" fill="#000" opacity="0.07"/>
<circle cx="{x + r * 0.35}" cy="{y + r * 0.2}" r="{r * 0.22}" fill="#000" opacity="0.07"/>
<circle cx="{x - r * 0.1}" cy="{y + r * 0.5}" r="{r * 0.1}" fill="#000" opacity="0.07"/>'''


def cat_scene():
    accent = "#cba6f7"
    hills = f'''<path d="M 0 1180 C 500 1040 900 1120 1300 1170 C 1700 1220 2200 1080 {W} 1150 L {W} {H} L 0 {H} Z" fill="{SURFACE}"/>
<path d="M 0 1300 C 600 1180 1200 1130 1790 1150 C 2100 1160 2400 1230 {W} 1290 L {W} {H} L 0 {H} Z" fill="{MANTLE}"/>'''
    return page(accent, "#3b2f5c", 7,
                f'{moon(1790, 760, 300, accent)}\n{hills}\n{cat(1790, 1160, 1.15)}')


def salma_scene():
    accent = "#fab387"
    floor = f'<rect x="0" y="1290" width="{W}" height="150" fill="{MANTLE}"/>'
    # The cat tree: post, base and the platform she sits on.
    tree = f'''<g fill="{CRUST}">
  <rect x="1740" y="930" width="100" height="370" rx="14"/>
  <rect x="1560" y="900" width="460" height="46" rx="23"/>
  <rect x="1620" y="1262" width="340" height="40" rx="16"/>
</g>
<g stroke="{SURFACE}" stroke-width="5" opacity="0.8">
  {"".join(f'<line x1="1740" y1="{y}" x2="1840" y2="{y - 16}"/>' for y in range(985, 1260, 26))}
</g>'''
    # The wand toy with the bird wings, dangling just out of reach.
    wand = f'''<g fill="none" stroke="{CRUST}" stroke-linecap="round">
  <path d="M 820 1290 L 1250 520" stroke-width="12"/>
  <path d="M 1250 520 C 1330 560 1380 640 1392 760" stroke-width="4" stroke="{SURFACE}"/>
</g>
<g transform="translate(1392 775)" fill="{accent}">
  <path d="M 0 0 C -70 -70 -130 -40 -150 10 C -100 0 -50 20 0 14 Z"/>
  <path d="M 0 0 C 70 -70 130 -40 150 10 C 100 0 50 20 0 14 Z"/>
  <ellipse cx="0" cy="12" rx="20" ry="28" fill="{CRUST}"/>
</g>'''
    # The crochet flower, left on the floor.
    petals = "".join(
        f'<circle cx="{38 * __import__("math").cos(a * 1.0472):.1f}" '
        f'cy="{38 * __import__("math").sin(a * 1.0472):.1f}" r="26"/>' for a in range(6))
    flower = f'''<g transform="translate(600 1262)">
  <g fill="{accent}" opacity="0.75">{petals}</g>
  <circle r="20" fill="#f9e2af" opacity="0.85"/>
</g>'''
    return page(accent, "#4a3327", 21,
                f'{moon(1790, 560, 270, accent)}\n{floor}\n{tree}\n{wand}\n{flower}\n{cat(1790, 902, 0.95)}')


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cat.svg").write_text(cat_scene())
    (OUT / "salma.svg").write_text(salma_scene())
    print(f"wrote {OUT}/cat.svg and salma.svg")
