#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veleho -- projectile / effect / item / UI / logo / bitmap-font art generator.

Every image is built either from the ASCII grids in this file ('.' = transparent,
other characters looked up in a per-asset palette dict) or from small procedural
drawing routines (explosion, slash, portal, drill, logo).  Output is crisp pixel
art: alpha is always exactly 0 or 255.  Everything is deterministic.

Writes (relative to the project root):
  assets/sprites/projectiles.png   48x156  12x12 cells, 4 frames x 13 projectile kinds
  assets/sprites/explosion.png    256x32   8 frames of 32x32
  assets/sprites/slash.png        128x32   4 frames of 32x32
  assets/sprites/portal.png       192x32   8 frames of 24x32
  assets/sprites/fx_small.png      32x24   8x8 cells, 4 cols x 3 rows
  assets/sprites/items.png         48x48   12x12 cells, 4 cols x 4 rows
  assets/sprites/ui.png            96x8    12 icons of 8x8
  assets/sprites/slot.png          60x20   3 frames of 20x20
  assets/sprites/crosshair.png     11x11
  assets/sprites/logo.png         200x48
  assets/sprites/spell_icons.png  128x48   16x16 spell cards, 8 cols x 3 rows (22 used)
  assets/sprites/ui_controls.png   80x10   8 UI control graphics in 10x10 cells
  assets/sprites/panel.png         24x24   nine-slice window frame, 8 px margins
  assets/sprites/flask.png         30x24   10x12 cells: row 0 glass, row 1 liquid masks
  assets/fonts/pixel_font.png     128x84   8x12 cells, 16 per row
  assets/fonts/pixel_font_charset.txt

Usage:
  python tools/art/gen_fx_ui.py                 # write the assets
  python tools/art/gen_fx_ui.py --preview DIR   # ... and 8x previews into DIR
"""
import argparse
import math
import os
import random

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SPRITES = os.path.join(ROOT, 'assets', 'sprites')
FONTS = os.path.join(ROOT, 'assets', 'fonts')

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
WHITE = '#ffffff'
K = '#140c1c'                       # outline / darkest
D1, D2 = '#2a1e36', '#3b2d4f'       # darks
ST1, ST2, ST3, ST4 = '#3d3a45', '#5c5866', '#858091', '#b3afbd'   # stone
CY0, CY1, CY2 = '#2b8fb3', '#49e0e8', '#b8fbff'                    # cyan
FI0, FI1, FI2, FI3, FI4 = '#fff3b0', '#ffd04a', '#ff8a1f', '#d9421b', '#8c1c12'
IC0, IC1, IC2, IC3 = '#e8fbff', '#a8e4f5', '#5fb4dc', '#2f6e9e'    # ice
AC0, AC1, AC2, AC3 = '#e7ff8a', '#9be03a', '#4f9a1e', '#2d5e14'    # acid
MG0, MG1, MG2, MG3 = '#ff9ce0', '#e04fb5', '#962a7d', '#5e1a52'    # magenta
VI0, VI1, VI2, VI3 = '#d7b0ff', '#9a5cf0', '#5a2fb0', '#3a1c78'    # violet
GO0, GO1, GO2, GO3 = '#fff2a8', '#f2c14e', '#b07b1f', '#6e4a12'    # gold
WA0, WA1, WA2, WA3 = '#bfe9ff', '#4aa3df', '#22598f', '#163d66'    # water
EA0, EA1, EA2 = '#e0b070', '#a8743a', '#6b4a2a'                    # earth
CR0, CR1, CR2, CR3 = '#ff6b6b', '#c8283c', '#6b1a26', '#3a0d18'    # crimson
TE0, TE1, TE2, TE3 = '#1d3b4a', '#2a5a6b', '#3f8090', '#6fb3b8'    # teal
SLOT_FILL = '#1a1424'
STORM = '#fff27a'
SH0, SH1 = '#ff6b9a', '#ffd3e2'                                    # boss shard pink / pale core
PA0, PA1, PA2 = '#efe6d2', '#c2b59b', '#8a7a62'                    # parchment
PANEL_FILL = '#120d1a'
# spell card colours: border per element (matches Spells.ELEMENT_COLORS), tile (dark, light)
ELEM_COL = {'arcane': '#7fd8ff', 'fire': '#ff7a2a', 'ice': '#a8e4f5', 'acid': '#9be03a',
            'earth': '#e0b070', 'water': '#4aa3df', 'storm': STORM}
CARD_PROJ = ('#1c1626', '#241c30')
CARD_MOD = ('#16233f', '#1d3156')
MOD_BORDER = '#7ab8ff'

_rgb_cache = {}


def rgb(c):
    """'#rrggbb' -> (r, g, b, 255); tuples pass through."""
    if not isinstance(c, str):
        return tuple(c)
    if c not in _rgb_cache:
        h = c.lstrip('#')
        _rgb_cache[c] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    return _rgb_cache[c]


# --------------------------------------------------------------------------
# tiny image toolkit (numpy RGBA, shape = (h, w, 4))
# --------------------------------------------------------------------------
def new(w, h):
    return np.zeros((h, w, 4), np.uint8)


def put(img, x, y, col):
    h, w = img.shape[:2]
    if 0 <= x < w and 0 <= y < h and col is not None:
        img[y, x] = rgb(col)


def is_col(img, x, y, col):
    h, w = img.shape[:2]
    return 0 <= x < w and 0 <= y < h and tuple(img[y, x]) == rgb(col)


def paste(dst, src, ox, oy):
    """Copy the opaque pixels of src onto dst at (ox, oy) (clipped)."""
    sh, sw = src.shape[:2]
    dh, dw = dst.shape[:2]
    for y in range(sh):
        ty = oy + y
        if not 0 <= ty < dh:
            continue
        for x in range(sw):
            tx = ox + x
            if 0 <= tx < dw and src[y, x, 3] > 0:
                dst[ty, tx] = src[y, x]


def shifted(mask, dx, dy):
    """mask moved by (dx, dy); vacated cells False."""
    h, w = mask.shape
    out = np.zeros_like(mask)
    ys0, ys1 = max(0, dy), h + min(0, dy)
    xs0, xs1 = max(0, dx), w + min(0, dx)
    if ys1 > ys0 and xs1 > xs0:
        out[ys0:ys1, xs0:xs1] = mask[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = N4 + [(-1, -1), (1, -1), (-1, 1), (1, 1)]


def ring_of(mask, diag=True):
    """Pixels just outside mask (4- or 8-neighbourhood)."""
    nb = np.zeros_like(mask)
    for dx, dy in (N8 if diag else N4):
        nb |= shifted(mask, dx, dy)
    return nb & ~mask


def add_outline(img, col=K, diag=True):
    m = img[..., 3] > 0
    out = img.copy()
    out[ring_of(m, diag)] = rgb(col)
    return out


def grid(rows, pal):
    h = len(rows)
    w = max(len(r) for r in rows)
    img = new(w, h)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == '.':
                continue
            if ch not in pal:
                raise KeyError('unknown palette char %r in %r' % (ch, row))
            img[y, x] = rgb(pal[ch])
    return img


def frames(block, pal):
    """Parse an ASCII block holding several frames side by side (space separated)."""
    lines = [ln.split() for ln in block.strip('\n').splitlines() if ln.strip()]
    n = len(lines[0])
    for ln in lines:
        if len(ln) != n:
            raise ValueError('ragged frame block line: %r' % (ln,))
    out = [grid([ln[i] for ln in lines], pal) for i in range(n)]
    for im in out:
        if im.shape != out[0].shape:
            raise ValueError('frames of unequal size in block')
    return out


def overlay(base, *layers):
    out = base.copy()
    for lay in layers:
        paste(out, lay, 0, 0)
    return out


def finalize(img):
    """Force binary alpha and clean RGB under transparent pixels."""
    out = img.copy()
    a = out[..., 3] > 0
    out[a, 3] = 255
    out[~a] = 0
    return out


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(finalize(img), 'RGBA').save(path)


def value_noise(w, h, cell, seed):
    rng = np.random.default_rng(seed)
    gw, gh = w // cell + 3, h // cell + 3
    g = rng.random((gh, gw))
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    fx, fy = xs / cell, ys / cell
    x0, y0 = fx.astype(int), fy.astype(int)
    tx, ty = fx - x0, fy - y0
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    a = g[y0, x0]
    b = g[y0, x0 + 1]
    c = g[y0 + 1, x0]
    d = g[y0 + 1, x0 + 1]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def ellipse_mask(w, h, cx, cy, rx, ry, thr=1.0):
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    dx = (xs + 0.5 - cx) / rx
    dy = (ys + 0.5 - cy) / ry
    return dx * dx + dy * dy <= thr


# ==========================================================================
# 1. projectiles.png  (12x12 cells, 4 frames per row, 12 rows; point RIGHT)
# ==========================================================================
def proj_spark():
    pal = {'W': WHITE, 'C': CY2, 'c': CY1, 'x': CY0}
    return frames('''
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
............ .........c.. ............ ............
.......cCc.. ....x..cCc.. .......cCc.. .......cCc..
..xxccCWWWC. ...xccCWWWC. .x.xccCWWWC. x.xcccCWWWC.
.......cCc.. .......cCc.. ....x..cCc.. .......cCc..
............ ............ ........c... ............
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
''', pal)


def proj_fireball():
    pal = {'W': WHITE, 'y': FI0, 'Y': FI1, 'o': FI2, 'r': FI3, 'R': FI4}
    flames = frames('''
............ ............ ............ ............
............ ............ ............ ............
............ ....r....... ............ ............
...rro...... ..R.oo...... .Rrroo...... ....ro......
..r.oo...... .rroYo...... ...roo...... Rrrroo......
RrrYoo...... ..rroo...... .RrYoo...... ...rYo......
...roo...... Rrroo....... ..r.oo...... .Rr.oo......
.Rrro....... ...ro....... ...rro...... ..R.ro......
............ ............ ....r....... ............
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
''', pal)
    balls = frames('''
............ ............ ............ ............
............ ............ ............ ............
......oYY... ......oYY... ......oYY... ......oYY...
.....oYyyY.. .....oYyyY.. .....oYyyY.. .....oYyyY..
....oYyWWyY. ....oYyyWyY. ....oYyWWyY. ....oYyyWyY.
....oYyWWWy. ....oYyWWWy. ....oYyWWWy. ....oYWWWWy.
....rYyWWyY. ....rYyyWyY. ....rYyWWyY. ....rYyyWyY.
.....roYyY.. .....roYyY.. .....roYyY.. .....roYyY..
......roY... ......roY... ......roY... ......roY...
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
''', pal)
    return [overlay(f, b) for f, b in zip(flames, balls)]


def proj_orb():
    pal = {'W': WHITE, 'm': MG0, 'M': MG1, 'n': MG2, 'N': MG3}
    return frames('''
............ ............ ............ ............
............ ............ ............ ............
............ .....nn..... ....NNNN.... .....nn.....
....mMMM.... ....mMMM.... ...NmmMMN... ....mMMM....
...mWWMMM... ...mWWMMM... ..NmWWmMMN.. ...mWWMMM...
...MWmMMn... ..nMWmMMnn.. ..NmWmMMnN.. ..nMWmMMnn..
...MMMMMn... ..nMMMMMnn.. ..NMmMMMnN.. ..nMMMMMnn..
...nMMMmn... ...nMMMmn... ..NnMMMmnN.. ...nMMMmn...
....nnnn.... ....nnnn.... ...NnnnnN... ....nnnn....
............ .....nn..... ....NNNN.... .....nn.....
............ ............ ............ ............
............ ............ ............ ............
''', pal)


def proj_ice():
    pal = {'W': WHITE, 'i': IC0, 'I': IC1, 'b': IC2, 'B': IC3}
    base = grid([
        '............',
        '............',
        '............',
        '............',
        '...bIIIii...',
        '.BbbIIiiiiW.',
        '...BBbbbI...',
        '............',
        '............',
        '............',
        '............',
        '............',
    ], pal)
    glints = [
        [(4, 4, WHITE), (3, 5, WHITE), (0, 4, IC3)],
        [(6, 4, WHITE), (5, 5, WHITE), (0, 6, IC3)],
        [(8, 4, WHITE), (7, 5, WHITE)],
        [(10, 5, WHITE), (11, 5, IC0), (10, 4, IC1), (10, 6, IC1), (9, 5, WHITE), (1, 3, IC3)],
    ]
    out = []
    for g in glints:
        img = base.copy()
        for x, y, c in g:
            put(img, x, y, c)
        out.append(img)
    return out


def proj_acid():
    pal = {'W': WHITE, 'a': AC0, 'A': AC1, 'g': AC2, 'G': AC3}
    return frames('''
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
.....aAA.... ............ .....aAA.... .....aA.....
....aWaAA... ....aAAA.... ....aWaAA... ....aWAA....
..g.AaAAg... .g.aWaAAg... .G..AaAAg... ....aaAA....
....AAAgg... ...AaAAgg... ..g.AAAgg... ..g.AAAg....
.....ggg.... ....gggg.... .....ggg.... ....AAgg....
............ ............ ......g..... .....gg.....
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
''', pal)


def proj_bomb():
    pal = {'k': K, 'd': D1, 's': ST1, 'S': ST2, 'L': ST3, 'l': ST4, 'e': EA1,
           'W': WHITE, 'y': FI0, 'Y': FI1, 'o': FI2}
    return frames('''
.......y.W.. ......Y..... ........W... .....y..y.y.
.......oY... .......oWy.. ......yoY... .......oW...
......e..... ......e.y... ......e..... ......e..y..
...kkLSk.... ...kkLSk.... ...kkLSk.... ...kkLSk....
..kSSSSk.... ..kSSSSk.... ..kSSSSk.... ..kSSSSk....
.kSllSSsk... .kSllSSsk... .kSllSSsk... .kSllSSsk...
.kSlSSSsk... .kSlSSSsk... .kSlSSSsk... .kSlSSSsk...
.kSSSSssk... .kSSSSssk... .kSSSSssk... .kSSSSssk...
.kSSSssdk... .kSSSssdk... .kSSSssdk... .kSSSssdk...
..ksdddk.... ..ksdddk.... ..ksdddk.... ..ksdddk....
...kkkk..... ...kkkk..... ...kkkk..... ...kkkk.....
............ ............ ............ ............
''', pal)


def proj_missile():
    pal = {'W': WHITE, 'p': '#f3e6ff', 'v': VI0, 'V': VI1, 'u': VI2}
    # violet arrowhead; a sparkle is shed from the notch and drifts back
    return frames('''
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
....vv...... ....vv...... ....vv...... ....vv......
.....vVVv... ...v.vVVv... .....vVVv... .....vVVv...
u...WuVVpvW. ..vWvuVVpvW. .VvV.uVVpvW. .V..puVVpvW.
.....uVVu... ...v.uVVu... .....uVVu... .....uVVu...
....uu...... ....uu...... ....uu...... ....uu......
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
''', pal)


def proj_meteor():
    pal = {'y': FI0, 'Y': FI1, 'o': FI2, 'r': FI3, 'R': FI4,
           'l': ST4, 'L': ST3, 'S': ST2, 's': ST1, 'D': D1}
    rock = grid([
        '............',
        '............',
        '............',
        '......lLLS..',
        '.....lLLSSs.',
        '.....LLSoSs.',
        '.....LSoSSs.',
        '.....SSSssD.',
        '......ssDD..',
        '............',
        '............',
        '............',
    ], pal)
    # flames wrap the top/back/bottom of the rock and stream backwards (left)
    flames = frames('''
............ ............ ............ ............
......r..... ....r....... .......r.... ............
..RrrooYoo.. ...RroYooo.. ..RrrooooY.. ....RrooYo..
.Rrrooo..... ..Rrooo..... ...Rroo..... .RRrooo.....
...rYoo..... .RrroYo..... .RrrYoo..... ...rrYo.....
RrroYYo..... ..rrYYo..... ..RrYYo..... .RrrYYo.....
.RrrYoo..... RrrYYoo..... ..rrYoo..... ...rYoo.....
...rroo..... ..Rrroo..... RrrYroo..... .Rrrroo.....
..Rrroor.... ...Rroor.... ...rroor.... ..R.roor....
....Rrrrr... .....rrrr... ...Rrrrrr... ....Rrrr....
............ ............ ............ ............
............ ............ ............ ............
''', pal)
    out = []
    for f, fl in enumerate(flames):
        img = fl.copy()
        paste(img, rock, 0, 0)
        # hot leading edge: a thin, flickering glow only on the front corners
        for (x, y) in [(10, 3), (11, 5), (11, 6), (10, 8)]:
            if (x + y + f) % 2 == 0:
                put(img, x, y, FI2)
        out.append(img)
    return out


def proj_drill():
    span = {2: (3, 4), 3: (2, 6), 4: (2, 8), 5: (2, 10), 6: (2, 8), 7: (2, 6), 8: (3, 4)}
    shade = {2: GO0, 3: GO0, 4: GO1, 5: GO1, 6: GO2, 7: GO2, 8: GO3}
    dark2 = {GO0: GO2, GO1: GO3, GO2: GO3, GO3: EA2}
    light = {GO0: WHITE, GO1: GO0, GO2: GO1, GO3: GO2}
    out = []
    for f in range(4):
        img = new(12, 12)
        for y, (x0, x1) in span.items():
            for x in range(x0, x1 + 1):
                c = shade[y]
                ph = (x + y + f) % 4
                if ph == 0:
                    c = dark2[c]
                elif ph == 1 and y <= 5:
                    c = light[c]
                put(img, x, y, c)
        put(img, 10, 5, WHITE)
        for y in range(3, 8):                      # collar
            put(img, 2, y, GO3 if y >= 5 else GO2)
        for y, c in ((4, ST4), (5, ST3), (6, ST2)):  # shank
            put(img, 0, y, c)
            put(img, 1, y, c)
        out.append(img)
    return out


def shade_blob(mask, cx, cy, roles):
    """Colour a blob mask: roles = dict(edge_dark, edge_light, body, body_dark, hi, spec)."""
    h, w = mask.shape
    img = new(w, h)
    edge = mask & ring_of(~mask, diag=False)
    ys, xs = np.nonzero(mask)
    rx = max(1.0, (xs.max() - xs.min() + 1) / 2.0)
    ry = max(1.0, (ys.max() - ys.min() + 1) / 2.0)
    for y, x in zip(ys, xs):
        dx = (x + 0.5 - cx) / rx
        dy = (y + 0.5 - cy) / ry
        lit = -(dx + dy) * 0.7071
        if edge[y, x]:
            col = roles['edge_light'] if lit > -0.25 else roles['edge_dark']
        else:
            if lit > 0.35:
                col = roles['hi']
            elif lit < -0.3:
                col = roles['body_dark']
            else:
                col = roles['body']
        img[y, x] = rgb(col)
    tx, ty = cx - rx * 0.42, cy - ry * 0.42
    best = None
    for y, x in zip(ys, xs):
        if edge[y, x]:
            continue
        d = (x + 0.5 - tx) ** 2 + (y + 0.5 - ty) ** 2
        if best is None or d < best[0]:
            best = (d, x, y)
    if best is not None and roles.get('spec'):
        img[best[2], best[1]] = rgb(roles['spec'])
    return img


def proj_water():
    roles = dict(edge_dark=WA1, edge_light=WA1, body=WA2, body_dark=WA3, hi=WA0, spec=WHITE)
    shapes = [(7, 7, 6.5, 5.5), (8, 6, 6.0, 6.0), (7, 7, 6.5, 5.5), (6, 8, 6.0, 6.0)]
    drops = [
        [(1, 6, WA1), (2, 3, WA0)],
        [(0, 5, WA1), (1, 7, WA2)],
        [(1, 4, WA1), (0, 7, WA2)],
        [(1, 7, WA1), (0, 4, WA2)],
    ]
    out = []
    for (w, h, cx, cy), dr in zip(shapes, drops):
        m = ellipse_mask(12, 12, cx, cy, w / 2.0, h / 2.0)
        img = shade_blob(m, cx, cy, roles)
        for x, y, c in dr:
            put(img, x, y, c)
        out.append(img)
    return out


def proj_quake():
    pal = {'h': EA2, 'E': EA1, 'e': EA0, 'Y': GO1, 'y': GO0, 'W': WHITE}
    cores = frames('''
............ ............ ............ ............
............ ............ ............ ............
............ ............ .....hh..... ............
....hEEh.... ....hEEh.... ....EeeE.... ....hEEh....
...hEeeEh... ...hEYYEh... ...EeYYeE... ...hEYYEh...
...EeYYeE... ...EYyyYE... ..hEYWyYEh.. ...EYyyYE...
...EeYYeE... ...EYyyYE... ..hEYyyYEh.. ...EYyyYE...
...hEeeEh... ...hEYYEh... ...EeYYeE... ...hEYYEh...
....hEEh.... ....hEEh.... ....EeeE.... ....hEEh....
............ ............ .....hh..... ............
............ ............ ............ ............
............ ............ ............ ............
''', pal)
    out = []
    for f, core in enumerate(cores):
        img = core.copy()
        for k in range(3):
            deg = -90 + k * 120 + f * 30
            a = math.radians(deg)
            px = 5.5 + 4.8 * math.cos(a)
            py = 5.5 + 4.8 * math.sin(a)
            tx, ty = int(round(px - 1)), int(round(py - 1))
            put(img, tx, ty, ST4)
            put(img, tx + 1, ty, ST3)
            put(img, tx, ty + 1, ST3)
            put(img, tx + 1, ty + 1, ST2)
        out.append(img)
    return out


def proj_enemy():
    pal = {'k': K, 'K': CR3, 'c': CR2, 'C': CR1, 'l': CR0}
    return frames('''
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
......cC.... .......cC... ......cC.... .....cC.....
...c.CKkC... ..c..CKkC... ...c.CKkC... .c...CKkC...
.cCKkkkkkCl. c.CKkkkkkCl. ..cKkkkkkCl. .cCKkkkkkCl.
...c.CKkC... .....CKkC... .c...CKkC... ...c.CKkC...
......cC.... .....cC..... .......cC... ......cC....
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
''', pal)


def proj_boss_shard():
    # jagged crimson-violet crystal with a dark broken base; a glint runs along the
    # pale core to the tip and the tip flickers
    pal = {'W': WHITE, 'p': SH1, 'P': SH0, 'C': CR1, 'c': CR2, 'K': CR3, 'V': VI1}
    return frames('''
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
...KPV.Pp... ...KPV.PW... ...KPV.Pp... ...KPV.Pp...
..KcPPpWpP.. ..KcPPppWp.. ..KcPPpppP.. ..KcPPpppP..
.KcCCVPPpPW. .KcCCVPPpPp. .KcCCVPPpPW. .KcCCVPPPPp.
...CV.cVc... ...CV.cVc... ...CV.cVc... ...CV.cVc...
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
............ ............ ............ ............
''', pal)


def make_projectiles():
    rows = [proj_spark(), proj_fireball(), proj_orb(), proj_ice(), proj_acid(), proj_bomb(),
            proj_missile(), proj_meteor(), proj_drill(), proj_water(), proj_quake(), proj_enemy(),
            proj_boss_shard()]
    sheet = new(48, 156)
    for r, frs in enumerate(rows):
        assert len(frs) == 4, r
        for c, img in enumerate(frs):
            assert img.shape[:2] == (12, 12), (r, c, img.shape)
            paste(sheet, img, c * 12, r * 12)
    return sheet


# ==========================================================================
# 2. explosion.png  (8 frames of 32x32)
# ==========================================================================
def fire_col(h):
    if h > 0.92:
        return WHITE
    if h > 0.80:
        return FI0
    if h > 0.66:
        return FI1
    if h > 0.52:
        return FI2
    if h > 0.40:
        return FI3
    return None


def smoke_col(s):
    if s > 0.80:
        return ST3
    if s > 0.55:
        return ST2
    if s > 0.32:
        return D2
    return D1


def make_explosion():
    S, N = 32, 8
    sheet = new(S * N, S)
    cx = cy = 16.0
    rng = random.Random(1337)
    npuff = 9
    puffs = []
    for i in range(npuff):
        a = (i + rng.uniform(-0.3, 0.3)) / npuff * 2 * math.pi
        puffs.append(dict(a=a, dm=rng.uniform(0.78, 1.08), rm=rng.uniform(0.82, 1.18),
                          hm=rng.uniform(-0.06, 0.06)))
    sparks = [(rng.uniform(0, 2 * math.pi), rng.uniform(0.85, 1.1)) for _ in range(7)]
    core_r = [0, 9.0, 9.5, 8.0, 5.5, 0, 0, 0]
    core_h = [0, 1.06, 0.92, 0.64, 0.44, 0, 0, 0]
    puff_d = [0, 5.2, 7.0, 8.4, 9.3, 9.9, 10.3, 10.6]
    puff_r = [0, 4.6, 5.3, 5.6, 5.3, 4.8, 4.0, 3.0]
    puff_h = [0, 0.9, 0.72, 0.5, 0.33, 0.2, 0.08, 0.0]
    rise = [0, 0, 0.4, 1.0, 1.7, 2.5, 3.3, 4.0]
    erode = [0, 0, 0, 0.0, 0.08, 0.2, 0.34, 0.5]
    lx, ly = -0.6, -0.8                      # light from upper left
    for f in range(N):
        img = new(S, S)
        noise = value_noise(S, S, 4, 100 + f)
        if f == 0:
            for y in range(S):
                for x in range(S):
                    d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                    if d <= 4.6:
                        put(img, x, y, WHITE)
                    elif d <= 6.2:
                        put(img, x, y, FI0)
                    elif d <= 7.0 and noise[y, x] > 0.35:
                        put(img, x, y, FI1)
            for k in range(8):
                a = k * math.pi / 4
                ln = 11 if k % 2 == 0 else 9
                for t in np.arange(7.0, ln, 0.5):
                    x = int(cx + math.cos(a) * t)
                    y = int(cy + math.sin(a) * t)
                    put(img, x, y, WHITE if t < ln - 2 else FI0)
            paste(sheet, img, f * S, 0)
            continue
        discs = []
        if core_r[f] > 0:
            discs.append((cx, cy - rise[f] * 0.5, core_r[f], core_h[f]))
        for p in puffs:
            d = puff_d[f] * p['dm']
            px = cx + math.cos(p['a']) * d
            py = cy + math.sin(p['a']) * d * 0.9 - rise[f]
            discs.append((px, py, puff_r[f] * p['rm'], puff_h[f] + p['hm']))
        for y in range(S):
            for x in range(S):
                best = None
                for (dx_, dy_, r, h) in discs:
                    d = math.hypot(x + 0.5 - dx_, y + 0.5 - dy_)
                    m = 1 - d / r
                    if m > 0 and (best is None or m > best[0]):
                        best = (m, dx_, dy_, r, h)
                if best is None:
                    continue
                m, dx_, dy_, r, h = best
                if noise[y, x] < erode[f] * (1.5 - m):
                    continue
                nx, ny = (x + 0.5 - dx_) / r, (y + 0.5 - dy_) / r
                lit = nx * lx + ny * ly
                heat = h * (0.72 + 0.4 * m) + 0.08 * lit
                col = fire_col(heat)
                if col is None:
                    if heat > 0.3 and lit < -0.05:
                        col = FI4              # ember glow in the shadowed folds
                    else:
                        col = smoke_col(0.45 + 0.45 * lit + 0.25 * m)
                put(img, x, y, col)
        if f >= 4:
            # drop crumbs: pixels with fewer than two 4-neighbours
            for _ in range(2):
                m = img[..., 3] > 0
                cnt = sum(shifted(m, dx, dy).astype(int) for dx, dy in N4)
                img[m & (cnt < 2)] = 0
        # flying sparks during the fire phase
        if f in (1, 2, 3):
            for (a, sm) in sparks:
                dist = [0, 11.0, 13.0, 14.5][f] * sm
                x = int(cx + math.cos(a) * dist)
                y = int(cy + math.sin(a) * dist)
                put(img, x, y, [None, WHITE, FI0, FI1][f])
                if f < 3:
                    put(img, int(cx + math.cos(a) * (dist - 1.2)), int(cy + math.sin(a) * (dist - 1.2)),
                        [None, FI0, FI1, None][f])
        paste(sheet, img, f * S, 0)
    return sheet


# ==========================================================================
# 3. slash.png  (4 frames of 32x32)  -- near white, tinted in game
# ==========================================================================
def make_slash():
    S = 32
    sheet = new(S * 4, S)
    cx, cy = 14.0, 16.0
    Ro = 15.2
    WH, L1, L2, L3 = WHITE, '#e9edf6', '#c6ccdb', '#a2a9bd'
    # (tail_deg, head_deg, max_width)
    specs = [(-66, -4, 5.2), (-66, 30, 6.6), (-60, 66, 6.0), (-14, 66, 2.6)]
    # concentric speed lines alongside the thin tail; they run into the thick
    # blade body: (radius, s_from, colour); s = 0 tail .. 1 head
    streaks = {0: [(Ro - 3.0, 0.25, L2)],
               1: [(Ro - 3.0, 0.10, L2), (Ro - 5.5, 0.26, L3)],
               2: [(Ro - 3.0, 0.08, L2), (Ro - 5.5, 0.22, L3)],
               3: []}
    for f, (t0, t1, wmax) in enumerate(specs):
        img = new(S, S)
        for y in range(S):
            for x in range(S):
                dx, dy = x + 0.5 - cx, y + 0.5 - cy
                r = math.hypot(dx, dy)
                a = math.degrees(math.atan2(dy, dx))
                if not (t0 <= a <= t1):
                    continue
                s = (a - t0) / (t1 - t0)                       # 0 tail .. 1 head
                base = min(1.0, s / 0.82) ** 1.35               # comet profile: thin tail, thick head
                head = 1.0 if s < 0.88 else math.sqrt(max(0.0, (1 - s) / 0.12))
                w = wmax * base * max(head, 0.35)
                if f == 3:
                    w = wmax * math.sin(math.pi * s) ** 0.6
                    if (int(a + 90) // 7) % 4 == 0:
                        continue                               # broken, fading arc
                if Ro - w <= r <= Ro:
                    if f == 3:
                        c = L1 if r > Ro - 1.2 else L3
                    elif r > Ro - 1.25:
                        c = WH if s > 0.22 else L1
                    elif r > Ro - 0.5 * w - 0.6:
                        c = L1 if s > 0.3 else L2
                    else:
                        c = L2 if s > 0.3 else L3
                    put(img, x, y, c)
                else:
                    for (rs, lo, sc) in streaks[f]:
                        # keep >= 1px gap to the blade so the line reads separately
                        if rs - 0.5 <= r < rs + 0.5 and s > lo and Ro - w > rs + 1.4:
                            put(img, x, y, sc)
        paste(sheet, img, f * S, 0)
    return sheet


# ==========================================================================
# 4. portal.png  (8 frames of 24x32)  -- seamless 8-frame swirl
# ==========================================================================
def make_portal():
    W, H, N = 24, 32, 8
    sheet = new(W * N, H)
    cx, cy = 12.0, 16.0
    ax, by = 10.6, 14.8
    rng = random.Random(99)
    stars = [(rng.uniform(-0.28, 0.28), rng.uniform(-0.3, 0.3), rng.randrange(8)) for _ in range(7)]
    for f in range(N):
        img = new(W, H)
        for y in range(H):
            for x in range(W):
                u = (x + 0.5 - cx) / ax
                v = (y + 0.5 - cy) / by
                r = math.hypot(u, v)
                if r > 1.0:
                    continue
                th = math.atan2(v, u)
                rim_a = (th / (2 * math.pi) - f / N) % 1.0
                if r > 0.925:
                    put(img, x, y, VI1 if rim_a > 0.5 else VI0)
                    continue
                if r > 0.83:
                    put(img, x, y, WHITE if (rim_a < 0.1 or 0.5 < rim_a < 0.6) else CY2)
                    continue
                if r > 0.36:
                    s = (3 * th / (2 * math.pi) + 1.8 * r - f / N) % 1.0
                    if r > 0.66:
                        band = [CY2, CY1, VI1]
                    elif r > 0.5:
                        band = [VI0, VI1, VI2]
                    else:
                        band = [VI1, VI2, VI3]
                    idx = 0 if s < 0.2 else 1 if s < 0.55 else 2
                    put(img, x, y, band[idx])
                    continue
                put(img, x, y, K if r < 0.3 else D1)
        for (su, sv, ph) in stars:
            x = int(cx + su * ax)
            y = int(cy + sv * by)
            st = (f + ph) % N
            if st == 0:
                put(img, x, y, WHITE)
                for dx, dy in N4:
                    if is_col(img, x + dx, y + dy, K) or is_col(img, x + dx, y + dy, D1):
                        put(img, x + dx, y + dy, VI1)
            elif st == 1:
                put(img, x, y, VI0)
            elif st in (2, 5):
                put(img, x, y, VI2)
        paste(sheet, img, f * W, 0)
    return sheet


# ==========================================================================
# 5. fx_small.png  (8x8 cells, 4 x 3)  -- near white / light yellow
# ==========================================================================
def make_fx_small():
    pal = {'W': WHITE, 'y': FI0, 'Y': '#ffe486'}
    sparkle = frames('''
........ ........ ...y.... ........
........ ...y.... ...y.... ........
........ ...W.... ...W.... ...y....
...y.... .yWWWy.. yyWWWyy. ..yWy...
..yWy... ...W.... ...W.... ...y....
...y.... ...y.... ...y.... ........
........ ........ ...y.... ........
........ ........ ........ ........
''', pal)
    burst = frames('''
........ ...y.... y..y..y. y..y..y.
...y.... .y.W.y.. .y.W.y.. ........
..yWy... ..WWW... ........ ........
.yWWWy.. yWW.WWy. yW...Wy. y.....y.
..yWy... ..WWW... ........ ........
...y.... .y.W.y.. .y.W.y.. ........
........ ...y.... y..y..y. y..y..y.
........ ........ ........ ........
''', pal)
    # muzzle flash, firing to the RIGHT from the cell centre
    muzzle = frames('''
.....y.. ........ ........ ........
..y.y... ....y... ........ ........
..WWW... ..yWy... ...y.... ........
.yWWWWWy ..WWWWy. ..yWy.y. ........
..WWW... ..yWy... ...y.... ........
..y.y... ....y... ........ ........
.....y.. ........ ........ ........
........ ........ ........ ........
''', pal)
    sheet = new(32, 24)
    for r, frs in enumerate([sparkle, burst, muzzle]):
        for c, img in enumerate(frs):
            paste(sheet, img, c * 8, r * 8)
    return sheet


# ==========================================================================
# 6. items.png  (12x12 cells, 4 x 3)
# ==========================================================================
def shine(base, interior, diag_sum, width=2, color=WHITE):
    """Brighten interior pixels on the '/' diagonal x + y in [diag_sum, diag_sum + width)."""
    img = base.copy()
    h, w = img.shape[:2]
    for y in range(h):
        for x in range(w):
            if diag_sum <= x + y < diag_sum + width and img[y, x, 3] and tuple(img[y, x]) in interior:
                img[y, x] = rgb(color)
    return img


def item_scroll():
    """Spell scroll ("loitsukäärö"): parchment with rolled ends and a shimmering rune."""
    pal = {'k': K, 'P': PA0, 'p': PA1, 'd': PA2}
    base = grid([
        '............',
        '..kkkkkkkk..',
        '.kPPPPPPPPk.',
        '.kdppppppdk.',
        '..kPPPPPpk..',
        '..kPPPPPpk..',
        '..kPPPPPpk..',
        '..kPPPPPpk..',
        '.kPPPPPPPPk.',
        '.kdppppppdk.',
        '..kkkkkkkk..',
        '............',
    ], pal)
    ring = [(5, 4), (6, 4), (4, 5), (7, 5), (4, 6), (7, 6), (5, 7), (6, 7)]
    core = [(5, 5), (6, 5), (5, 6), (6, 6)]
    corners = [(4, 4), (7, 4), (4, 7), (7, 7)]
    # (ring, core, corner glow) per frame
    looks = [(VI1, CY1, None), (VI1, CY2, VI0), (VI0, WHITE, CY2), (VI1, CY2, None)]
    out = []
    for rc, cc, gc in looks:
        img = base.copy()
        for (x, y) in ring:
            put(img, x, y, rc)
        for (x, y) in core:
            put(img, x, y, cc)
        if gc:
            for (x, y) in corners:
                put(img, x, y, gc)
        out.append(img)
    return out


def make_items():
    hp = {'k': K, 'H': '#ffd0d6', 'l': CR0, 'C': CR1, 'd': CR2}
    heart = grid([
        '............',
        '...kk..kk...',
        '..kHlkkClk..',
        '.kHllCCClCk.',
        '.klllCCCCdk.',
        '.kClllCCddk.',
        '..kCClCddk..',
        '...kCCddk...',
        '....kCdk....',
        '.....kk.....',
        '............',
        '............',
    ], hp)
    hint = {rgb(c) for c in (CR0, CR1, CR2, '#ffd0d6')}
    hearts = [shine(heart, hint, s) for s in (5, 8, 11, 14)]

    gp = {'k': K, 'y': GO0, 'Y': GO1, 'O': GO2, 'o': GO3}
    nugget = grid([
        '............',
        '............',
        '............',
        '.....kkk....',
        '...kkyYYk...',
        '..kyYYYOYk..',
        '..kYYOYYOk..',
        '..kYOOYOok..',
        '...kkOOok...',
        '.....kkk....',
        '............',
        '............',
    ], gp)
    sparks = [
        [(9, 2, FI0)],
        [(9, 2, WHITE), (8, 2, FI0), (10, 2, FI0), (9, 1, FI0), (9, 3, FI0)],
        [(9, 2, WHITE), (8, 2, WHITE), (10, 2, WHITE), (9, 1, WHITE), (9, 3, WHITE),
         (7, 2, FI0), (11, 2, FI0), (9, 0, FI0)],
        [(4, 5, WHITE), (9, 2, FI0)],
    ]
    nuggets = []
    for sp in sparks:
        img = nugget.copy()
        for x, y, c in sp:
            put(img, x, y, c)
        nuggets.append(img)

    mp = {'k': K, 'i': IC0, 'I': IC1, 'b': IC2, 'B': IC3, 'D': '#1f4470'}
    mana = grid([
        '............',
        '.....kk.....',
        '....kIbk....',
        '...kIibBk...',
        '...kIibBk...',
        '...kIibBk...',
        '...kIibBk...',
        '...kIbbDk...',
        '....kbDk....',
        '.....kk.....',
        '............',
        '............',
    ], mp)
    mint = {rgb(c) for c in (IC0, IC1, IC2, IC3, '#1f4470')}
    manas = [shine(mana, mint, s, 2) for s in (13, 11, 9, 7)]

    sheet = new(48, 48)
    for r, frs in enumerate([hearts, nuggets, manas, item_scroll()]):
        for c, img in enumerate(frs):
            paste(sheet, img, c * 12, r * 12)
    return sheet


# ==========================================================================
# 7. ui.png  (12 icons, 8x8, dark outline)
# ==========================================================================
UI_PAL = {
    'k': K, 'W': WHITE,
    'p': '#ffd0d6', 'l': CR0, 'R': CR1, 'd': CR2,          # heart
    'w': WA0, 'b': WA1, 'B': WA2,                         # mana drop
    'C': CY2, 'c': CY1, 'x': CY0,                         # glow
    '4': ST4, '3': ST3, '2': ST2,                         # bone / steel / stone
    'y': GO0, 'Y': GO1, 'O': GO2,                         # gold
    'e': EA0, 'E': EA1, 'h': EA2,                         # wood
    'v': VI0, 'V': VI1, 'u': VI2,                         # violet
}


def make_ui():
    # 0 heart, 1 mana drop, 2 feather, 3 skull, 4 coin, 5 down arrow,
    # 6 hourglass, 7 sword, 8 wand, 9 staff, 10 star, 11 portal swirl
    icons = frames('''
.kk..kk. ...k.... .....kk. .kkkkkk. ..kkkk.. ..kkkk.. kkkkkkk. .....kkk .....C.. ....kkk. ...kk... ..kkkk..
kplkkRRk ..kbk... ....kWWk kWWWWWWk .kyyYYk. ..kW4k.. keeeeEk. ....kW4k ....kCk. ...kvVVk ...kYk.. .kVVVck.
kllRRRdk .kbbbk.. ...kW44k kWWWWW4k kyYYYYOk ..kW4k.. .kyYyk.. ...kW4k. ...kWWkC ...kVWuk kkkyYkkk kVkkkVck
kRRRRRdk kbwbbBk. ..kW4k3k kWkkWkk4 kyYOyYOk kkkW4kkk ..kYk... .kkW4k.. ..kCck.. ..kkuuk. kyyyYYOk kVkCckVk
.kRRRdk. kbwbbBk. .kW4k3k. kWkkW4kk kyYOYYOk kWWW444k ..kyk... kYYk4k.. .kEkk... ..kYkk.. .kyYYOk. kVkckkVk
..kRdk.. kbbbBBk. .kW43k.. k4WWWW4k kYYYYOOk .kWW44k. .kCYCk.. .kYkk... .kEk.... .kEk.... .kYOOOk. kckkkVuk
...kk... .kBBBk.. .k43k... .k4k4kk. .kOOOOk. ..kW4k.. keeeeEk. kEkYk... kEk..... kEk..... kYOkkOOk .kcVVuk.
........ ..kkk... k3kk.... ..kkkk.. ..kkkk.. ...kk... kkkkkkk. kk.k.... kk...... kk...... kkk..kkk ..kkkk..
''', UI_PAL)
    sheet = new(96, 8)
    for i, img in enumerate(icons):
        paste(sheet, img, i * 8, 0)
    return sheet


# ==========================================================================
# 8. slot.png  (3 frames of 20x20)
# ==========================================================================
def make_slot():
    sheet = new(60, 20)
    variants = [
        # ring1 (top-left, bottom-right, mixed corner), ring2 (tl, br), fill, inner shadow, rivet
        dict(a=(ST4, ST2, ST3), b=(ST3, ST1), fill=SLOT_FILL, sh='#110c19', rivet=ST4, gold=False),
        dict(a=(GO0, GO2, GO1), b=(GO1, GO3), fill=SLOT_FILL, sh='#110c19', rivet=WHITE, gold=True),
        dict(a=(ST2, D2, ST1), b=(ST1, D1), fill='#120e1a', sh='#0d0913', rivet=None, gold=False),
    ]
    for i, v in enumerate(variants):
        img = new(20, 20)
        for y in range(20):
            for x in range(20):
                if x in (0, 19) and y in (0, 19):
                    continue                      # rounded outer corners
                ring = min(x, y, 19 - x, 19 - y)
                if ring == 0:
                    c = K
                elif ring in (1, 2):
                    lo, hi = ring, 19 - ring
                    tl = (x == lo or y == lo) and not (x == hi or y == hi)
                    br = (x == hi or y == hi) and not (x == lo or y == lo)
                    pair = v['a'] if ring == 1 else v['b']
                    c = pair[0] if tl else pair[1] if br else (v['a'][2] if ring == 1 else pair[0])
                elif ring == 3:
                    c = K
                else:
                    c = v['sh'] if (x == 4 or y == 4) else v['fill']
                put(img, x, y, c)
        if v['rivet']:
            for (rx, ry) in [(2, 2), (17, 2), (2, 17), (17, 17)]:
                put(img, rx, ry, v['rivet'])
        if v['gold']:
            # corner glints: small sparkles sitting on the border corners
            for (gx, gy) in [(2, 2), (17, 2), (2, 17), (17, 17)]:
                put(img, gx, gy, WHITE)
                for dx, dy in N4:
                    put(img, gx + dx, gy + dy, GO0 if 0 < gx + dx < 19 and 0 < gy + dy < 19 else WHITE)
            for (gx, gy) in [(1, 1), (18, 1), (1, 18), (18, 18)]:
                put(img, gx, gy, WHITE)
        paste(sheet, img, i * 20, 0)
    return sheet


# ==========================================================================
# 9. crosshair.png  (11x11, white + 1px dark outline, open centre)
# ==========================================================================
def make_crosshair():
    img = new(11, 11)
    white = [(5, 1), (5, 2), (5, 8), (5, 9), (1, 5), (2, 5), (8, 5), (9, 5),
             (3, 3), (7, 3), (3, 7), (7, 7)]
    for x, y in white:
        put(img, x, y, WHITE)
    return add_outline(img, K, diag=False)


# ==========================================================================
# 10. logo.png  (200x48)
# ==========================================================================
def letter_mask(ch, H=32, T=8, B=7):
    def bar_end(m, y0, kind, xmax):
        # trims the right end of a horizontal bar starting at row y0 (B rows tall)
        for yy in range(B):
            if kind == 'down':        # top bar: lower edge shorter  -> slanted '\'
                cut = yy // 2
            elif kind == 'up':        # bottom bar: upper edge shorter -> slanted '/'
                cut = (B - 1 - yy) // 2
            else:                     # pointed arrow end '>'
                cut = abs(yy - (B - 1) // 2)
            if cut:
                m[y0 + yy, xmax - cut + 1:xmax + 1] = False

    if ch == 'V':
        w = 34
        m = np.zeros((H, w), bool)
        for y in range(H):
            xl, xr = y // 2, w - 1 - y // 2
            for x in range(xl, xr + 1):
                if xl + T < x < xr - T:
                    continue
                m[y, x] = True
        m[0, 0] = m[0, w - 1] = False
        return m
    if ch == 'E':
        w = 24
        m = np.zeros((H, w), bool)
        m[:, :T] = True
        m[:B, :] = True
        m[H - B:, :] = True
        mid = (H - B) // 2
        m[mid:mid + B, :w - 3] = True
        bar_end(m, 0, 'down', w - 1)
        bar_end(m, mid, 'point', w - 4)
        bar_end(m, H - B, 'up', w - 1)
        m[0, 0] = m[H - 1, 0] = False
        return m
    if ch == 'L':
        w = 22
        m = np.zeros((H, w), bool)
        m[:, :T] = True
        m[H - B:, :] = True
        bar_end(m, H - B, 'up', w - 1)
        m[0, 0] = m[0, T - 1] = m[H - 1, 0] = False
        return m
    if ch == 'H':
        w = 28
        m = np.zeros((H, w), bool)
        m[:, :T] = True
        m[:, w - T:] = True
        mid = (H - B) // 2
        m[mid:mid + B, :] = True
        for (yy, xx) in [(0, 0), (0, T - 1), (0, w - T), (0, w - 1),
                         (H - 1, 0), (H - 1, T - 1), (H - 1, w - T), (H - 1, w - 1)]:
            m[yy, xx] = False
        return m
    if ch == 'O':
        w = 30
        m = np.zeros((H, w), bool)
        c, ci = 7, 3
        iw, ih = w - 2 * T, H - 2 * B
        for y in range(H):
            for x in range(w):
                if x + y < c or (w - 1 - x) + y < c or x + (H - 1 - y) < c or (w - 1 - x) + (H - 1 - y) < c:
                    continue
                ix, iy = x - T, y - B
                if 0 <= ix < iw and 0 <= iy < ih:
                    if not (ix + iy < ci or (iw - 1 - ix) + iy < ci or ix + (ih - 1 - iy) < ci
                            or (iw - 1 - ix) + (ih - 1 - iy) < ci):
                        continue
                m[y, x] = True
        return m
    raise KeyError(ch)


def sparkle(img, x, y, arm=2, core=WHITE, c1=CY2, c2=CY1):
    put(img, x, y, core)
    for dx, dy in N4:
        put(img, x + dx, y + dy, c1)
        if arm >= 2:
            put(img, x + 2 * dx, y + 2 * dy, c2)


def make_logo():
    W, H = 200, 48
    word = 'VELEHO'
    LH = 32
    masks = [letter_mask(c, LH) for c in word]
    gap = 4
    total = sum(m.shape[1] for m in masks) + gap * (len(masks) - 1)
    ox = (W - total) // 2
    oy = 7
    body = np.zeros((H, W), bool)
    letter_boxes = []
    x = ox
    for m in masks:
        h, w = m.shape
        body[oy:oy + h, x:x + w] |= m
        letter_boxes.append((x, w))
        x += w + gap
    # vertical teal -> violet ramp, clean bands
    ramp = ['#a6f7ee', '#6fdcd6', '#4cbcc8', '#4a98cf', '#5576d8', '#6a5adf', '#7744d8', '#6233bd', '#4f27a0']
    def ramp_at(y):
        t = (y - oy) / (LH - 1)
        return min(len(ramp) - 1, max(0, int(round(t * (len(ramp) - 1)))))
    img = new(W, H)
    base_y = oy + LH - 1
    for y in range(H):
        for x in range(W):
            if not body[y, x]:
                continue
            i = ramp_at(y)
            up = body[y - 1, x]
            dn = body[y + 1, x] if y + 1 < H else False
            lf = body[y, x - 1]
            rt = body[y, x + 1]
            if not up:
                c = '#effffd'                           # top bevel highlight
            elif not dn:
                c = FI2 if y >= base_y - 1 else VI3      # ember glow along the base
            elif not lf:
                c = ramp[max(0, i - 1)]
            elif not rt:
                c = ramp[min(len(ramp) - 1, i + 1)]
            else:
                c = ramp[i]
            put(img, x, y, c)
    # hot spots along the ember-lit base (regular rhythm, not noise)
    for x in range(W):
        if body[base_y, x] and (x * 7) % 5 == 0:
            put(img, x, base_y, FI1)
    # ember rune floating in the O's counter
    ob_x, ob_w = letter_boxes[5]
    rx, ry = ob_x + ob_w // 2 - 1, oy + LH // 2 - 1
    rune = {(0, -2): FI2, (-1, -1): FI2, (0, -1): FI1, (1, -1): FI2,
            (-1, 0): FI1, (0, 0): WHITE, (1, 0): FI1,
            (-1, 1): FI3, (0, 1): FI1, (1, 1): FI3, (0, 2): FI3}
    for (dx, dy), c in rune.items():
        put(img, rx + dx, ry + dy, c)
    # drop shadow + outline
    full = img[..., 3] > 0
    shadow = shifted(full, 1, 2) & ~full
    for y, x in zip(*np.nonzero(shadow)):
        put(img, x, y, D1)
    full = img[..., 3] > 0
    ring = ring_of(full, diag=True)
    for y, x in zip(*np.nonzero(ring)):
        put(img, x, y, K)
    # rising embers: (x, y, length) -- bright head, cooling tail below it
    for (ex, ey, ln) in [(21, 3, 2), (61, 2, 1), (94, 3, 2), (129, 1, 1), (151, 3, 2), (184, 4, 1),
                         (42, 44, 1), (76, 45, 2), (119, 44, 1), (166, 45, 1)]:
        cols = [FI1, FI3] if ln == 2 else [FI2]
        for i, c in enumerate(cols):
            if not img[ey + i, ex, 3]:
                put(img, ex, ey + i, c)
    # star sparkles
    sparkle(img, ox + 3, oy - 3, arm=2)
    sparkle(img, letter_boxes[2][0] + 14, oy - 4, arm=1)
    sparkle(img, letter_boxes[5][0] + letter_boxes[5][1] - 2, oy - 2, arm=2)
    sparkle(img, letter_boxes[4][0] + letter_boxes[4][1] + 2, oy + LH + 4, arm=1)
    return img


# ==========================================================================
# 11. bitmap font
# ==========================================================================
CHARSET = ''.join(chr(c) for c in range(32, 127)) + 'ÄÖÅäöåÉéÜü×•…–°'

_A = ['.XXX.', 'X...X', 'X...X', 'XXXXX', 'X...X', 'X...X', 'X...X']
_O = ['.XXX.', 'X...X', 'X...X', 'X...X', 'X...X', 'X...X', '.XXX.']
_U = ['X...X', 'X...X', 'X...X', 'X...X', 'X...X', 'X...X', '.XXX.']
_E = ['XXXX', 'X...', 'X...', 'XXX.', 'X...', 'X...', 'XXXX']
_a = ['.XX.', '...X', '.XXX', 'X..X', '.XXX']
_o = ['.XX.', 'X..X', 'X..X', 'X..X', '.XX.']
_u = ['X..X', 'X..X', 'X..X', 'X..X', '.XXX']
_e = ['.XX.', 'X..X', 'XXXX', 'X...', '.XXX']

# char -> (top row, rows).  Caps/digits rows 2..8, x-height rows 4..8,
# descenders to row 10, row 11 always empty.
GLYPHS = {
    ' ': (2, []),
    '!': (2, ['X', 'X', 'X', 'X', 'X', '.', 'X']),
    '"': (2, ['X.X', 'X.X']),
    '#': (2, ['.X.X.', '.X.X.', 'XXXXX', '.X.X.', 'XXXXX', '.X.X.', '.X.X.']),
    '$': (1, ['..X..', '.XXXX', 'X.X..', 'X.X..', '.XXX.', '..X.X', '..X.X', 'XXXX.', '..X..']),
    '%': (2, ['XX..X', 'XX..X', '...X.', '..X..', '.X...', 'X..XX', 'X..XX']),
    '&': (2, ['.XX..', 'X..X.', 'X.X..', '.X...', 'X.X.X', 'X..X.', '.XX.X']),
    "'": (2, ['X', 'X']),
    '(': (1, ['.X', 'X.', 'X.', 'X.', 'X.', 'X.', 'X.', 'X.', '.X']),
    ')': (1, ['X.', '.X', '.X', '.X', '.X', '.X', '.X', '.X', 'X.']),
    '*': (3, ['..X..', 'X.X.X', '.XXX.', 'X.X.X', '..X..']),
    '+': (4, ['..X..', '..X..', 'XXXXX', '..X..', '..X..']),
    ',': (8, ['.X', 'X.']),
    '-': (6, ['XXX']),
    '.': (8, ['X']),
    '/': (2, ['..X', '..X', '.X.', '.X.', '.X.', 'X..', 'X..']),
    '0': (2, ['.XX.', 'X..X', 'X..X', 'X..X', 'X..X', 'X..X', '.XX.']),
    '1': (2, ['.X.', 'XX.', '.X.', '.X.', '.X.', '.X.', 'XXX']),
    '2': (2, ['.XX.', 'X..X', '...X', '..X.', '.X..', 'X...', 'XXXX']),
    '3': (2, ['.XX.', 'X..X', '...X', '.XX.', '...X', 'X..X', '.XX.']),
    '4': (2, ['...X', '..XX', '.X.X', 'X..X', 'XXXX', '...X', '...X']),
    '5': (2, ['XXXX', 'X...', 'XXX.', '...X', '...X', 'X..X', '.XX.']),
    '6': (2, ['.XX.', 'X...', 'X...', 'XXX.', 'X..X', 'X..X', '.XX.']),
    '7': (2, ['XXXX', '...X', '...X', '..X.', '.X..', '.X..', '.X..']),
    '8': (2, ['.XX.', 'X..X', 'X..X', '.XX.', 'X..X', 'X..X', '.XX.']),
    '9': (2, ['.XX.', 'X..X', 'X..X', '.XXX', '...X', '...X', '.XX.']),
    ':': (5, ['X', '.', '.', 'X']),
    ';': (5, ['.X', '..', '..', '.X', 'X.']),
    '<': (4, ['..X', '.X.', 'X..', '.X.', '..X']),
    '=': (5, ['XXXX', '....', 'XXXX']),
    '>': (4, ['X..', '.X.', '..X', '.X.', 'X..']),
    '?': (2, ['.XX.', 'X..X', '...X', '..X.', '.X..', '....', '.X..']),
    '@': (2, ['.XXX.', 'X...X', 'X.XXX', 'X.X.X', 'X.XXX', 'X....', '.XXX.']),
    'A': (2, _A),
    'B': (2, ['XXXX.', 'X...X', 'X...X', 'XXXX.', 'X...X', 'X...X', 'XXXX.']),
    'C': (2, ['.XXX.', 'X...X', 'X....', 'X....', 'X....', 'X...X', '.XXX.']),
    'D': (2, ['XXXX.', 'X...X', 'X...X', 'X...X', 'X...X', 'X...X', 'XXXX.']),
    'E': (2, _E),
    'F': (2, ['XXXX', 'X...', 'X...', 'XXX.', 'X...', 'X...', 'X...']),
    'G': (2, ['.XXX.', 'X...X', 'X....', 'X..XX', 'X...X', 'X...X', '.XXX.']),
    'H': (2, ['X...X', 'X...X', 'X...X', 'XXXXX', 'X...X', 'X...X', 'X...X']),
    'I': (2, ['XXX', '.X.', '.X.', '.X.', '.X.', '.X.', 'XXX']),
    'J': (2, ['...X', '...X', '...X', '...X', '...X', 'X..X', '.XX.']),
    'K': (2, ['X...X', 'X..X.', 'X.X..', 'XX...', 'X.X..', 'X..X.', 'X...X']),
    'L': (2, ['X...', 'X...', 'X...', 'X...', 'X...', 'X...', 'XXXX']),
    'M': (2, ['X...X', 'XX.XX', 'X.X.X', 'X.X.X', 'X...X', 'X...X', 'X...X']),
    'N': (2, ['X...X', 'X...X', 'XX..X', 'X.X.X', 'X..XX', 'X...X', 'X...X']),
    'O': (2, _O),
    'P': (2, ['XXXX.', 'X...X', 'X...X', 'XXXX.', 'X....', 'X....', 'X....']),
    'Q': (2, ['.XXX.', 'X...X', 'X...X', 'X...X', 'X.X.X', 'X..X.', '.XX.X']),
    'R': (2, ['XXXX.', 'X...X', 'X...X', 'XXXX.', 'X.X..', 'X..X.', 'X...X']),
    'S': (2, ['.XXX.', 'X...X', 'X....', '.XXX.', '....X', 'X...X', '.XXX.']),
    'T': (2, ['XXXXX', '..X..', '..X..', '..X..', '..X..', '..X..', '..X..']),
    'U': (2, _U),
    'V': (2, ['X...X', 'X...X', 'X...X', 'X...X', '.X.X.', '.X.X.', '..X..']),
    'W': (2, ['X...X', 'X...X', 'X...X', 'X.X.X', 'X.X.X', 'XX.XX', 'X...X']),
    'X': (2, ['X...X', 'X...X', '.X.X.', '..X..', '.X.X.', 'X...X', 'X...X']),
    'Y': (2, ['X...X', 'X...X', '.X.X.', '..X..', '..X..', '..X..', '..X..']),
    'Z': (2, ['XXXXX', '....X', '...X.', '..X..', '.X...', 'X....', 'XXXXX']),
    '[': (1, ['XX', 'X.', 'X.', 'X.', 'X.', 'X.', 'X.', 'X.', 'XX']),
    '\\': (2, ['X..', 'X..', '.X.', '.X.', '.X.', '..X', '..X']),
    ']': (1, ['XX', '.X', '.X', '.X', '.X', '.X', '.X', '.X', 'XX']),
    '^': (2, ['.X.', 'X.X']),
    '_': (9, ['XXXX']),
    '`': (2, ['X.', '.X']),
    'a': (4, _a),
    'b': (2, ['X...', 'X...', 'XXX.', 'X..X', 'X..X', 'X..X', 'XXX.']),
    'c': (4, ['.XXX', 'X...', 'X...', 'X...', '.XXX']),
    'd': (2, ['...X', '...X', '.XXX', 'X..X', 'X..X', 'X..X', '.XXX']),
    'e': (4, _e),
    'f': (2, ['.XX', '.X.', 'XXX', '.X.', '.X.', '.X.', '.X.']),
    'g': (4, ['.XXX', 'X..X', 'X..X', 'X..X', '.XXX', '...X', '.XX.']),
    'h': (2, ['X...', 'X...', 'XXX.', 'X..X', 'X..X', 'X..X', 'X..X']),
    'i': (2, ['X', '.', 'X', 'X', 'X', 'X', 'X']),
    'j': (2, ['.X', '..', '.X', '.X', '.X', '.X', '.X', '.X', 'X.']),
    'k': (2, ['X...', 'X...', 'X..X', 'X.X.', 'XX..', 'X.X.', 'X..X']),
    'l': (2, ['X', 'X', 'X', 'X', 'X', 'X', 'X']),
    'm': (4, ['XXXX.', 'X.X.X', 'X.X.X', 'X.X.X', 'X.X.X']),
    'n': (4, ['XXX.', 'X..X', 'X..X', 'X..X', 'X..X']),
    'o': (4, _o),
    'p': (4, ['XXX.', 'X..X', 'X..X', 'X..X', 'XXX.', 'X...', 'X...']),
    'q': (4, ['.XXX', 'X..X', 'X..X', 'X..X', '.XXX', '...X', '...X']),
    'r': (4, ['X.XX', 'XX..', 'X...', 'X...', 'X...']),
    's': (4, ['.XXX', 'X...', '.XX.', '...X', 'XXX.']),
    't': (2, ['.X.', '.X.', 'XXX', '.X.', '.X.', '.X.', '..X']),
    'u': (4, _u),
    'v': (4, ['X...X', 'X...X', '.X.X.', '.X.X.', '..X..']),
    'w': (4, ['X...X', 'X...X', 'X.X.X', 'X.X.X', '.X.X.']),
    'x': (4, ['X...X', '.X.X.', '..X..', '.X.X.', 'X...X']),
    'y': (4, ['X..X', 'X..X', 'X..X', 'X..X', '.XXX', '...X', '.XX.']),
    'z': (4, ['XXXX', '..X.', '.X..', 'X...', 'XXXX']),
    '{': (1, ['..X', '.X.', '.X.', '.X.', 'X..', '.X.', '.X.', '.X.', '..X']),
    '|': (1, ['X'] * 9),
    '}': (1, ['X..', '.X.', '.X.', '.X.', '..X', '.X.', '.X.', '.X.', 'X..']),
    '~': (5, ['.XX.X', 'X..X.']),
    'Ä': (0, ['.X.X.', '.....'] + _A),
    'Ö': (0, ['.X.X.', '.....'] + _O),
    'Å': (0, ['..X..', '.X.X.'] + _A),
    'ä': (2, ['X..X', '....'] + _a),
    'ö': (2, ['X..X', '....'] + _o),
    'å': (1, ['..X.', '.X.X', '..X.'] + _a),
    'É': (0, ['..X.', '.X..'] + _E),
    'é': (1, ['..X.', '.X..', '....'] + _e),
    'Ü': (0, ['.X.X.', '.....'] + _U),
    'ü': (2, ['X..X', '....'] + _u),
    '×': (5, ['X.X', '.X.', 'X.X']),
    '•': (5, ['.X.', 'XXX', '.X.']),
    '…': (8, ['X.X.X']),
    '–': (6, ['XXXXX']),
    '°': (2, ['.X.', 'X.X', '.X.']),
}


def make_font():
    assert len(CHARSET) == 95 + 15, len(CHARSET)
    missing = [c for c in CHARSET if c not in GLYPHS]
    assert not missing, missing
    cols = 16
    rows = (len(CHARSET) + cols - 1) // cols
    atlas = new(cols * 8, rows * 12)
    for i, ch in enumerate(CHARSET):
        top, rws = GLYPHS[ch]
        assert top + len(rws) <= 11, ch          # row 11 stays empty
        cx, cy = (i % cols) * 8, (i // cols) * 12
        for r, row in enumerate(rws):
            assert len(row) <= 8, ch
            for x, c in enumerate(row):
                if c == 'X':
                    atlas[cy + top + r, cx + x] = (255, 255, 255, 255)
    return atlas


def glyph_metrics(atlas):
    """char -> (cell_x, cell_y, first_used_col, width) of the trimmed glyph."""
    res = {}
    for i, ch in enumerate(CHARSET):
        cx, cy = (i % 16) * 8, (i // 16) * 12
        cell = atlas[cy:cy + 12, cx:cx + 8, 3] > 0
        used = np.nonzero(cell.any(axis=0))[0]
        if len(used) == 0:
            res[ch] = (cx, cy, 0, 0)
        else:
            res[ch] = (cx, cy, used[0], used[-1] - used[0] + 1)
    return res


def render_text(atlas, text, space_w=3, spacing=1, color=(255, 255, 255)):
    """Lay out text the way the game does: trimmed glyphs + 1px spacing."""
    met = glyph_metrics(atlas)
    text = text.replace('—', '–')      # em dash is not in the charset -> en dash
    lines = text.split('\n')
    width = 0
    for ln in lines:
        w = 0
        for ch in ln:
            cx, cy, x0, gw = met.get(ch, met['?'])
            w += (space_w if ch == ' ' else gw) + spacing
        width = max(width, w)
    img = new(width + 2, 12 * len(lines) + 2)
    for li, ln in enumerate(lines):
        pen = 1
        for ch in ln:
            cx, cy, x0, gw = met.get(ch, met['?'])
            if ch == ' ':
                pen += space_w + spacing
                continue
            cell = atlas[cy:cy + 12, cx + x0:cx + x0 + gw]
            for y in range(12):
                for x in range(gw):
                    if cell[y, x, 3]:
                        img[1 + li * 12 + y, pen + x] = (*color, 255)
            pen += gw + spacing
    return img


# ==========================================================================
# 12. spell_icons.png  (16x16 spell cards, 8 cols x 3 rows, row-major index)
#     0-11 projectile spells: dark card, 1px border in the element colour
#     12-21 modifier spells: deep-blue card, light-blue border.  22-23 empty.
#     Projectiles fly towards the upper right, like projectiles.png rotated.
# ==========================================================================
def card_base(border, tones):
    """16x16 card: corner pixels cut, 1px border, darker inner ring, lighter field."""
    dark, light = tones
    img = new(16, 16)
    for y in range(16):
        for x in range(16):
            if x in (0, 15) and y in (0, 15):
                continue
            ring = min(x, y, 15 - x, 15 - y)
            put(img, x, y, border if ring == 0 else dark if ring == 1 else light)
    return img


def card_art(rows, pal):
    """14x14 artwork that goes inside the card border."""
    g = grid(rows, pal)
    assert g.shape[:2] == (14, 14), g.shape
    return g


def line_pts(x0, y0, x1, y1):
    """Bresenham line, both ends included."""
    pts = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return pts
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def icon_spark():
    pal = {'W': WHITE, 'C': CY2, 'c': CY1, 'x': CY0}
    return card_art([
        '.........x....',
        '.........c....',
        '........xCx...',
        '.......xCWCx..',
        '......xCWWWCcx',
        '.......xCWCx..',
        '.......C.c....',
        '......c.......',
        '.....c........',
        '....x.........',
        '..............',
        '..x...........',
        '..............',
        '..............',
    ], pal)


def icon_fireball():
    pal = {'W': WHITE, 'y': FI0, 'Y': FI1, 'o': FI2, 'r': FI3, 'R': FI4}
    img = card_art([
        '..............',
        '..............',
        '..............',
        '..............',
        '......r.......',
        '.....rroo.....',
        '....Rrooo.....',
        '...R.rroYo....',
        '..RrrroYYo....',
        '.R.rrroo......',
        '..RrRrr.......',
        '.Rr.R.........',
        'R..R..........',
        '..............',
    ], pal)
    # the ball: white-hot towards the front (upper right), cooler at the back
    cx, cy, r = 9.5, 4.5, 3.8
    m = ellipse_mask(14, 14, cx, cy, r, r)
    for y, x in zip(*np.nonzero(m)):
        d = math.hypot(x + 0.5 - 10.3, y + 0.5 - 3.7)
        back = (-(x + 0.5 - cx) + (y + 0.5 - cy)) / r * 0.7071
        c = WHITE if d < 1.5 else FI0 if d < 2.5 else FI1 if d < 3.4 else FI2
        if back > 0.55:
            c = FI3 if back > 0.8 else FI2
        put(img, x, y, c)
    return img


def icon_orb():
    # bouncing orb: faded ghosts of the earlier positions, squashed on the floor
    pal = {'W': WHITE, 'm': MG0, 'M': MG1, 'n': MG2, 'L': ST3}
    return card_art([
        '.........mMM..',
        '.n......mWWMn.',
        'nMn....mWWmMMn',
        '.n.....MWmMMMn',
        '.......MMMMMnn',
        '..n.....nMMnn.',
        '.........nnn..',
        '...n..........',
        '.......n......',
        '..............',
        '....nnn.......',
        '...nMMMn......',
        '....nnn.......',
        '.LLLLLLLLL....',
    ], pal)


def icon_ice():
    pal = {'W': WHITE, 'i': IC0, 'I': IC1, 'b': IC2, 'B': IC3}
    return card_art([
        '..............',
        '............W.',
        '...........I..',
        '.........iIb..',
        '.......iWIb...',
        '......iiIbB...',
        '.....iiIbB....',
        '....iWIbB.....',
        '...iiIbB......',
        '...iIbB.......',
        '..iIbB........',
        '..IbB.........',
        '.BB...........',
        '..............',
    ], pal)


def icon_acid():
    pal = {'W': WHITE, 'a': AC0, 'A': AC1, 'g': AC2, 'G': AC3}
    return card_art([
        '..............',
        '.........aAA..',
        '.......aaWaAA.',
        '......aWWaAAAg',
        '...g..AaaAAAgg',
        '......AAAAAggg',
        '..g..gAAAAggG.',
        '......gAAggG..',
        '.......gAgG...',
        '.......gG.G...',
        '.......G......',
        '..........g...',
        '.......g......',
        '..............',
    ], pal)


def icon_bomb():
    pal = {'k': K, 'd': D1, 's': ST1, 'S': ST2, 'L': ST3, 'l': ST4, 'e': EA1, 'E': EA0,
           'W': WHITE, 'y': FI0, 'Y': FI1}
    return card_art([
        '..........Y...',
        '.........YWY.y',
        '.......eE.Y...',
        '......e.......',
        '...kkkLSk.....',
        '..kSSSSSSk....',
        '.kSllSSSSsk...',
        '.kSlSSSSSsk...',
        '.kSlSSSSssk...',
        '.kSSSSSSsdk...',
        '.kSSSSSssdk...',
        '..kSSsssdk....',
        '...kkkkkk.....',
        '..............',
    ], pal)


def icon_missile():
    pal = {'W': WHITE, 'p': '#f3e6ff', 'v': VI0, 'V': VI1, 'u': VI2, 'U': VI3}
    return card_art([
        '..............',
        '............W.',
        '..........vW..',
        '........vvpV..',
        '.......vVpV...',
        '.....vvVpVu...',
        '...VvvVVuu....',
        '..VvvVVuu.....',
        '......uuu.....',
        '....W.uu......',
        '..V...UU......',
        '......U.......',
        '.u............',
        '..............',
    ], pal)


def icon_meteor():
    fpal = {'Y': FI1, 'o': FI2, 'r': FI3, 'R': FI4}
    rpal = {'l': ST4, 'L': ST3, 'S': ST2, 's': ST1, 'D': D1, 'o': FI2, 'y': FI1}
    flames = card_art([
        '......r.......',
        '.....o........',
        '....Y.........',
        '...oY.........',
        '..roY.........',
        '.rroo.........',
        'R.rroY........',
        '.R.rooY.......',
        'R..orooYoor...',
        '..r..rorr.....',
        '.r...r.R......',
        'R...R.R.......',
        '...R..........',
        '..............',
    ], fpal)
    rock = card_art([
        '.......lLLS...',
        '......lLLLSS..',
        '.....lLLLSoSs.',
        '.....LLLSoySs.',
        '.....LLSSoSSsD',
        '.....LSSoSSssD',
        '......SSSssDD.',
        '.......ssDDD..',
        '..............',
        '..............',
        '..............',
        '..............',
        '..............',
        '..............',
    ], rpal)
    img = overlay(flames, rock)
    for (x, y) in [(11, 0), (12, 1), (13, 3)]:       # glowing leading edge
        put(img, x, y, FI2)
    return img


def icon_drill():
    """Golden drill cone pointing up-right with slanted (helical) grooves, steel shank."""
    img = new(14, 14)
    a_tip, a_base, R = 7.6, -1.6, 3.1
    for y in range(14):
        for x in range(14):
            px, py = x + 0.5 - 7.0, y + 0.5 - 7.0
            a = (px - py) / math.sqrt(2)            # along the axis, + towards upper right
            p = (px + py) / math.sqrt(2)            # across it, + towards lower right
            if a_base <= a <= a_tip:
                hw = R * (a_tip - a) / (a_tip - a_base)
                if abs(p) <= hw + 0.15:
                    groove = (a - p * 0.9) % 2.4 < 0.85
                    if p < -0.9:
                        c = GO1 if groove else GO0
                    elif p < 0.4:
                        c = GO2 if groove else GO1
                    else:
                        c = GO3 if groove else GO2
                    if p > 0 and abs(p) > hw - 0.55:
                        c = GO3
                    put(img, x, y, c)
            elif a_base - 1.0 <= a < a_base and abs(p) <= R * 0.95:
                put(img, x, y, GO3 if p > -0.5 else GO2)      # collar
            elif a_base - 5.2 <= a < a_base - 1.0 and abs(p) <= 1.0:
                put(img, x, y, ST4 if p < -0.3 else ST3 if p < 0.4 else ST2)
    put(img, 12, 1, WHITE)
    return img


def icon_water():
    pal = {'b': WA1, 'B': WA2, 'D': WA3, 'w': WA0, 'W': WHITE}
    return card_art([
        '..............',
        '......bbbbb...',
        '.....bwwBBBb..',
        '....bwWwBBBBb.',
        '....bwBBBBBBb.',
        '....bBBBBBBDb.',
        '....bBBBBBDDb.',
        '....bBBBBDDDb.',
        '..b..bBDDDDb..',
        '......bbbbb...',
        '.bw...........',
        '.bb..b........',
        '..............',
        'b.............',
    ], pal)


def icon_quake():
    pal = {'h': EA2, 'E': EA1, 'e': EA0, 'Y': GO1, 'y': GO0, 'W': WHITE,
           'l': ST4, 'L': ST3, 'S': ST2, 's': ST1}
    return card_art([
        '........hh.lL.',
        '..........lLLS',
        '...........Ss.',
        '.....hEEh.....',
        '....hEeeEh....',
        '...hEeYYeEh...',
        '...EeYyWYeE...',
        '...EeYyyYeE...',
        'lL.hEeYYeEh...',
        'LLS.hEeeEh..h.',
        '.Ss..hEEh...h.',
        'h.........lL..',
        'h........lLLS.',
        '..........Ss..',
    ], pal)


def icon_lightning():
    pal = {'W': WHITE, 'Y': STORM, 'O': GO1}
    return card_art([
        '..............',
        '.......YYYYY..',
        '......YWWWO...',
        '.....YWWWO....',
        '....YWWWO.....',
        '...YWWWWYYYY..',
        '...OOOOWWWO...',
        '......YWWO....',
        '.....YWWO.....',
        '....YWWO......',
        '....YWO.......',
        '...YWO........',
        '...WO.........',
        '..............',
    ], pal)


def icon_damage():
    pal = {'k': K, 'l': CR0, 'C': CR1, 'd': CR2, 'y': GO0, 'Y': GO1}
    return card_art([
        '...........y..',
        '....k......y..',
        '...klk...yyyyY',
        '..kllCk....y..',
        '.kllCCCk...Y..',
        'kllCCCCdk.....',
        'kkklCCkkk.....',
        '..klCdk.......',
        '..klCdk.......',
        '..klCdk.......',
        '..klCdk.......',
        '..klCdk.......',
        '..kkkkk.......',
        '..............',
    ], pal)


def icon_speed():
    pal = {'W': WHITE, 'y': GO0, 'Y': GO1, 'O': GO2}
    return card_art([
        '..............',
        '..............',
        '.yy.....yy....',
        '..yy.....yy...',
        '...yy.....yy..',
        '....yy.....yy.',
        '.....yW.....yW',
        '.....YO.....YO',
        '....YO.....YO.',
        '...YO.....YO..',
        '..YO.....YO...',
        '.YO.....YO....',
        '..............',
        '..............',
    ], pal)


def icon_homing():
    pal = {'l': CR0, 'C': CR1, 'W': WHITE, 'v': VI0, 'V': VI1}
    return card_art([
        '.........lll..',
        '........lWWWl.',
        '.......lWWCWWl',
        '.......lWCCCWl',
        '....vvvlWWCWWl',
        '.....vV.lWWWl.',
        '....vVv..lll..',
        '...vV.........',
        '..vV..........',
        '.vV...........',
        '.vV...........',
        '.vV...........',
        '.vV...........',
        '..............',
    ], pal)


def icon_bounce():
    img = card_art(['L' * 14] + ['.' * 14] * 12 + ['S' * 14], {'L': ST3, 'S': ST2})
    for x, y in line_pts(0, 3, 4, 12) + line_pts(4, 12, 8, 1) + line_pts(8, 1, 11, 8):
        put(img, x, y, MG0)
    for (x, y) in [(4, 12), (8, 1)]:                  # impacts
        put(img, x, y, WHITE)
    orb = grid(['.mM.', 'mWMn', 'MMnn', '.nn.'], {'m': MG0, 'M': MG1, 'n': MG2, 'W': WHITE})
    paste(img, orb, 10, 7)
    return img


def small_orb(cols, big=False):
    a, A, b = cols
    rows = ['.aAA.', 'aWaAb', 'AaAAb', 'AAAbb', '.bbb.'] if big else ['.aA.', 'aWAb', 'AAbb', '.bb.']
    return grid(rows, {'a': a, 'A': A, 'b': b, 'W': WHITE})


def icon_multicast(n):
    """n spells leaving one point at once: trails fanning out to n differently coloured orbs."""
    img = new(14, 14)
    orbcols = [(CY2, CY1, CY0), (GO0, GO1, GO2), (MG0, MG1, MG2)]
    if n == 2:
        spots, big = [(8, 0, 10, 2), (8, 9, 10, 11)], True        # orb x, y, trail end x, y
    else:
        spots, big = [(9, 0, 10, 1), (10, 5, 11, 6), (9, 10, 10, 11)], False
    for i, (ox, oy, ex, ey) in enumerate(spots):
        pts = line_pts(1, 6 if ey < 6 else 7, ex, ey)
        for k, (x, y) in enumerate(pts):
            put(img, x, y, orbcols[i][2] if k < 0.55 * (len(pts) - 1) else orbcols[i][1])
    for i, (ox, oy, ex, ey) in enumerate(spots):
        paste(img, small_orb(orbcols[i], big), ox, oy)
    for (x, y) in [(0, 6), (0, 7), (1, 6), (1, 7)]:
        put(img, x, y, WHITE)
    return img


def icon_explode():
    pal = {'W': WHITE, 'y': FI0, 'Y': FI1, 'o': FI2, 'r': FI3}
    return card_art([
        '..............',
        '......oo......',
        '..r...YY...r..',
        '...oo.YY.oo...',
        '...oYYyyYYo...',
        '....YyWWyY....',
        '.ooYyWWWWyYoo.',
        '.ooYyWWWWyYoo.',
        '....YyWWyY....',
        '...oYYyyYYo...',
        '...oo.YY.oo...',
        '..r...YY...r..',
        '......oo......',
        '..............',
    ], pal)


def icon_pierce():
    pal = {'k': K, 'L': ST3, 'S': ST2, 's': ST1, 'l': ST4, 'y': GO0, 'Y': GO1, 'O': GO2}
    return card_art([
        '..............',
        '..............',
        '.....kkkkk....',
        '.....klLSk....',
        '.....kLSSk..y.',
        '.y...kLSsk..yy',
        'yyyyykLSskyyyy',
        'YOOOOkSSskOOOO',
        '.O...kSssk..OO',
        '.....kSssk..O.',
        '.....kssskk...',
        '.....kkkkk....',
        '..............',
        '..............',
    ], pal)


def icon_accuracy():
    img = new(14, 14)
    for y in range(14):
        for x in range(14):
            if 4.4 <= math.hypot(x + 0.5 - 7, y + 0.5 - 7) <= 5.5:
                put(img, x, y, WHITE)
    for k in range(4):
        for (x, y) in [(6, k), (7, k), (6, 13 - k), (7, 13 - k), (k, 6), (k, 7), (13 - k, 6), (13 - k, 7)]:
            put(img, x, y, WHITE)
    for (x, y) in [(6, 6), (7, 6), (6, 7), (7, 7)]:
        put(img, x, y, CR0)
    return img


def icon_giant():
    cx, cy, r = 8.8, 6.6, 4.9
    roles = dict(edge_dark=CY0, edge_light=CY1, body=CY1, body_dark=CY0, hi=CY2, spec=WHITE)
    img = shade_blob(ellipse_mask(14, 14, cx, cy, r, r), cx, cy, roles)
    paste(img, grid(['xCx', 'CWC', 'xCx'], {'C': CY2, 'W': WHITE, 'x': CY0}), 0, 9)
    return img


SPELL_ICONS = [
    # projectile spells: (artwork, element of the border)
    (icon_spark, 'arcane'), (icon_fireball, 'fire'), (icon_orb, 'arcane'), (icon_ice, 'ice'),
    (icon_acid, 'acid'), (icon_bomb, 'fire'), (icon_missile, 'arcane'), (icon_meteor, 'fire'),
    (icon_drill, 'earth'), (icon_water, 'water'), (icon_quake, 'earth'), (icon_lightning, 'storm'),
    # modifiers
    (icon_damage, None), (icon_speed, None), (icon_homing, None), (icon_bounce, None),
    (lambda: icon_multicast(2), None), (lambda: icon_multicast(3), None), (icon_explode, None),
    (icon_pierce, None), (icon_accuracy, None), (icon_giant, None),
]


def make_spell_icons():
    sheet = new(128, 48)
    for i, (art, element) in enumerate(SPELL_ICONS):
        if element:
            card = card_base(ELEM_COL[element], CARD_PROJ)
        else:
            card = card_base(MOD_BORDER, CARD_MOD)
        paste(card, art(), 1, 1)
        paste(sheet, card, (i % 8) * 16, (i // 8) * 16)
    return sheet


# ==========================================================================
# 13. ui_controls.png  (10x10 cells, graphic centred: offset = (10 - size) // 2)
#     0 checkbox  1 checkbox checked  2 slider grabber  3 grabber highlighted
#     4 arrow left  5 arrow right  6 close  7 padlock
# ==========================================================================
def shade_strokes(mask, lit, mid, dark):
    """Colour a stroke mask lit from the upper left."""
    h, w = mask.shape
    img = new(w, h)
    for y, x in zip(*np.nonzero(mask)):
        up = y > 0 and mask[y - 1, x]
        lf = x > 0 and mask[y, x - 1]
        dn = y < h - 1 and mask[y + 1, x]
        rt = x < w - 1 and mask[y, x + 1]
        put(img, x, y, lit if not (up and lf) else dark if not (dn and rt) else mid)
    return img


def make_ui_controls():
    sheet = new(80, 10)
    box = new(9, 9)                                    # stone bevel around a dark well
    for y in range(9):
        for x in range(9):
            if x in (0, 8) and y in (0, 8):
                continue
            ring = min(x, y, 8 - x, 8 - y)
            if ring == 0:
                c = K
            elif ring == 1:
                tl = (x == 1 or y == 1) and not (x == 7 or y == 7)
                br = (x == 7 or y == 7) and not (x == 1 or y == 1)
                c = ST4 if tl else ST2 if br else ST3
            else:
                c = '#0d0913' if (x == 2 or y == 2) else SLOT_FILL
            put(box, x, y, c)
    paste(sheet, box, 0, 0)
    checked = box.copy()
    paste(checked, grid([
        '.....yY',
        '....yYO',
        'y..yYO.',
        'YyyYO..',
        '.YYO...',
        '..O....',
    ], {'y': GO0, 'Y': GO1, 'O': GO2}), 1, 1)          # tick spills over the rim
    paste(sheet, checked, 10, 0)
    knob = ['.kkk.', 'klllk', 'klLSk', 'klLSk', 'kSkSk', 'klLSk', 'klLSk', 'kLSsk', '.kkk.']
    paste(sheet, grid(knob, {'k': K, 'l': ST4, 'L': ST3, 'S': ST2, 's': ST1}), 22, 0)
    paste(sheet, grid(knob, {'k': K, 'l': WHITE, 'L': GO0, 'S': GO1, 's': GO2}), 32, 0)
    arrow = ['...kl', '..kll', '.klll', 'kllll', '.kLLL', '..kLL', '...kL']
    apal = {'k': K, 'l': ST4, 'L': ST3}
    paste(sheet, grid(arrow, apal), 42, 1)
    paste(sheet, grid([r[::-1] for r in arrow], apal), 52, 1)
    cross = np.array([[ch == 'X' for ch in r] for r in [
        'XX...XX',
        'XXX.XXX',
        '.XXXXX.',
        '..XXX..',
        '.XXXXX.',
        'XXX.XXX',
        'XX...XX',
    ]])
    paste(sheet, shade_strokes(cross, CR0, CR1, CR2), 61, 1)
    paste(sheet, grid([
        '..LLL..',
        '.L...S.',
        '.L...S.',
        'yyyyyyY',
        'yYYYYYO',
        'YYYkYYO',
        'YYYkYYO',
        'OOOOOOO',
    ], {'L': ST4, 'S': ST3, 'y': GO0, 'Y': GO1, 'O': GO2, 'k': K}), 71, 1)
    return sheet


# ==========================================================================
# 14. panel.png  (24x24 nine-slice, 8 px corners)
#     Edge strips depend only on the distance to the outer edge, so they stretch
#     or tile cleanly; the middle 8x8 is plain PANEL_FILL.
# ==========================================================================
def make_panel():
    S = 24
    T = [K, ST3, ST2, D1, ST1, K]       # rings 0..5 on the top / left sides: lit bevel, groove
    B = [K, ST1, ST2, D1, ST3, K]       # bottom / right sides
    M = [K, ST2, ST2, D1, ST2, K]       # mitre where a lit side meets a shaded one
    img = new(S, S)
    for y in range(S):
        for x in range(S):
            ring = min(x, y, S - 1 - x, S - 1 - y)
            if ring >= len(T):
                c = PANEL_FILL
            else:
                lo, hi = ring, S - 1 - ring
                on_tl = x == lo or y == lo
                on_br = x == hi or y == hi
                c = M[ring] if (on_tl and on_br) else T[ring] if on_tl else B[ring]
            put(img, x, y, c)
    block = grid([                      # raised corner block with a gold stud
        '.kkkkk.',
        'klLLLSk',
        'kLyYOsk',
        'kLYWOsk',
        'kLOOosk',
        'kSssssk',
        '.kkkkk.',
    ], {'k': K, 'l': ST4, 'L': ST3, 'S': ST2, 's': ST1,
        'y': GO0, 'Y': GO1, 'O': GO2, 'o': GO3, 'W': WHITE})
    for (bx, by) in [(0, 0), (S - 7, 0), (0, S - 7), (S - 7, S - 7)]:
        paste(img, block, bx, by)
    for (x, y) in [(0, 0), (S - 1, 0), (0, S - 1), (S - 1, S - 1)]:
        img[y, x] = 0
    return img


# ==========================================================================
# 15. flask.png  (10x12 cells; row 0 glass, row 1 liquid masks)
#     The game fills a mask from the bottom up with the liquid colour and draws
#     the glass on top.  'i' = fillable interior (transparent glass, white mask),
#     'w' / 'b' = highlights drawn over the liquid (also part of the mask).
# ==========================================================================
FLASKS = [
    [   # round-bottom flask
        '...kkkk...',
        '...kCck...',
        '..kkcckk..',
        '...kiik...',
        '..kwiiik..',
        '.kwiiiiik.',
        'kwiiiiiibk',
        'kwiiiiiiik',
        'kiiiiiiibk',
        'kiiiiiiibk',
        '.kiiiiibk.',
        '..kkkkkk..',
    ],
    [   # tall bottle
        '...kkkk...',
        '...kCck...',
        '...kcck...',
        '...kiik...',
        '..kwiiik..',
        '..kwiibk..',
        '..kwiiik..',
        '..kwiiik..',
        '..kiiiik..',
        '..kiiibk..',
        '..kiiibk..',
        '..kkkkkk..',
    ],
    [   # small square vial
        '..........',
        '..........',
        '...kkkk...',
        '...kCck...',
        '..kkcckk..',
        '.kwwiiibk.',
        '.kwiiiiik.',
        '.kwiiiiik.',
        '.kiiiiiik.',
        '.kiiiiibk.',
        '.kiiiiibk.',
        '.kkkkkkkk.',
    ],
]


def make_flask():
    sheet = new(30, 24)
    glass_pal = {'k': K, 'C': EA0, 'c': EA1, 'w': WHITE, 'b': WA0}
    for i, rows in enumerate(FLASKS):
        assert len(rows) == 12 and all(len(r) == 10 for r in rows), i
        paste(sheet, grid([r.replace('i', '.') for r in rows], glass_pal), i * 10, 0)
        mask = [''.join('M' if ch in 'iwb' else '.' for ch in r) for r in rows]
        paste(sheet, grid(mask, {'M': WHITE}), i * 10, 12)
    return sheet


# ==========================================================================
# previews
# ==========================================================================
def preview(img, path, cw=None, ch=None, scale=8, gap=4, cols=None, bg=(40, 40, 44), cellbg=(52, 52, 58)):
    h, w = img.shape[:2]
    cw = cw or w
    ch = ch or h
    cells = [(x, y) for y in range(h // ch) for x in range(w // cw)]
    cols = cols or (w // cw)
    rows = (len(cells) + cols - 1) // cols
    PW = cols * cw * scale + (cols + 1) * gap
    PH = rows * ch * scale + (rows + 1) * gap
    canvas = Image.new('RGB', (PW, PH), bg)
    src = Image.fromarray(finalize(img), 'RGBA')
    for i, (gx, gy) in enumerate(cells):
        cell = src.crop((gx * cw, gy * ch, gx * cw + cw, gy * ch + ch)).resize((cw * scale, ch * scale), Image.NEAREST)
        px = gap + (i % cols) * (cw * scale + gap)
        py = gap + (i // cols) * (ch * scale + gap)
        canvas.paste(cellbg, (px, py, px + cw * scale, py + ch * scale))
        canvas.paste(cell, (px, py), cell)
    canvas.save(path)


def nine_slice(src, w, h, m=8):
    """Stretch a nine-slice texture to w x h (nearest), like Godot's StyleBoxTexture."""
    def idx(n, size):
        mid = size - 2 * m
        return (list(range(m)) + [m + (i * mid) // (n - 2 * m) for i in range(n - 2 * m)]
                + list(range(size - m, size)))
    return src[np.ix_(idx(h, src.shape[0]), idx(w, src.shape[1]))].copy()


def fill_flask(sheet, idx, frac, col):
    """Flask idx filled like the game does it: mask rows from the bottom up, glass on top."""
    glass = sheet[0:12, idx * 10:idx * 10 + 10]
    mask = sheet[12:24, idx * 10:idx * 10 + 10, 3] > 0
    rows = np.nonzero(mask.any(axis=1))[0]
    level = rows.max() + 1 - int(round(frac * (rows.max() - rows.min() + 1)))
    img = new(10, 12)
    img[level:][mask[level:]] = rgb(col)
    paste(img, glass, 0, 0)
    return img


LIQUIDS = ['#4aa3df', '#ff8a1f', '#ff6bc1']           # water, lava, pink


def mock_window(assets):
    """The panel stretched to 200x120 holding spell cards in slots and the UI controls."""
    font, ui, slot, icons = assets['font'], assets['ui_controls'], assets['slot'], assets['spell_icons']
    img = new(220, 132)
    img[:, :] = rgb('#2a2433')
    ox, oy = 10, 6
    paste(img, nine_slice(assets['panel'], 200, 120), ox, oy)
    paste(img, render_text(font, 'Loitsut', color=(232, 224, 208)), ox + 9, oy + 6)
    paste(img, ui[:, 60:70], ox + 183, oy + 7)                      # close
    for i in range(24):
        sx, sy = ox + 10 + (i % 8) * 22, oy + 22 + (i // 8) * 22
        frame = 1 if i == 3 else 2 if i >= 22 else 0
        paste(img, slot[:, frame * 20:frame * 20 + 20], sx, sy)
        if i < 22:
            paste(img, icons[(i // 8) * 16:(i // 8) * 16 + 16, (i % 8) * 16:(i % 8) * 16 + 16], sx + 2, sy + 2)
        elif i == 23:
            paste(img, ui[:, 70:80], sx + 5, sy + 5)                # padlock
    y0 = oy + 91
    for k, (label, cell) in enumerate([('Ääni', 0), ('Tärinä', 1)]):
        paste(img, ui[:, cell * 10:cell * 10 + 10], ox + 10, y0 + k * 12)
        paste(img, render_text(font, label, color=(232, 224, 208)), ox + 21, y0 + k * 12 - 2)
    for k, (fill, grab) in enumerate([(30, 2), (14, 3)]):          # HSlider like the theme draws it
        sx, sy = ox + 64, y0 + 3 + k * 12
        for x in range(56):
            for y in range(4):
                edge = y in (0, 3) or x in (0, 55)
                put(img, sx + x, sy + y, '#5a4a6e' if edge else (GO2 if k == 0 else GO1) if x < fill else K)
        paste(img, ui[:, grab * 10:grab * 10 + 10], sx + fill - 4, sy - 3)
    paste(img, ui[:, 40:50], ox + 52, y0 + 12)
    paste(img, ui[:, 50:60], ox + 122, y0 + 12)
    for k, frac in enumerate([0.3, 0.7, 1.0]):
        paste(img, fill_flask(assets['flask'], k, frac, LIQUIDS[k]), ox + 150 + k * 12, y0 + 2)
    return img


def mock_flasks(flask):
    """Every flask x liquid at 0 / 30 / 70 / 100 %."""
    img = new(3 * 52, 3 * 14)
    img[:, :] = rgb('#1c1626')
    for idx in range(3):
        for li, col in enumerate(LIQUIDS):
            for fi, frac in enumerate([0.0, 0.3, 0.7, 1.0]):
                paste(img, fill_flask(flask, idx, frac, col), idx * 52 + fi * 12 + 2, li * 14 + 1)
    return img


def write_previews(outdir, assets):
    os.makedirs(outdir, exist_ok=True)
    p = lambda n: os.path.join(outdir, n)
    preview(assets['spell_icons'], p('spell_icons.png'), 16, 16)
    preview(assets['spell_icons'], p('spell_icons_3x.png'), 16, 16, scale=3, gap=2,
            bg=(18, 13, 26), cellbg=(18, 13, 26))
    preview(assets['ui_controls'], p('ui_controls.png'), 10, 10)
    preview(assets['panel'], p('panel.png'))
    preview(assets['flask'], p('flask.png'), 10, 12)
    window = mock_window(assets)
    preview(window, p('mock_window_8x.png'), scale=8)
    preview(window, p('mock_window_3x.png'), scale=3)
    preview(mock_flasks(assets['flask']), p('mock_flasks_8x.png'), scale=8)
    preview(assets['projectiles'], p('projectiles.png'), 12, 12)
    preview(assets['explosion'], p('explosion.png'), 32, 32, cols=4)
    preview(assets['slash'], p('slash.png'), 32, 32)
    preview(assets['portal'], p('portal.png'), 24, 32, cols=4)
    preview(assets['fx_small'], p('fx_small.png'), 8, 8)
    preview(assets['items'], p('items.png'), 12, 12)
    preview(assets['ui'], p('ui.png'), 8, 8, cols=6)
    preview(assets['slot'], p('slot.png'), 20, 20)
    preview(assets['crosshair'], p('crosshair.png'))
    preview(assets['logo'], p('logo.png'), scale=6)
    preview(assets['font'], p('font_atlas.png'), scale=8)
    sample = 'Veleho — Hämyluolat: Löysit Liekkisauvan! ÄÖÅ äöå 0123456789 (Kipinä x3) Elämä 100/100'
    wrapped = 'Veleho — Hämyluolat:\nLöysit Liekkisauvan!\nÄÖÅ äöå 0123456789\n(Kipinä x3) Elämä 100/100'
    preview(render_text(assets['font'], wrapped), p('font_sample_8x.png'), scale=8)
    preview(render_text(assets['font'], sample), p('font_sample_3x.png'), scale=3)
    preview(render_text(assets['font'], CHARSET[:55] + '\n' + CHARSET[55:]), p('font_charset_4x.png'), scale=4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--preview', help='also write enlarged previews into this directory')
    args = ap.parse_args()

    assets = {
        'projectiles': make_projectiles(),
        'explosion': make_explosion(),
        'slash': make_slash(),
        'portal': make_portal(),
        'fx_small': make_fx_small(),
        'items': make_items(),
        'ui': make_ui(),
        'slot': make_slot(),
        'crosshair': make_crosshair(),
        'logo': make_logo(),
        'font': make_font(),
        'spell_icons': make_spell_icons(),
        'ui_controls': make_ui_controls(),
        'panel': make_panel(),
        'flask': make_flask(),
    }
    expect = {'projectiles': (48, 156), 'explosion': (256, 32), 'slash': (128, 32), 'portal': (192, 32),
              'fx_small': (32, 24), 'items': (48, 48), 'ui': (96, 8), 'slot': (60, 20),
              'crosshair': (11, 11), 'logo': (200, 48), 'font': (128, 84),
              'spell_icons': (128, 48), 'ui_controls': (80, 10), 'panel': (24, 24), 'flask': (30, 24)}
    for k, (w, h) in expect.items():
        assert assets[k].shape[:2] == (h, w), (k, assets[k].shape)
    for k in expect:
        if k != 'font':
            save(assets[k], os.path.join(SPRITES, k + '.png'))
    save(assets['font'], os.path.join(FONTS, 'pixel_font.png'))
    with open(os.path.join(FONTS, 'pixel_font_charset.txt'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(CHARSET)
    if args.preview:
        write_previews(args.preview, assets)
    print('wrote %d sprite sheets + font' % (len(expect) - 1))


if __name__ == '__main__':
    main()
