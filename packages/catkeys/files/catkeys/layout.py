"""Physical keyboard geometry, keyed by Linux evdev key codes.

Cats do not type words, they land paws. A paw covers a blob of physically
neighbouring keys, so the detector needs to know which keys touch each other.
Key codes are the layout-independent scancodes from linux/input-event-codes.h,
which means this works the same on QWERTY, AZERTY, Dvorak and friends.
"""

# (row, x position of the key centre in key widths, key codes left to right)
_ROWS = (
    (0, 0.0, (41, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)),   # ` 1 .. 0 - =
    (1, 1.5, (16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27)),  # q .. p [ ]
    (2, 1.75, (30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40)),   # a .. l ; '
    (3, 2.25, (44, 45, 46, 47, 48, 49, 50, 51, 52, 53)),       # z .. m , . /
)

KEY_SPACE = 57
_SPACE_ROW = 4
_SPACE_SPAN = (3.5, 10.5)

# Keys humans legitimately hold for a long time or chord with everything.
MODIFIERS = frozenset({29, 42, 54, 56, 58, 97, 100, 125, 126})

# code -> (row, x)
POSITIONS = {}
for _row, _x0, _codes in _ROWS:
    for _i, _code in enumerate(_codes):
        POSITIONS[_code] = (_row, _x0 + _i)
POSITIONS[KEY_SPACE] = (_SPACE_ROW, 7.0)

# Letters by key code (US names), used only to recognise the unlock word.
LETTERS = dict(zip(
    (16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
     30, 31, 32, 33, 34, 35, 36, 37, 38,
     44, 45, 46, 47, 48, 49, 50),
    "qwertyuiopasdfghjklzxcvbnm",
))


def adjacent(a, b):
    """True when keys a and b physically touch."""
    if a == b or a not in POSITIONS or b not in POSITIONS:
        return False
    if KEY_SPACE in (a, b):
        other = b if a == KEY_SPACE else a
        row, x = POSITIONS[other]
        return row == 3 and _SPACE_SPAN[0] <= x <= _SPACE_SPAN[1]
    (row_a, x_a), (row_b, x_b) = POSITIONS[a], POSITIONS[b]
    if row_a == row_b:
        return abs(x_a - x_b) <= 1.0
    if abs(row_a - row_b) == 1:
        return abs(x_a - x_b) < 1.0
    return False


def clusters(codes):
    """Split key codes into groups of physically connected keys."""
    remaining = {c for c in codes if c in POSITIONS}
    groups = []
    while remaining:
        stack = [remaining.pop()]
        group = set(stack)
        while stack:
            current = stack.pop()
            touching = {c for c in remaining if adjacent(current, c)}
            remaining -= touching
            group |= touching
            stack.extend(touching)
        groups.append(group)
    return groups


def rows_spanned(codes):
    return len({POSITIONS[c][0] for c in codes if c in POSITIONS})
