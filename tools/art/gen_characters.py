#!/usr/bin/env python3
"""Veleho character sprite-sheet generator.

Every frame is defined in this file as an ASCII-art grid (one character per
pixel, '.' = transparent) plus a per-sprite palette dict.  Running the script
writes the sheets into ``assets/sprites/``:

    python tools/art/gen_characters.py                  # write the PNGs
    python tools/art/gen_characters.py --preview DIR    # + enlarged previews
    python tools/art/gen_characters.py --only player,golem   # subset
    python tools/art/gen_characters.py --only boss --preview DIR   # just the boss

Conventions
-----------
* The frames of one animation row are written side by side in one text block,
  separated by spaces, so a whole cycle can be read (and edited) at a glance.
* '#' is the outline colour: #140c1c, unless a sheet overrides it (the
  tintable slime uses a grey #3a3640 outline).
* Sprites with ``outline=True`` get an automatic 1px outline: every transparent
  pixel that touches a body pixel orthogonally becomes '#'.  So frames may be
  drawn as bare shapes; explicitly drawn '#' pixels are kept as they are.
  Characters listed in a sprite's ``fx`` string are emissive (sparkles, embers,
  smoke, glows) and never receive an outline.
* Output pixels are fully opaque or fully transparent (alpha 0/255 only).
* The 48x48 boss has too many independently moving parts for whole-frame
  strips: its parts are ASCII art and code places them per frame (see BOSS).
"""
import argparse
import math
import os

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.join(ROOT, "assets", "sprites")

# --------------------------------------------------------------------------
# Shared colours
# --------------------------------------------------------------------------
C = dict(
    outline="#140c1c",
    dk1="#2a1e36", dk2="#3b2d4f", dk3="#54426a",
    teal0="#1d3b4a", teal1="#2a5a6b", teal2="#3f8090", teal3="#6fb3b8",
    ind0="#262b5c", ind1="#3a4796",
    scarf0="#8a2c22", scarf1="#c8462e", scarf2="#ef7d3c",
    amber0="#ffb43a", amber1="#ffd36b",
    lea0="#6b4430", lea1="#8f5d3b", lea2="#b07a4f",
    stone0="#3d3a45", stone1="#5c5866", stone2="#858091", stone3="#b3afbd",
    moss0="#3e6b2f", moss1="#6a9c3c",
    cyan0="#49e0e8", cyan1="#b8fbff",
    fire0="#fff3b0", fire1="#ffd04a", fire2="#ff8a1f", fire3="#d9421b", fire4="#8c1c12",
    crim0="#3a0f17", crim1="#6b1a26", crim2="#a32b35",
    bone0="#efe6d2", bone1="#c2b59b",
    vio0="#d7b0ff", vio1="#9a5cf0", vio2="#5a2fb0",
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def strip(text, w, h):
    """Parse a block of side-by-side frames into a list of frames (lists of rows)."""
    lines = [ln.split() for ln in text.strip("\n").splitlines() if ln.strip()]
    if len(lines) != h:
        raise ValueError(f"strip has {len(lines)} lines, expected {h}")
    n = len(lines[0])
    frames = [[] for _ in range(n)]
    for y, parts in enumerate(lines):
        if len(parts) != n:
            raise ValueError(f"line {y}: {len(parts)} frames, expected {n}")
        for i, p in enumerate(parts):
            if len(p) != w:
                raise ValueError(f"line {y} frame {i}: width {len(p)}, expected {w}: {p!r}")
            frames[i].append(p)
    return frames


def add_outline(frame, fx=""):
    h, w = len(frame), len(frame[0])
    g = [list(r) for r in frame]

    def body(x, y):
        if 0 <= x < w and 0 <= y < h:
            c = frame[y][x]
            return c not in ".#" and c not in fx
        return False

    for y in range(h):
        for x in range(w):
            if g[y][x] == "." and (body(x - 1, y) or body(x + 1, y) or body(x, y - 1) or body(x, y + 1)):
                g[y][x] = "#"
    return ["".join(r) for r in g]


def hex_rgba(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def frame_image(frame, pal):
    h, w = len(frame), len(frame[0])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(frame):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            if ch not in pal:
                raise KeyError(f"char {ch!r} not in palette")
            px[x, y] = hex_rgba(pal[ch])
    return img


class Sheet:
    def __init__(self, name, fw, fh, cols, rows, pal, anims, fx="", outline=True,
                 outline_color=None):
        self.name, self.fw, self.fh, self.cols, self.rows = name, fw, fh, cols, rows
        self.pal = dict(pal)
        self.pal["#"] = outline_color or C["outline"]
        self.fx = fx
        self.outline = outline
        self.anims = anims  # list of (label, [frames]) in row order

    def frames(self):
        out = []
        for label, frames in self.anims:
            row = []
            for f in frames:
                if len(f) != self.fh or any(len(r) != self.fw for r in f):
                    raise ValueError(f"{self.name}/{label}: bad frame size")
                row.append(add_outline(f, self.fx) if self.outline else f)
            out.append((label, row))
        return out

    def build(self):
        img = Image.new("RGBA", (self.fw * self.cols, self.fh * self.rows), (0, 0, 0, 0))
        anims = self.frames()
        if len(anims) > self.rows:
            raise ValueError(f"{self.name}: too many rows")
        for r, (label, frames) in enumerate(anims):
            if len(frames) > self.cols:
                raise ValueError(f"{self.name}/{label}: too many frames")
            for c, f in enumerate(frames):
                img.paste(frame_image(f, self.pal), (c * self.fw, r * self.fh))
        return img


# --------------------------------------------------------------------------
# PLAYER  "Veleho"  16x16, 6 cols x 7 rows, faces right
# Shoulder pivot for the separately drawn arm: (8, 8).
# --------------------------------------------------------------------------
PLAYER_PAL = {
    "x": C["dk1"], "X": C["dk2"], "k": C["dk3"],
    "1": C["teal0"], "2": C["teal1"], "3": C["teal2"], "4": C["teal3"],
    "i": C["ind0"], "I": C["ind1"],
    "r": C["scarf0"], "s": C["scarf1"], "S": C["scarf2"],
    "e": C["amber1"], "E": C["amber0"],
    "c": C["cyan0"], "C": C["cyan1"],
    "a": C["stone0"], "A": C["stone1"], "g": C["stone2"],
    "f": C["fire2"], "F": C["fire1"], "d": C["fire3"], "w": C["fire0"],
    "l": C["lea0"], "L": C["lea1"], "b": "#c9953e",
    "q": C["stone2"], "Q": C["stone3"], "y": C["amber1"],
}
PLAYER_FX = "cCEwFfqQy"

P_IDLE = strip("""
................ ................ ................ ................
................ ................ ...44443........ ...44443........
...44443........ ...44443........ ....4444333..... ....4444333.....
....4444333..... ....4444333..... .....443xxxx.... .....443xxxx....
.....443xxxx.... .....443xxxx.... .....432xexe.... .....432xexe....
.....432xexe.... .....432xexe.... .....322xxxx.... .....322xxxx....
.....322xxxx.... .....322xxxx.... ....rSSSSssr.... ....rSSSSssr....
....rSSSSssr.... ....rSSSSssr.... ..SSs.433322.... ...Ss.433322....
..SSs.433322.... .SSSs.433322.... .Ssr..433322.... ..Ssr.433322....
.Ssr..433222.... .Ssr..433222.... .sr...433222.... .Ssr..433222....
.sr...lLllbl.... ..r...lLllbl.... .r....lLllbl.... .s....lLllbl....
.r...4333222.... .....4333222.... .....4333222.... .....4333222....
....443332222... ....443332222... ....443332222... ....443332222...
...4432222211... ...4432222211... ...4432222211... ...4432222211...
.....kX..kXX.... .....kX..kXX.... .....kX..kXX.... .....kX..kXX....
................ ................ ................ ................
""", 16, 16)

P_WALK = strip("""
................ ................ ................ ................ ................ ................
................ ................ ...44443........ ................ ................ ...44443........
...44443........ ...44443........ ....4444333..... ...44443........ ...44443........ ....4444333.....
....4444333..... ....4444333..... .....443xxxx.... ....4444333..... ....4444333..... .....443xxxx....
.....443xxxx.... .....443xxxx.... .....432xexe.... .....443xxxx.... .....443xxxx.... .....432xexe....
.....432xexe.... .....432xexe.... .....322xxxx.... .....432xexe.... .....432xexe.... .....322xxxx....
.....322xxxx.... .....322xxxx.... ....rSSSSssr.... .....322xxxx.... .....322xxxx.... ....rSSSSssr....
..SSrSSSSssr.... ...SrSSSSssr.... ..SSs.433322.... ..SSrSSSSssr.... ...SrSSSSssr.... ..SSs.433322....
.Ssrr.433322.... .SSsr.433322.... .Ssr..433222.... .Ssrr.433322.... .SSsr.433322.... .Ssr..433222....
.r....433222.... .sr...433222.... .r....lLllbl.... .r....433222.... .sr...433222.... .r....lLllbl....
......lLllbl.... ......lLllbl.... .....4333222.... ......lLllbl.... ......lLllbl.... .....4333222....
.....4333222.... .....4333222.... .....4333222.... .....4333222.... .....4333222.... .....4333222....
....443332222... ....443332222... ....44332222.... ....443332222... ....443332222... ....44332222....
...4432222221... ....443222221... ....43222221.... ...4432222221... ....443222221... ....43222221....
...xX.....kXX... ....xX...kXX.... ......kXX....... ...kX.....xXX... ....kX...xXX.... ......xXX.......
................ ................ ................ ................ ................ ................
""", 16, 16)

P_JUMP = strip("""
................ ................
...44443........ ...44443........
....4444333..... ....4444333.....
.....443xxxx.... .....443xxxx....
.....432xexe.... .....432xexe....
.....322xxxx.... .....322xxxx....
....rSSSSssr.... ....rSSSSssr....
...Ss.433322.... ..SSs.433322....
..Ssr.433222.... .Ssr..433222....
..sr..lLllbl.... .sr...lLllbl....
..s...4333222... .r...43332222...
..r...4333222... .....43332222...
......433222.... .....4332222....
.......3221..... .....4322221....
........21...... ......kX.kX.....
................ ................
""", 16, 16)

P_FALL = strip("""
................ ................
..S..4.......... .S...4..........
..Ss.4443....... .Ss..4443.......
..sr.444333..... ..sr.444333.....
..sr.443xxxx.... ..sr.443xxxx....
...r.432xexe.... ..r..432xexe....
...r.322xxxx.... ...r.322xxxx....
...rrSSSSssr.... ...rrSSSSssr....
..4...433322..3. ......433322....
..44..433222.32. ..4...433222..3.
..344.lLllbl322. ..44..lLllbl.32.
...3443332222i2. ..3443332222i22.
...iiIIIIIIIii.. ..iiIIIIIIIIii..
......XX..XX.... ......XX.XX.....
......kX..kX.... ......kX.kX.....
................ ................
""", 16, 16)

P_LEVITATE = strip("""
................ ................ ................ ................
................ ...44443........ ...44443........ ................
...44443........ ....4444333..... ....4444333..... ...44443........
....4444333..... .....443xxxx.... .....443xxxx.... ....4444333.....
.....443xxxx.... .....432xexe.... .....432xexe.... .....443xxxx....
.....432xexe.... .....322xxxx.... .....322xxxx.... .....432xexe....
.....322xxxx.... ...SrSSSSssr.... ..SSrSSSSssr.... .....322xxxx....
..SSrSSSSssr.... .SSsr.433322.... .Ssr..433322.... .SSSrSSSSssr....
.Ssr..433322.... .sr...433222.... .s....433222.... .sr...433322....
.r....433222.... ......lLllbl.... ......lLllbl.... .r....433222....
......lLllbl.... .....4333222.... .....4333222.... ......lLllbl....
.....4333222.... ...I443332222I.. ...I443332222I.. .....4333222....
...I443332222I.. ..iI432222221Ii. ..iI432222221Ii. ...I443332222I..
..iI432222221Ii. ......kX.kX..... ......kX.kX..... ..iI432222221Ii.
......kX.kX..... ........C....... ......y...c..... ......kX.kX.....
....C...y...c... ...y.......c.... ....C.......y... ...c..C...y.....
""", 16, 16)

P_HURT = strip("""
................ ................
..44443......... ................
...4444333...... ..44443.........
....443xxxx..... ...4444333......
....432EEEx..... ....443xxxx.....
....322xxxx..... ....432xexe.....
...rSSSSssr..... ....322xxxx.....
.SSs.4433322.... ..SrSSSSssr.....
.sr..4333222.... .Ssr.4433322....
.r...lLllbl..... .sr..4333222....
.....43332222... .r....lLllbl....
.....443332222.. ......4333222...
.....4432222221. .....44332222...
.....4322222211. ....4432222211..
......kX...kXX.. .....kX...kXX...
................ ................
""", 16, 16)

P_DEATH = strip("""
................ ................ ................ ................ ................ ................
................ ................ ................ ................ ................ ................
................ ................ ........q....... ................ ................ ................
...44443........ ................ .....Q.......... .......q........ ................ ................
....4444333..... ................ .......q...Q.... ..........F..... ................ ................
.....4433xxx.... ....44443....... .....qAg........ ....q........... ......Q......... ................
.....432xExx.... .....4444333.... .....AgAAgA..... ........q..f.... ...........q.... ................
.....3222xxx.... ......4433xxx... ......AfdAf..... ................ ....F........... ................
...rrSSSSssr.... ......432xExx... ......4d2xExx... ................ .........f...... ................
..Ssr.433322.... ......3222xxx... ......3222xxx... .......gAg...... ................ ................
.Sr...lLllbl.... ....rrSSSSssr... ....rrSSSSssr... .....gAAAAAg.... .......q........ ................
.r...4333222.... ..SSs.4333322... ..SSs.4333322... ...rAgAAfAAAA... ................ ................
....443332222... .Sr..443332222.. .Sr..443332222.. .SsAAAgAAAdAAA.. .......gAg...... ........F.......
...4432222211... ...443332222221. ...443332222221. ...44AAfAAAA221. .....gAAfAAg.... .......gA.......
.....kX..kXX.... ..4432222222211. ..4432222222211. ..443222222221.. ...aAAAAAAdAAa.. .....aAfAAa.....
................ ................ ................ ................ ................ ................
""", 16, 16)

PLAYER = Sheet("player", 16, 16, 6, 7, PLAYER_PAL, [
    ("idle", P_IDLE),
    ("walk", P_WALK),
    ("jump", P_JUMP),
    ("fall", P_FALL),
    ("levitate", P_LEVITATE),
    ("hurt", P_HURT),
    ("death", P_DEATH),
], fx=PLAYER_FX)

# Arm: sleeve from the shoulder (pivot pixel (1,2)) to the glove at x=6..7.
P_ARM = strip("""
........
.33334Ll
.22223ll
........
""", 8, 4)

PLAYER_ARM = Sheet("player_arm", 8, 4, 1, 1, PLAYER_PAL, [("arm", P_ARM)], fx=PLAYER_FX)


# --------------------------------------------------------------------------
# SLIME  16x12, 4 cols x 3 rows.  Light greyscale so the game can tint it.
# --------------------------------------------------------------------------
SLIME_PAL = {
    "W": "#ffffff", "w": "#dcdcdc", "g": "#b4b4b4", "m": "#8c8c8c", "d": "#6a6a6a",
    "K": "#25222a",
}

S_IDLE = strip("""
................ ................ ................ ................
................ ................ ................ ................
................ ................ ................ ................
................ ................ ................ ......wwgg......
.....wwwwgg..... ................ .....wwwwgg..... ....wWWwwwgg....
....wWWwwwgg.... ....wwwwwwgg.... ....wWWwwwgg.... ...wWwwwwwwgg...
...wWwwwwwwgg... ..wWWwwwwwwggg.. ...wWwwwwwwgg... ...wwwwwKwwKg...
..wwwwwwKwwKgg.. .wWwwwwwKwwKggg. ..wwwwwwKwwKgg.. ...wwwwwKwwKg...
..wwwwwwKwwKgm.. .wwwwwwwKwwKggm. ..wwwwwwKwwKgm.. ...wwwwwwwwgm...
..gwwwwwwwwggm.. .gwwwwwwwwwwggm. ..gwwwwwwwwggm.. ...gwwwwwwggm...
...gggggggmmd... ..gggggggggmmd.. ...gggggggmmd... ....gggggmmd....
................ ................ ................ ................
""", 16, 12)

S_HOP = strip("""
................ ................ ................ ................
................ .......wg....... .....wwwwgg..... ................
................ ......wWwg...... ....wWWwwwgg.... ................
................ .....wWwwgg..... ...wWwwwwwwgg... ................
................ .....wwwwgg..... ..wwwwwwKwwKgg.. ................
................ .....wwKwKg..... ..wwwwwwKwwKgm.. ................
...wwwwwwwggg... .....wwKwKg..... ..gwwwwwwwwggm.. ................
.wWWwwwwKwwKggg. .....wwwwgm..... ...ggwwwwwggm... ....wwwwwwwgg...
.wWwwwwwKwwKggm. .....gwwwgm..... ....gggggmmd.... .wWWwwwwKwwKggg.
.gwwwwwwwwwwggm. ......wwgm...... ................ .wWwwwwwKwwKggm.
..ggggggggggmd.. ......ggmd...... ................ .ggggggggggggmd.
................ ................ ................ ................
""", 16, 12)

S_DEATH = strip("""
................ ................ ................ ................
................ ................ ................ ................
................ ..w..........w.. ................ ................
................ ................ ................ ................
................ ...w........w... ................ ................
....wwwwwwgg.... ................ ................ ................
..wWWwwwwwwggg.. ................ ..w..........w.. ................
.wWwwwwKKwKKggg. ................ ................ ................
.wwwwwwwwwwwggm. ....wwwwwwwgg... ................ ................
.gwwwwwwwwwwggm. .wWwwwKKwKKwggm. ...wwwwwwwwggg.. ................
..gggggggggmmd.. .gggggggggggggm. .wWwwwKKwKKwwgm. ....wWwwwwwgm...
................ ................ ................ ................
""", 16, 12)

SLIME = Sheet("slime", 16, 12, 4, 3, SLIME_PAL, [
    ("idle", S_IDLE),
    ("hop", S_HOP),
    ("death", S_DEATH),
], outline_color="#3a3640")


# --------------------------------------------------------------------------
# BAT  "Siipio"  16x12, 4 cols x 2 rows, front view, centred.
# --------------------------------------------------------------------------
BAT_PAL = {
    "h": "#46303f", "f": "#6b4a59", "F": "#93707a",
    "n": "#36223e", "m": "#553359", "M": "#774a74", "b": "#b08a98",
    "E": "#ff3d3d", "w": C["bone0"], "K": C["crim1"],
}

B_FLY = strip("""
................ ................ ................ ................
.b............b. ................ .....F....F..... ................
.Mb..F....F..bM. .....F....F..... .....Ff..fF..... .b...F....F...b.
.MMb.Ff..fF.bMM. .....Ff..fF..... ....bffffffb.... .Mbb.Ff..fF.bbM.
..mMbffffffbMm.. .bbbbffffffbbbb. ...bMfEffEfMb... .mMMbffffffbMMm.
..nmMfEffEfMmn.. .MMMMfEffEfMMMM. ..bMmfhwwhfmMb.. ..nmMfEffEfMmn..
...nmfhwwhfmn... .mmmmfhwwhfmmmm. .bMmn.ffff.nmMb. ...n.fhwwhf.n...
....n.ffff.n.... .n.nm.ffff.mn.n. .bmn..hffh..nmb. ......ffff......
......hffh...... ......hffh...... .bn....hh....nb. ......hffh......
.......hh....... .......hh....... ..n..........n.. .......hh.......
................ ................ ................ ................
................ ................ ................ ................
""", 16, 12)

B_DEATH = strip("""
................ ................ ................ ................
................ ................ ................ ................
................ ................ ................ ................
.....F....F..... ................ ................ ................
....bFf..fFb.... ................ ................ ................
...bMffffffMb... .......hh....... ................ ................
...MmfKffKfmM... ......hffh...... ................ ................
...nmfhwwhfmn... ...n.ffffff.n... ................ ................
....n.ffff.n.... ...mMfKffKfMm... ......F..F...... ................
......hffh...... ....bFf..fFb.... ...nbMfffffMbn.. ................
.......hh....... .....F....F..... ..nmMmfKffKfmMm. ................
................ ................ ................ ................
""", 16, 12)

BAT = Sheet("bat", 16, 12, 4, 2, BAT_PAL, [
    ("fly", B_FLY),
    ("death", B_DEATH),
])


# --------------------------------------------------------------------------
# WISP  "Tulihenki"  12x12, 4 cols x 2 rows.  Emissive: no outline.
# --------------------------------------------------------------------------
WISP_PAL = {
    "w": C["fire0"], "y": C["fire1"], "o": C["fire2"], "r": C["fire3"], "R": C["fire4"],
    "K": C["crim0"], "s": C["stone1"], "S": C["stone0"], "z": C["stone2"], "Z": C["stone3"],
}

W_FLOAT = strip("""
......r..... .....r...... .......r.... .....r......
.....rr..... ....rr...... ......rr.... ....rr.r....
....roor.r.. ..r.roor.... ....roor.r.. ...rroorr...
...royyor... ...royyor... ..r.royyor.. ...royyor...
..royywyor.. ..royywyor.. ..royywyor.. ..royywyor..
..roywwyor.. ..roywwyor.. ..roywwyor.. ..roywwyor..
.royKwwKyor. .royKwwKyor. .royKwwKyor. .royKwwKyor.
.royKwwKyor. .royKwwKyor. .royKwwKyor. .royKwwKyor.
.royywwyyor. .royywwyyor. .royywwwyor. .royywwyyor.
..royyyyor.. ..royyyyor.. ..royyyyor.. ..royyyyor..
...rrooorr.. ...rrooorR.. ...rRooorr.. ...rrooorr..
....RrrR.... ....RrrR.... ....RrrR.... ....RrrR....
""", 12, 12)

W_DEATH = strip("""
...r..r..r.. ....s..s.... ...sz..zs... ..z.....s...
...rr.rr.r.. ...s....s... ..szs.ssz... ...s...z....
..rooroor... .....ss..... ...ss..ss... ....s...s...
..royyyyor.. ....s..s.... ....s....... ...s........
.royywwyyor. ...r.rr.r... .....ss..... ....z.s.....
.roywwwwyor. ...roooor... ....szzs.... .....s......
.rywwwwwwyr. ..rooyyoor.. ...sssSss... ............
.royKwwKyor. ..roKyyKor.. ....SssS.... ............
.royywwyyor. ..rooyyoor.. .....rR..... ............
..royyyyor.. ...rooooR... ......o..... ............
...rrooorr.. ....RrrR.... ............ ............
....RrrR.... ............ ............ ............
""", 12, 12)

WISP = Sheet("wisp", 12, 12, 4, 2, WISP_PAL, [
    ("float", W_FLOAT),
    ("death", W_DEATH),
], outline=False)

# --------------------------------------------------------------------------
# CASTER  "Varjomaagi"  16x18, 5 cols x 4 rows, faces right, feet on y=17.
# The gnarled staff (red gem on top) is part of the sprite, held in front.
# --------------------------------------------------------------------------
CASTER_PAL = {
    "k": "#1c1020", "r": C["crim0"], "R": C["crim1"], "C": C["crim2"], "H": "#c9474a",
    "b": C["bone0"], "B": C["bone1"], "u": "#8a7d66",
    "n": "#46291e", "l": C["lea0"], "L": C["lea1"],
    "G": "#ff3b3b", "g": "#a3121f", "W": "#ffc2b8",
    "o": "#ff5a4a", "O": "#ffb0a0", "Y": C["fire0"],
}
CASTER_FX = "oOY"

K_IDLE = strip("""
................ ................
.....r.......... ....r........o..
.....Rr......W.. .....Rr......G..
.....CRr....GGg. .....CRr....GWg.
....CRRrk...ngn. ....CRRrk...ngn.
....CRkbbB...l.. ....CRkbbB...l..
....CRk#b#...L.. ....CRk#b#...L..
....RRkbbB...l.. ....RRkbbB...l..
....RrkkB....l.. ....RrkkB....l..
....CRrrRRr..L.. ....CRrrRRr..L..
....CRrrrRRRbl.. ....CRrrrRRRbl..
....CRrkrrr..l.. ....CRrkrrr..l..
...CRrrkrrrr.l.. ...CRrrkrrrr.l..
...CRrrkrrrr.l.. ...CRrrkrrrr.l..
...CRrkrrkrr.l.. ...CRrkrrkrr.l..
...C.Rk.rr.k.n.. ...CR.krr.kr.n..
...R..k..r...n.. ....R.k..r..rn..
................ ................
""", 16, 18)

K_WALK = strip("""
................ ................ ................ ................
.....r.......... .....Rr......W.. .....r.......... .....Rr......W..
.....Rr......W.. .....CRr....GGg. .....Rr......W.. .....CRr....GGg.
.....CRr....GGg. ....CRRrk...ngn. .....CRr....GGg. ....CRRrk...ngn.
....CRRrk...ngn. ....CRkbbB...l.. ....CRRrk...ngn. ....CRkbbB...l..
....CRkbbB...l.. ....CRk#b#...L.. ....CRkbbB...l.. ....CRk#b#...L..
....CRk#b#...L.. ....RRkbbB...l.. ....CRk#b#...L.. ....RRkbbB...l..
....RRkbbB...l.. ....RrkkB....l.. ....RRkbbB...l.. ....RrkkB....l..
....RrkkB....l.. ....CRrrRRr..L.. ....RrkkB....l.. ....CRrrRRr..L..
....CRrrRRr..L.. ....CRrrrRRRbl.. ....CRrrRRr..L.. ....CRrrrRRRbl..
....CRrrrRRRbl.. ....CRrkrrr..l.. ....CRrrrRRRbl.. ....CRrkrrr..l..
....CRrkrrr..l.. ....CRrkrrrr.l.. ....CRrkrrr..l.. ....CRrkrrrr.l..
...CRrrkrrrr.l.. ...CRrrkrrrr.l.. ...CRrrkrrrr.l.. ...CRrrkrrrr.l..
..CRrrkrrrrr.l.. ...CRrkrrkrr.l.. ..CRrrkrrrrr.l.. ...CRrkrrkrr.l..
..CRrkrrrkrr.l.. ...CRrkrrkr..l.. ..CRrkrrrkrr.l.. ...CRrkrrkr..l..
.CR.k.rr.kkk.n.. ...C.R.kr.r..n.. .CRk..rr.kr..n.. ...CR.krr..r.n..
.R..k..r..kk.n.. .......kk....n.. .kk...r...r..n.. ....R..kk....n..
................ ................ ................ ................
""", 16, 18)

K_CAST = strip("""
................ ................ ..............o.
.....r.......W.. .....r.....oOYOo .....r......o...
.....Rr.....GGg. .....Rr....OYYYO .....Rr......W..
.....CRr....ngn. .....CRr....OYO. .....CRr....GGg.
....CRRrk....l.. ....CRRrk...oOo. ....CRRrk...ngn.
....CRkbbB...L.. ....CRkbbB...L.. ....CRkbbB...l..
....CRk#b#...l.. ....CRkGbG...l.. ....CRk#b#...L..
....RRkbbB...l.. ....RRkbbB...l.. ....RRkbbB...l..
....RrkkB..bbL.. ....RrkkB..bbL.. ....RrkkB....l..
....CRrrRRRR.l.. ....CRrrRRRR.l.. ....CRrrRRr..L..
....CRrrrRr..l.. ....CRrrrRr..l.. ....CRrrrRRRbl..
....CRrkrrr..L.. ....CRrkrrr..L.. ....CRrkrrr..l..
...CRrrkrrrr.l.. ...CRrrkrrrr.l.. ...CRrrkrrrr.l..
...CRrrkrrrr.l.. ...CRrrkrrrr.l.. ...CRrrkrrrr.l..
...CRrkrrkrr.l.. ...CRrkrrkrr.l.. ...CRrkrrkrr.l..
...C.Rk.rr.k.n.. ...C.Rk.rr.k.n.. ...C.Rk.rr.k.n..
...R..k..r...... ...R..k..r...... ...R..k..r...n..
................ ................ ................
""", 16, 18)

K_DEATH = strip("""
................ ................ ................ ................ ................
....r........... .............W.. ................ ................ ................
....Rr.......W.. ............Gg.. ................ ................ ................
....CRr.....GGg. ............n... ................ ................ ................
...CRRrk....ngn. ...........l.... ................ ................ ................
...CRkbbB....l.. ...........l.... ................ ................ ................
...CRk#b#....L.. .....r....l..... ................ ................ ................
...RRkbbB....l.. .....Rr...L..... ................ ................ ................
...RrkkB.....l.. ....CRRrkl...... ................ ................ ................
....CRrrRRr..L.. ....CRkbbB...... ................ ................ ................
....CRrrrRRRbl.. ....CRk#b#...... ......r......... ................ ................
....CRrkrrr..l.. ....RRkbbB...... .....CRr........ ................ ................
...CRrrkrrrr.l.. ...CRrkkB....... ....CRkbbB...... ................ ................
...CRrrkrrrr.l.. ...CRrrRRr...... ...CRRk#b#...... ......bbB....... ................
...CRrkrrkrr.l.. ..CRrrkrrrr..... ..CRrrkbbBr..... ....CR#b#R...... ....CRr.........
...C.Rk.rr.k.l.. .CRrrkrrkrrr.... .CRrrkrrkrrr.Gg. ..CRrrkrrkrr.Gg. ..CRrrkRr.bbBgg.
...R..k..r...n.. .R.k.rr.kr.k.... .RrkkrrkrRrnlLl. .CRrkkrrkrRnlLl. .CRrkkrrkr#b#lL.
................ ................ ................ ................ ................
""", 16, 18)

CASTER = Sheet("caster", 16, 18, 5, 4, CASTER_PAL, [
    ("idle", K_IDLE),
    ("walk", K_WALK),
    ("cast", K_CAST),
    ("death", K_DEATH),
], fx=CASTER_FX)

# --------------------------------------------------------------------------
# GOLEM  "Kivikolossi"  24x24, 5 cols x 4 rows, faces right, feet on y=23.
# --------------------------------------------------------------------------
GOLEM_PAL = {
    "a": "#2a2526", "s": "#463e3a", "S": "#675c53", "t": "#8a7d6e", "T": "#b0a28e",
    "m": "#4d7a33", "M": C["moss1"],
    "c": C["cyan0"], "C": C["cyan1"], "q": "#23707e",
    "u": "#9a8b78", "U": "#c9bca6",
}
GOLEM_FX = "cCquU"

G_IDLE = strip("""
........................ ........................
........................ ........................
........................ ........................
........................ ........................
............mMm......... ........................
....mMMm...mtTTm........ ....mMMm....mMm.........
...mtTTtm..tTttSS....... ...mtTTtm..mtTTm........
..mtTtttSs.tSSSSs....... ..mtTtttSs.tTttSS.......
..tTttSSSSaaaCaCa.mMm... ..tTttSSSSatSSSSs.mMm...
.sttSSSSSSasSSSsamtTtm.. .sttSSSSSSaaaCaCamtTtm..
.stSSaSSSSaaaaaasTttSSs. .stSSaSSSSasSSSsaTttSSs.
.sSSSSaSSSqcqSSSsattSSs. .sSSSSaSSScCcSSSsattSSs.
.sSSSSSaSqcCcqSSsaSSSSs. .sSSSSSaScCCCcSSsaSSSSs.
.sSsSSSSSSqcqSSssaSSSss. .sSsSSSSSScCcSSssaSSSss.
.ssaSSSSSSSSSaSsasSSSs.. .ssaSSSSSSSSSaSsasSSSs..
.sSsasSSSSSSaSsa.sSSSs.. .sSsasSSSSSSaSsa.sSSSs..
.sSs.assSSSSssa.tTtSSs.. .sSs.assSSSSssa.tTtSSs..
.tTts.asssssaa.tTttSSSs. .tTts.asssssaa.tTttSSSs.
.tSSs..sSSs.sSs.tSaSaSs. .tSSs..sSSs.sSs.tSaSaSs.
.sasa..tSSs.tSSs.sssss.. .sasa..tSSs.tSSs.sssss..
.......tSSs.tSSs........ .......tSSs.tSSs........
......ttSSs.tTSSs....... ......ttSSs.tTSSs.......
......sssss.ssssss...... ......sssss.ssssss......
........................ ........................
""", 24, 24)

G_WALK = strip("""
........................ ........................ ........................ ........................
........................ ........................ ........................ ........................
........................ ........................ ........................ ........................
............mMm......... ........................ ............mMm......... ........................
....mMMm...mtTTm........ ........................ ....mMMm...mtTTm........ ........................
...mtTTtm..tTttSS....... ............mMm......... ...mtTTtm..tTttSS....... ............mMm.........
..mtTtttSs.tSSSSs....... ....mMMm...mtTTm........ ..mtTtttSs.tSSSSs....... ....mMMm...mtTTm........
..tTttSSSSaaaCaCa.mMm... ...mtTTtm..tTttSS....... ..tTttSSSSaaaCaCa.mMm... ...mtTTtm..tTttSS.......
.sttSSSSSSasSSSsamtTtm.. ..mtTtttSs.tSSSSs....... .sttSSSSSSasSSSsamtTtm.. ..mtTtttSs.tSSSSs.......
.stSSaSSSSaaaaaasTttSSs. ..tTttSSSSaaaCaCa.mMm... .stSSaSSSSaaaaaasTttSSs. ..tTttSSSSaaaCaCa.mMm...
.sSSSSaSSSqcqSSSsattSSs. .sttSSSSSSasSSSsamtTtm.. .sSSSSaSSSqcqSSSsattSSs. .sttSSSSSSasSSSsamtTtm..
.sSSSSSaSqcCcqSSsaSSSSs. .stSSaSSSSaaaaaasTttSSs. .sSSSSSaSqcCcqSSsaSSSSs. .stSSaSSSSaaaaaasTttSSs.
.sSsSSSSSSqcqSSssaSSSss. .sSSSSaSSSqcqSSSsattSSs. .sSsSSSSSSqcqSSssaSSSss. .sSSSSaSSSqcqSSSsattSSs.
.ssaSSSSSSSSSaSsasSSSs.. .sSSSSSaSqcCcqSSsaSSSSs. .ssaSSSSSSSSSaSsasSSSs.. .sSSSSSaSqcCcqSSsaSSSSs.
.sSsasSSSSSSaSsa.sSSSs.. .sSsSSSSSSqcqSSssaSSSss. .sSsasSSSSSSaSsa.sSSSs.. .sSsSSSSSSqcqSSssaSSSss.
.sSs.assSSSSssastTtSSs.. .ssaSSSSSSSSSaSsasSSSs.. .sSs.assSSSSssa.tTtSSs.. .ssaSSSSSSSSSaSsasSSSs..
.tTts.asssssaaStTttSSSs. .sSsasSSSSSSaSsa.sSSSs.. .tTts.asssssaastTttSSSs. .sSsasSSSSSSaSsa.sSSSs..
.tSSs..sSSs..tSStSaSaSs. .sSs.assSSSSssastTtSSs.. .tSSs...tSSssSs.tSaSaSs. .sSs.assSSSSssa.tTtSSs..
.sasa..sSSs..tSSssssss.. .tTts.asssssaaStTttSSSs. .sasa...tSSssSs..sssss.. .tTts.asssssaastTttSSSs.
.......tSSs..tTSSs...... .tSSs..tSSs..tSStSaSaSs. .......ttSSstSSs........ .tSSs...tSSstSSstSaSaSs.
.......tSSs..ssssss..... .sasa..tSSs..tSSssssss.. .......ssssstSSs........ .sasaU..tSSstSSs.sssss..
......ttSSs............. ......ttSSs.utTSSs.u.... ............tTSSs....... .....u.ttSSstTSSs.......
......sssss............. ......sssssU.ssssss.U... ............ssssss...... ....U..sssssssssss......
........................ ........................ ........................ ........................
""", 24, 24)

G_ATTACK = strip("""
........................ ........................ ........................ ........................
........................ ...tTTt..........tTTt... ........................ ........................
........................ ..tTttSs........tTttSs.. ........................ ........................
..tTTt............tTTt.. ..tSaSaS........tSaSaS.. ........................ ........................
.tTttSs.....mMm..tTttSs. ...sSSs.....mMm..sSSs... ...................U.... ........................
.tSaSaSMm..mtTTm.tSaSaS. ...tSsMm...mtTTm.tSSs... .....mMm.....mMm....u... ........................
..sSSstm..tTttSS..sSSs.. ...mtTtm...tTttSStSSs... ....mtTtm...mtTTm....U.. ......mMm...............
..mtSStSs.tSSSSs..tSSs.. ..mtTtttSs.tSSSSstSSs... ...mtTtttSs.tTttSS...u.. .....mtTtm....mMm.......
..tTttSSSSaaaCaCa.tSSs.. ..tTttSSSSaaaCaCasSSs... ...tTttSSSSatSSSSs...... ....mtTtttSs.mtTTm......
...tSSSSSSasSSSsamtTtm.. ...tSSSSSSasSSSsamtTtm.. ...tttSSSSSaaaCaCa.mMm.. ....tTttSSSSStTttSS.....
...tSaSSSSaaaaaasTttSSs. ...tSaSSSSaaaaaasTttSSs. ..stSSSSSSSasSSSsamtTtm. ...stttSSSSSSatSSSSs....
...sSSaSSSqcqSSSsattSSs. ...sSSaSSSqcqSSSsattSSs. ..sSSaSSSSaaaaaasTttSSs. ...stSaSSSSSaaaCaCa.....
...sSSSaSqcCcqSSsaSSSs.. ...sSSSaSqcCcqSSsaSSSs.. ..sSSSaSSqcqSSSsattSSs.. ...sSSSaSSSSasSSSsa.mMm.
...sSSSSSSqcqSSssaSSs... ...sSSSSSSqcqSSssaSSs... ..sSSSSaqcCcqSSsatSSSs.. ...sSSSSaSqcqSSSsamtTtm.
....sSSSSSSSSaSsasSs.... ....sSSSSSSSSaSsasSs.... ..sSSSSSSqcqSSStTttSSs.. ...sSSSSSqcCcqSSsatTtSs.
.....sSSSSSSaSsa.ss..... .....sSSSSSSaSsa.ss..... ...sSSSSSSSSaStTttSSSSs. ....sSSSSSqcqSSsa.tSSs..
.....assSSSSssa......... .....assSSSSssa......... ....sSSSSSSaSstSaSaSaSs. .....sSSSSSSSSsa.tSSs...
......asssssaa.......... ......asssssaa.......... .....asssssaa.sssssss... .....assSSSSssa.tSSs..U.
.......sSSs.sSs......... .......sSSs.sSs......... .......sSSs.sSs......... ......asssssaa.tSSs..u..
.......tSSs.tSSs........ .......tSSs.tSSs........ .......tSSs.tSSs........ .u.....sSSs.sSs.tTTtTTt.
.......tSSs.tSSs........ .......tSSs.tSSs........ .......tSSs.tSSs........ U.u....tSSs.tSSstTttSSs.
......ttSSs.tTSSs....... ......ttSSs.tTSSs....... ......ttSSs.tTSSs....... .u....ttSSs.tTaStSaSaSs.
......sssss.ssssss...... ......sssss.ssssss...... ......sssss.ssssss...... u.....sssss.sssssssssss.
........................ ........................ ........................ ........................
""", 24, 24)

G_DEATH = strip("""
........................ ........................ ........................ ........................ ........................
........................ ........................ ........................ ........................ ........................
........................ .....U.................. ........................ ........................ ........................
........................ .........u...mMm........ ........................ ........................ ........................
............mMm......... ....mMMm....mtTTm...U... ........................ ........................ ........................
....mMMm...mtTTm........ ...mtTTtm...tTtaSS...... ........................ ........................ ........................
...mtTTtm..tTtaSS....... ..mtTtatSs.aaaqaqa...... ........................ ........................ ........................
..mtTtatSs.tSSaSs....... ..tTtaSSSS.asSSSsa....u. ........................ ........................ ........................
..tTtaSSSSaaaqaqa.mMm... .sttSaSSSS.............. ........................ ........................ ........................
.sttSaSSSSasSSSsamtTtm.. ..................mMm... ...............u........ ........................ ........................
.stSSaSSSSaaaaaasTatSSs. .stSSaSSSSaaaaaa.mtTtm.. ........................ ........................ ........................
.sSSSSaSSSaqaSSSsaStSSs. .sSSSSaSSSaqaSSS.TatSSs. .....mMm................ ........................ ........................
.sSSSSSaSqcqcaSSsaSaSSs. .sSSSSSaSqaqaaSSs.StSSs. ....mtTtm....mMm........ ........................ ........................
.sSsSSSSaSaqaSSssaSSass. .sSsSSSSaSaqaSSss.SaSSs. ...mtTtttS..mtTTm....... ........................ ........................
.ssaSSSSSaSSSaSsasSSSs.. .....SSSSaSSSaSs..SSass. ...tTtSSSs..tTtSSs.mMm.. ........................ ........................
.sSsasSSSSaSaSsa.sSaSs.. .ssaSsSSSSaSaSsa.sSSSs.. ..stSSSaSs.aaqaqa.mtTm.. ........mMm............. ........................
.sSs.assSSSaSsa.tTtSSs.. .sSsaassSSSaSsa..sSaSs.. ..sSSaSSs.saSSSsa.tTtSs. .......mtTTm....mMm..... ........................
.tTts.asssssaa.tTtaSSSs. .sSs..asssssaa..tTtSSs.. ..sSSSSs.tSSaaaSs.SSaSs. ..mMm..tTtSSs..mtTTm.... .........mMm............
.tSSs..sSSs.sSs.tSaSaSs. .tTts..sSSs.sSstTtaSSSs. ...ssss.tTSaSSSSs.tSSSs. .mtTtm.tSSSSs.aqaqaS.... ......mMmtTtm...mMm.....
.sasa..tSSs.tSSs.sssss.. .tSSs..tSSs.tSSstSaSaSs. ..tTts.tSSSaSSSss.tSaSs. .tTtSSsaSSSs.tSSSSSs.u.. ....tTtSstSSs.mtTtSs....
.......tSaS.tSSs........ .sasa..tSaS.tSSs.sssss.. ..tSSs.sSSSSSSss..ssss.. .tSSaSs.sss.tTtSaSSs.... ..tTtSSsaSSaSstSSaSSs...
......ttSSs.tTaSs....... ......ttSSs.tTaSs....... ..sasa.tSSs.tSSs........ ..ssss.tTtSs.tSSSSs.tTs. .tSSaSSStSSSsatSSSqSSs..
......sssss.ssssss...... ......sssss.ssssss...... ......sssss.ssssss...... ......sssssssss.sssssss. .ssssssssssssssssssssss.
........................ ........................ ........................ ........................ ........................
""", 24, 24)

GOLEM = Sheet("golem", 24, 24, 5, 4, GOLEM_PAL, [
    ("idle", G_IDLE),
    ("walk", G_WALK),
    ("attack", G_ATTACK),
    ("death", G_DEATH),
], fx=GOLEM_FX)


# --------------------------------------------------------------------------
# BOSS  "Portinvartija" (the Gatekeeper)  48x48, 6 cols x 4 rows, front view
# (symmetric, never flipped).  Rows: idle, attack (0-3 wind-up, 4-5 release),
# summon (frames 2-5 loop), death.
#
# A floating carved stone mask with one eye and a gate-arch crown, a tattered
# banner and two loose stone fists, circled by three crystal shards.  It has
# too many independently moving parts to draw 24 whole frames, so the PARTS
# are ASCII art below and the _boss_*() functions place them frame by frame.
# Each part gets its own outline before it is stamped, so overlapping parts
# stay separated; the composed frames then go through the normal Sheet
# pipeline.  Banner sway, shard orbit, light effects and the death fragments
# are computed.
# --------------------------------------------------------------------------
BOSS_PAL = {
    "T": C["stone3"], "S": C["stone2"], "s": C["stone1"], "a": C["stone0"], "x": C["dk1"],
    "M": C["crim2"], "m": C["crim1"], "k": C["crim0"],
    # emissive
    "W": "#ffffff", "C": C["cyan1"], "c": C["cyan0"], "q": "#2b8fb3", "r": "#2b8fb3",
    "V": C["vio0"], "v": C["vio1"], "u": C["vio2"], "U": "#3a1c78",
    "d": C["stone2"], "D": C["stone1"],          # dust specks
}
BOSS_FX = "WCcqrVvuUdD"

# 'r' = glowing rune crack (faint; brightened by _RUNES), 'x' = eye socket.
# The crown is a little stone gate arch with the dimension glowing inside.
B_MASK = """
.............TS.............
............TSSs............
...........TauvSa...........
..........TauvVuSa..........
..........TavVvvSa..........
.........TSauvvuSsa.........
..TS....TTSSTTTSsssa....Ss..
.TSSs..TSSSSSssssssaa..Srsa.
.TSSSTTSSSSSSssssssssSSrssa.
TSSSSSSSSSSTTssSSssssssrsssa
SsaaaaaaaaaaSTTSaaaaaaraaaaa
..TSaaaaaaaxxssxxaaaarassa..
..TSSsaaaxxxxaaxxxxarsssaa..
..TSSSsxxxxxxxxxxxxxxsssaa..
..TSSsxxxxxxxxxxxxxxxxssaa..
..TSSrxxxxxxxxxxxxxxxxssaa..
..TSrsxxxxxxxxxxxxxxxxssaa..
..TSrSsxxxxxxxxxxxxxxsssaa..
..srSSSSsxxxxxxxxxxssssaaa..
..srSSSSTTTxxxxxxSSssssaaa..
...rSSSSSSSTTTTTSssssssaa...
....SSSsssssssssssssaaaa....
.....SSsa##########aaaa.....
......Ss#SSSSSsssss#aa......
.......Sssssssssaaaaa.......
.........Ssssssaaaa.........
...........saaaaa...........
"""

# Eyes are stamped at B_EYE_AT inside the mask.  The 14x7 ones only paint
# socket pixels, so the frowning brow tip clips them; the 14x9 wide/flare
# eyes paint over the brow (the eye tears open).
B_EYES = dict(
    normal="""
.....uvvu.....
...uvcWWcvu...
.uvcCCWWCCcvu.
vccCCCWWCCCccv
.uvcCCWWCCcvu.
...uvcWWcvu...
.....uvvu.....
""",
    half="""
..............
..............
.uvccccccccvu.
vcCCCCWWCCCCcv
.uvcCCWWCCcvu.
...uvcWWcvu...
.....uvvu.....
""",
    narrow="""
..............
..............
..............
.uvcCCWWCCcvu.
...uvvvvvvu...
..............
..............
""",
    dim="""
.....UuuU.....
...UuvvvvuU...
.UuvvVVVVvvuU.
UuvvVVWWVVvvuU
.UuvvVVVVvvuU.
...UuvvvvuU...
.....UuuU.....
""",
    ember="""
..............
..............
..............
......uU......
..............
..............
..............
""",
    wide="""
....xuvvux....
..xuvccccvux..
.xvcCCWWCCcvx.
xvcCWWWWWWCcvx
xvcCWWWWWWCcvx
xvcCWWWWWWCcvx
.xvcCCWWCCcvx.
..xuvccccvux..
....xuvvux....
""",
    flare="""
....xvccvx....
..xvcCCCCcvx..
.xcCWWWWWWCcx.
xcCWWWWWWWWCcx
xcCWWWWWWWWCcx
xcCWWWWWWWWCcx
.xcCWWWWWWCcx.
..xvcCCCCcvx..
....xvccvx....
""",
)

B_FIST_L = """
...TTTSSs...
.TTSSSTSsss.
TSS#SS#Ss#sa
TSS#SS#Ss#sa
TSs#Ss#ss#aa
.sa#sa#sa#a.
.TTTTTTSssa.
.TSSSSSssaa.
..sSsaasaa..
..TrSrSrsa..
...aasaaa...
"""

B_FIST_R = """
...TTSSSs...
.TTSSSTSsss.
TS#SS#Ss#ssa
TS#SS#Ss#ssa
Ts#Ss#ss#saa
.s#sa#sa#aa.
.TTTTTTSssa.
.TSSSSSssaa.
..sSsaasaa..
..TrSrSrsa..
...aasaaa...
"""

# Open hands for the summon: palm to the viewer, thumbs toward the mask.
B_PALM_L = """
.......TS.....
....TS.TS.TS..
.TS.TS.TS.TS..
.TS.TS.TS.Ss..
.TS.TS.Ss.Ss..
.TSSTSSSsSsa..
.TSSSSSSSssa..
.TSSuvvuSssa.T
.TSuVccVusaTS.
.TSuvccvusTS..
.TSSuvvuSssa..
..TSSSSSssa...
...saaaaa.....
....arra......
"""

B_PALM_R = """
.....TS.......
..TS.TS.TS....
..TS.TS.TS.TS.
..TS.TS.TS.Ss.
..TS.TS.Ss.Ss.
..TSSTSSSsSsa.
..TSSSSSSSssa.
T.TSSSuvvuSsa.
.TSTSuVccVusa.
..TSTuvccvusa.
..TSSSuvvuSsa.
...TSSSSSssa..
.....saaaaa...
......arra....
"""

B_SHARD = """
.C.
CWc
cCv
.v.
"""

B_SHARD_SM = """
C.
cc
.v
"""

B_CHUNKS = ["""
.TS.
TSsa
.sa.
""", """
TS
sa
""", """
.TSs
TSsa
saa.
""", """
TSs
Saa
"""]

B_SCRAP = """
mMk
.mk
"""

# Banner: per-column fold shading (light from the left) and its tattered
# strips (first column, last column, length); strips hang joined above
# B_CLOTH_JOIN and sway separately below it.
B_CLOTH_FOLDS = "mMmkmMMmkmMMmmkmMmkmMmkk"
B_CLOTH_STRIPS = ((0, 3, 12), (4, 8, 16), (9, 14, 18), (15, 18, 13), (19, 23, 15))
B_CLOTH_PHASE = (0.0, 2.1, 4.0, 1.2, 3.3)
B_CLOTH_JOIN = 8
B_CLOTH_SIGIL = {(10, 11): "u", (11, 10): "v", (12, 10): "v", (13, 11): "u", (10, 12): "U", (13, 12): "U"}

# Resting layout, frame coordinates.
B_MASK_AT = (10, 5)
B_EYE_AT = (7, 12)             # 14x7 eye origin inside the mask
B_EYE_C = (23.5, 20.0)         # eye centre at rest (pixel coordinates)
B_CLOTH_AT = (12, 22)
B_FIST_L_AT, B_FIST_R_AT = (5, 28), (31, 28)

_RUNES = [  # glow levels of the rune cracks (and, from level 2, the crown gate)
    {},
    {"r": "c"},
    {"r": "C", "u": "v", "v": "V"},
    {"r": "W", "u": "V", "v": "C", "V": "W"},
]
_DIM = {"W": "C", "C": "c", "c": "q", "V": "v", "v": "u", "u": "U"}


def _art(text):
    rows = text.strip("\n").splitlines()
    if any(len(r) != len(rows[0]) for r in rows):
        raise ValueError(f"ragged boss part: {rows[0]!r}")
    return rows


def _recolor(art, cmap):
    return ["".join(cmap.get(ch, ch) for ch in row) for row in art]


def _outlined(art):
    """The part with its own 1px outline (one pixel bigger on every side)."""
    w = len(art[0]) + 2
    return add_outline(["." * w] + ["." + r + "." for r in art] + ["." * w], BOSS_FX)


def _r(v):
    return int(math.floor(v + 0.5))


class _Canvas:
    def __init__(self, w=48, h=48):
        self.w, self.h = w, h
        self.g = [["."] * w for _ in range(h)]

    def get(self, x, y):
        return self.g[y][x] if 0 <= x < self.w and 0 <= y < self.h else "."

    def put(self, x, y, ch, only_on=None):
        if 0 <= x < self.w and 0 <= y < self.h and (only_on is None or self.g[y][x] in only_on):
            self.g[y][x] = ch

    def stamp(self, art, x, y, outline=True, only_on=None):
        if outline:
            art, x, y = _outlined(art), x - 1, y - 1
        for j, row in enumerate(art):
            for i, ch in enumerate(row):
                if ch != ".":
                    self.put(x + i, y + j, ch, only_on)

    def rows(self):
        return ["".join(r) for r in self.g]


MASK = _art(B_MASK)
EYES = {k: _art(v) for k, v in B_EYES.items()}
FIST_L, FIST_R = _art(B_FIST_L), _art(B_FIST_R)
PALM_L, PALM_R = _art(B_PALM_L), _art(B_PALM_R)
SHARD, SHARD_SM = _art(B_SHARD), _art(B_SHARD_SM)
CHUNKS = [_art(t) for t in B_CHUNKS]
SCRAP = _art(B_SCRAP)


def _cloth(t, amp=1.6, fan=0.0, lift=0, strips=None):
    """Banner art at sway phase t; returns (rows, x offset of column 0)."""
    pad = 6
    g = [["."] * (24 + 2 * pad) for _ in range(24)]
    for i, (x0, x1, ln) in enumerate(B_CLOTH_STRIPS):
        if strips is not None and i not in strips:
            continue
        ln -= lift
        side = ((x0 + x1) / 2 - 11.5) / 11.5
        for y in range(ln):
            d = max(0.0, (y - B_CLOTH_JOIN) / max(1, ln - B_CLOTH_JOIN))
            dx = amp * d ** 1.3 * math.sin(t + B_CLOTH_PHASE[i] - 0.45 * y)
            dx += fan * side * max(0, y - B_CLOTH_JOIN)
            if y == ln - 1:
                xs = [x0 + (x1 - x0 + 1) // 2]
            elif y == ln - 2:
                xs = range(x0, x1)
            else:
                xs = range(x0, x1 + 1)
            for x in xs:
                ch = B_CLOTH_SIGIL.get((x, y), B_CLOTH_FOLDS[x])
                if y >= ln - 3 and ch == "M":
                    ch = "m"
                g[y][_r(x + dx) + pad] = ch
    return ["".join(r) for r in g], -pad


def _shard_pts(theta, n=3, rx=21.0, ry=5.0, cx=23.5, cy=20.5):
    pts = []
    for i in range(n):
        a = theta + i * 2 * math.pi / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a), math.sin(a)))
    return pts


def _draw_shards(cv, pts, front):
    """Shards at pts [(x, y, depth)]: the far ones (small, dim) or the near ones."""
    for x, y, depth in pts:
        if (depth >= -0.35) != front:
            continue
        art = SHARD if front else _recolor(SHARD_SM, _DIM)
        cv.stamp(art, _r(x) - len(art[0]) // 2, _r(y) - len(art) // 2, outline=False)


_G_SOFT = {"x": "u", "a": "U"}
_G_MID = {"x": "v", "a": "u", "s": "u", "S": "v", "T": "V"}
_G_HOT = {"x": "V", "a": "v", "s": "V", "S": "C", "T": "W", "#": "u"}


def _glow(cv, cx, cy, rings):
    """Light the stone around (cx, cy): rings = [(radius, tint map)], inner first."""
    for y in range(cv.h):
        for x in range(cv.w):
            d = math.hypot(x - cx, (y - cy) * 1.2)
            for r, tint in rings:
                if d <= r:
                    ch = cv.get(x, y)
                    if ch in tint:
                        cv.put(x, y, tint[ch])
                    break


_GATE_RING = ((13, 2), (14, 2), (15, 3), (15, 4), (15, 5), (14, 5), (13, 5), (12, 5), (12, 4), (12, 3))
_GATE_CORE = ((13, 3), (14, 3), (14, 4), (13, 4))


def _gate(art, phase):
    """Swirl the light inside the crown gate (phase 0..1 = one turn)."""
    g = [list(r) for r in art]
    i0 = _r(phase * len(_GATE_RING))
    for i, (x, y) in enumerate(_GATE_RING):
        k = (i - i0) % len(_GATE_RING)
        g[y][x] = "V" if k == 0 else "v" if k in (1, 5, 9) else "u"
    for i, (x, y) in enumerate(_GATE_CORE):
        g[y][x] = "V" if (i - _r(phase * 4)) % 4 == 2 else "v"
    return ["".join(r) for r in g]


def _body(cv, bob=0, eye="normal", runes=0, cloth=None, hands=None, shards=(),
          glow=None, gate=0.0):
    """Back shards, banner, mask + eye, hands, front shards."""
    _draw_shards(cv, shards, front=False)
    if cloth is not None:
        art, ox = cloth
        cv.stamp(art, B_CLOTH_AT[0] + ox, B_CLOTH_AT[1] + bob)
    mx, my = B_MASK_AT[0], B_MASK_AT[1] + bob
    cv.stamp(_recolor(_gate(MASK, gate), _RUNES[runes]), mx, my)
    ea = EYES[eye]
    if len(ea) == 7:
        cv.stamp(ea, mx + B_EYE_AT[0], my + B_EYE_AT[1], outline=False, only_on="x")
    else:
        cv.stamp(ea, mx + B_EYE_AT[0], my + B_EYE_AT[1] - 1, outline=False)
    if glow:
        _glow(cv, B_EYE_C[0], B_EYE_C[1] + bob, glow)
    for art, x, y in hands or ():
        cv.stamp(art, x, y)
    _draw_shards(cv, shards, front=True)


def _fists(dl=(0, 0), dr=(0, 0), runes=0):
    al = _recolor(FIST_L, _RUNES[runes])
    ar = _recolor(FIST_R, _RUNES[runes])
    return [(al, B_FIST_L_AT[0] + dl[0], B_FIST_L_AT[1] + dl[1]),
            (ar, B_FIST_R_AT[0] + dr[0], B_FIST_R_AT[1] + dr[1])]


def _boss_idle():
    frames = []
    bob = (0, -1, -1, 0, 1, 1)
    tri = (0, -1, -2, -1, 0, 1)
    for f in range(6):
        cv = _Canvas()
        t = -f * 2 * math.pi / 6
        _body(cv, bob=bob[f], eye="normal", runes=0, gate=f / 6,
              cloth=_cloth(t),
              hands=_fists((0, tri[f]), (0, tri[(f + 3) % 6])),
              shards=_shard_pts(math.radians(-90 + 20 * f)))
        frames.append(cv.rows())
    return frames


def _line(cv, x0, y0, x1, y1, chars):
    """Line from (x0, y0) to (x1, y1), colour graded along it by chars."""
    n = max(abs(_r(x1) - _r(x0)), abs(_r(y1) - _r(y0)), 1)
    for i in range(n + 1):
        t = i / n
        ch = chars[min(len(chars) - 1, int(t * len(chars)))]
        cv.put(_r(x0 + (x1 - x0) * t), _r(y0 + (y1 - y0) * t), ch)


def _burst(cv, cx, cy, core, rays, ray_chars="WWCCcv"):
    """White-hot flash: a core disc and rays [(angle in degrees, length)]."""
    for y in range(cv.h):
        for x in range(cv.w):
            d = math.hypot(x - cx, y - cy)
            if d <= core:
                cv.put(x, y, "W")
            elif d <= core + 1.1:
                cv.put(x, y, "C")
    for ang, ln in rays:
        a = math.radians(ang)
        _line(cv, cx + math.cos(a) * core, cy + math.sin(a) * core,
              cx + math.cos(a) * ln, cy + math.sin(a) * ln, ray_chars)


def _ring(cv, cx, cy, r, chars, sy=1.0):
    """Circle (or flattened ellipse) outline; chars cycle around it ('.' = gap)."""
    n = max(8, int(2 * math.pi * r * 1.4))
    for k in range(n):
        a = 2 * math.pi * k / n
        ch = chars[k * len(chars) // n]
        if ch != ".":
            cv.put(_r(cx + r * math.cos(a)), _r(cy + r * sy * math.sin(a)), ch)


def _trail(cv, x, y, tx, ty, n, chars="Ccq"):
    """Streak behind a flying shard at (x, y), pointing back to (tx, ty)."""
    d = math.hypot(tx - x, ty - y) or 1.0
    for i in range(1, n + 1):
        ch = chars[min(len(chars) - 1, (i - 1) * len(chars) // n)]
        cv.put(_r(x + (tx - x) / d * i), _r(y + (ty - y) / d * i), ch)


def _boss_attack():
    frames = []
    ex, ey = B_EYE_C
    bob = (0, -1, -1, -2, 1, 0)
    spread = (0, 1, 2, 3, 1, 0)
    rise = (0, -1, -2, -3, 0, 0)
    eyes = ("normal", "wide", "wide", "flare", "flare", "wide")
    runes = (1, 1, 2, 2, 3, 1)
    glows = (None, None, [(6.5, _G_SOFT)], [(5.5, _G_MID), (8, _G_SOFT)],
             [(6, _G_HOT), (9, _G_MID), (12, _G_SOFT)], [(6.5, _G_SOFT)])
    targets = (210, 330, 90)          # where shards 0, 1, 2 gather (deg around the eye)
    start = _shard_pts(math.radians(-90))
    for f in range(6):
        cv = _Canvas()
        b = bob[f]
        cy = ey + b
        pts = []
        if f < 4:
            k = (0.0, 0.45, 0.8, 1.0)[f]
            for (sx, sy, dep), a in zip(start, targets):
                a = math.radians(a)
                tx, ty = ex + 8 * math.cos(a), cy + 7 * math.sin(a)
                pts.append((sx + (tx - sx) * k, sy + (ty - sy) * k, dep if k == 0 else 1.0))
        _body(cv, bob=b, eye=eyes[f], runes=runes[f], gate=f / 6,
              cloth=_cloth(-f * math.pi / 3, amp=1.3),
              hands=_fists((-spread[f], rise[f]), (spread[f], rise[f]), runes[f]),
              shards=pts, glow=glows[f])
        if f == 3:      # energy drawn into the eye
            for a in (0, 45, 135, 180, 225, 315):
                r = math.radians(a)
                _line(cv, ex + 11 * math.cos(r), cy + 9 * math.sin(r),
                      ex + 8 * math.cos(r), cy + 6.5 * math.sin(r), "vV")
        if f >= 4:      # release: flash, shards flung outward
            if f == 4:
                _burst(cv, ex, cy, 2.6, [(0, 17), (180, 17), (90, 11), (270, 12),
                                         (40, 8), (140, 8), (220, 8), (320, 8)])
            else:
                _ring(cv, ex, cy, 13, "vV.V", sy=0.8)
                _ring(cv, ex, cy, 4, "CcCc")
            dist = 15 if f == 4 else 21
            for a in targets:
                a = math.radians(a)
                x, y = ex + dist * math.cos(a), cy + dist * 0.85 * math.sin(a)
                _trail(cv, x, y, ex, cy, 5 if f == 4 else 7, "CCcq" if f == 4 else "ccqU")
                cv.stamp(SHARD, _r(x) - 1, _r(y) - 2, outline=False)
        frames.append(cv.rows())
    return frames


def _rune_circle(cv, cx, cy, rx, ry, step, level):
    """Summoning circle (flat ellipse) whose glyph marks turn with `step`."""
    def inside(x, y, sx, sy):
        return ((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2 <= 1.0

    for y in range(_r(cy - ry) - 1, _r(cy + ry) + 2):
        for x in range(_r(cx - rx) - 1, _r(cx + rx) + 2):
            ang = (math.atan2((y - cy) / ry, (x - cx) / rx) / (2 * math.pi)) % 1.0
            b = int(ang * 16 + step) % 16
            if inside(x, y, rx, ry) and not all(inside(x + dx, y + dy, rx, ry)
                                                 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                if level == 0:
                    ch = "u" if b % 4 == 0 else "."
                elif level == 1:
                    ch = "v" if b % 4 == 0 else "u"
                else:
                    ch = "C" if b % 4 == 0 else "V" if b % 4 == 2 else "v"
                if ch != ".":
                    cv.put(x, y, ch)
            elif level >= 1 and inside(x, y, rx * 0.55, ry * 0.45) and not all(
                    inside(x + dx, y + dy, rx * 0.55, ry * 0.45) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                bi = int(ang * 16 - step) % 16
                ch = ("c" if bi % 2 == 0 else "u") if level >= 2 else ("u" if bi % 2 == 0 else ".")
                if ch != ".":
                    cv.put(x, y, ch)


def _boss_summon():
    frames = []
    bob = (0, -1, -2, -3, -3, -2)
    for f in range(6):
        cv = _Canvas()
        b = bob[f]
        lp = (f - 2) % 4                       # phase of the frame 2-5 loop
        _rune_circle(cv, 23.5, 42.5, 17.0, 4.4, lp, (0, 1, 2, 2, 2, 2)[f])
        if f >= 2:                             # light rising from the circle
            for x, off in ((12, 0), (18, 5), (29, 2), (35, 7)):
                y = 41 - (lp * 2 + off) % 8
                cv.put(x, y, "c" if (lp + off) % 2 else "V")
        if f == 0:
            hands = _fists((-2, -5), (2, -5), 1)
        elif f == 1:
            hands = [(PALM_L, 0, 14), (PALM_R, 34, 14)]
        else:
            hl, hr = (0, -1, -1, 0)[lp], (-1, 0, 0, -1)[lp]
            hands = [(PALM_L, 0, 6 + hl), (PALM_R, 34, 6 + hr)]
        _body(cv, bob=b, eye="half" if f == 0 else "narrow", runes=(1, 1, 2, 1, 2, 1)[f],
              gate=lp / 4,
              cloth=_cloth(-lp * math.pi / 2, amp=2.0, fan=(0.1, 0.25, 0.4, 0.4, 0.4, 0.4)[f],
                           lift=(0, 1, 2, 2, 2, 2)[f]),
              hands=hands,
              shards=_shard_pts(math.radians(-90 + 30 * lp), cy=20.5 + b))
        frames.append(cv.rows())
    return frames


_RUNES_DEAD = {"r": "U", "u": "U", "v": "u", "V": "v"}     # runes and crown gate go dark


def _mask_piece(x, y):
    """Fragment that mask pixel (x, y) breaks off with when the Gatekeeper dies."""
    if y <= 5:
        return "K"                                       # crown gate
    if y <= 8 and (x <= 5 or x >= 22):
        return "HL" if x <= 5 else "HR"                  # horns
    side = "L" if x < 14 + _r(1.3 * math.sin(0.55 * y + 0.5)) else "R"
    if y <= 11 + _r(1.2 * math.sin(0.5 * x + 2.0)):
        return side + "1"
    if y <= 19 + _r(1.2 * math.sin(0.45 * x + 0.3)):
        return side + "2"
    return side + "3"


def _fist_piece(x, y):
    return "top" if y <= 4 + (0, 1)[x % 2] else "bot"


def _split(art, label):
    """{label: art of just that fragment} for every fragment of art."""
    out = {}
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch != ".":
                k = label(x, y)
                out.setdefault(k, [["."] * len(row) for _ in art])[y][x] = ch
    return {k: ["".join(r) for r in g] for k, g in out.items()}


def _seams(art, label):
    """Pixels of art that lie on a seam between two fragments (the cracks)."""
    seam = set()
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            for dx, dy in ((1, 0), (0, 1)):
                if (y + dy < len(art) and x + dx < len(row) and art[y + dy][x + dx] != "."
                        and label(x + dx, y + dy) != label(x, y)):
                    seam.add((x, y))
    return seam


def _boss_death():
    frames = []
    ex, ey = B_EYE_C
    mx, my = B_MASK_AT[0], B_MASK_AT[1] + 1           # the blow knocks it down a pixel
    cy = ey + 1
    mcx, mcy = ex - mx, cy - my                        # eye centre in mask coordinates
    dead = _recolor(MASK, _RUNES_DEAD)
    seams = _seams(dead, _mask_piece)
    fist_l, fist_r = _split(FIST_L, _fist_piece), _split(FIST_R, _fist_piece)
    shard_rest = _shard_pts(math.radians(-90), cy=ey + 0.5)
    ground = 46

    def near(x, y):
        return math.hypot(x - mcx, (y - mcy) * 1.3)

    def mask_with(fn):
        return ["".join(fn(x, y, ch) for x, ch in enumerate(row)) for y, row in enumerate(dead)]

    def rays(cv, length, chars, angles=(270, 205, 335, 155, 25, 90, 235, 305)):
        for a in angles:
            dx, dy = math.cos(math.radians(a)), 0.9 * math.sin(math.radians(a))
            ln = length
            while not (1 <= ex + ln * dx <= 46 and 1 <= cy + ln * dy <= 46):
                ln -= 1                 # the whole ray, tip included, stays inside the frame
            _line(cv, ex, cy, ex + ln * dx, cy + ln * dy, chars)

    def shards(cv, drop, front):
        for x, y, d in shard_rest:
            if (d >= -0.35) == front:
                yy = min(ground - 1, _r(y) + drop)
                cv.stamp(_recolor(SHARD_SM, _DIM), _r(x) - 1, yy - 1, outline=False)

    def fists(cv, sag, cracked):
        for art, x, y in _fists((1, sag), (-1, sag)):
            cv.stamp(_recolor(art, _RUNES_DEAD), x, y)
            if cracked:
                for i in range(1, 11):
                    cv.put(x + i, y + 5 + (0, 1)[i % 2], "c", only_on="TSsa#")

    for f in range(6):
        cv = _Canvas()
        if f <= 1:
            # 0: first cracks around the flickering eye; 1: cracks run along every
            # seam with light bursting through, and the eye has gone out
            if f == 1:
                rays(cv, 22, "WCCcv")
            shards(cv, (1, 5)[f], front=False)
            art, ox = _cloth(0.6, amp=(0.4, 0.0)[f])
            cv.stamp(_recolor(art, _RUNES_DEAD), B_CLOTH_AT[0] + ox, B_CLOTH_AT[1] + 1 + 2 * f)
            if f == 0:
                def crack(d):
                    return ("c" if d < 6 else "#") if d < 10 else None
            else:
                def crack(d):
                    return "W" if d < 7 else "C" if d < 12 else "c"
            cv.stamp(mask_with(lambda x, y, ch: (crack(near(x, y)) or ch)
                               if (x, y) in seams and ch != "x" else ch), mx, my)
            cv.stamp(EYES[("dim", "ember")[f]], mx + B_EYE_AT[0], my + B_EYE_AT[1],
                     outline=False, only_on="x")
            fists(cv, (2, 5)[f], cracked=f == 1)
            shards(cv, (1, 5)[f], front=True)
        elif f <= 3:
            if f == 2:
                # the mask splits; light floods out of the gaps and the empty socket
                rays(cv, 27, "WWCCcv")
                art, ox = _cloth(1.0, amp=0.8, lift=-1, strips=(1, 2, 3))
                cv.stamp(_recolor(art, _RUNES_DEAD), B_CLOTH_AT[0] + ox, B_CLOTH_AT[1] + 6)
                art = mask_with(lambda x, y, ch: ("W" if near(x, y) < 6 else "C") if ch == "x" else ch)
                off = dict(K=(0, -2), HL=(-2, -1), HR=(2, -1), L1=(-1, 0), R1=(1, 0),
                           L2=(-2, 1), R2=(2, 1), L3=(-1, 2), R3=(1, 2))
            else:
                # fragments fly apart and fall, their broken edges cooling to violet
                for x, y in ((6, 34), (37, 33), (20, 41)):
                    cv.stamp(SCRAP, x, y)
                art = mask_with(lambda x, y, ch: ("u" if near(x, y) < 11 else "U") if (x, y) in seams
                                else "a" if ch == "x" else ch)
                off = dict(K=(0, 3), HL=(-9, 2), HR=(9, 2), L1=(-6, 4), R1=(6, 4),
                           L2=(-8, 7), R2=(8, 7), L3=(-4, 10), R3=(4, 10))
            for k, piece in _split(art, _mask_piece).items():
                cv.stamp(piece, mx + off[k][0], my + off[k][1])
            if f == 3:
                for x, y in ((22, 21), (26, 24), (19, 27), (29, 19)):
                    cv.put(x, y, "V" if x % 2 else "v")
            if f == 2:
                for y, row in enumerate(dead):
                    for x, ch in enumerate(row):
                        if ch != "." and cv.get(mx + x, my + y) in ".#":
                            d = near(x, y)
                            cv.put(mx + x, my + y, "W" if d < 8 else "C" if d < 13 else "c")
                for x, y in ((7, 12), (40, 11), (5, 24), (42, 25), (15, 3), (32, 3)):
                    cv.put(x, y, "d" if (x + y) % 2 else "D")
            # the fists break in two, then crumble as they drop
            for parts, (bx, by), sgn in ((fist_l, B_FIST_L_AT, -1), (fist_r, B_FIST_R_AT, 1)):
                if f == 2:
                    cv.stamp(_recolor(parts["top"], _RUNES_DEAD), bx + sgn, by + 6)
                    cv.stamp(_recolor(parts["bot"], _RUNES_DEAD), bx, by + 8)
                else:
                    cx0 = bx + 4
                    for i, (dx, dy) in enumerate(((sgn * 3, 9), (-sgn * 2, 12), (sgn * 1, 14))):
                        cv.stamp(CHUNKS[(i + (sgn > 0)) % len(CHUNKS)], cx0 + dx, by + dy)
            shards(cv, (12, 30)[f - 2], front=False)
            shards(cv, (12, 30)[f - 2], front=True)
        elif f == 4:
            # rubble: the crown gate lies among the chunks, dust settling
            cv.stamp(_split(dead, _mask_piece)["K"], mx, ground - 6)
            for i, (x, y) in enumerate(((5, 42), (11, 43), (31, 42), (37, 43), (42, 44), (17, 44))):
                cv.stamp(CHUNKS[i % len(CHUNKS)], x, y)
            for x, y in ((9, 38), (15, 36), (13, 40), (34, 37), (39, 39), (28, 35), (20, 39),
                         (24, 33), (44, 40), (6, 39)):
                cv.put(x, y, "d" if (x + y) % 2 else "D")
            cv.stamp(SCRAP, 25, 44)
            for x, y, d in shard_rest[1:]:
                cv.stamp(_recolor(SHARD_SM, _DIM), _r(x) - 1, ground - 2, outline=False)
            # the gate's last light leaves as a wisp
            for i, (x, y) in enumerate(((24, 38), (23, 36), (23, 35), (24, 33), (25, 32), (24, 30), (23, 29))):
                cv.put(x, y, "v" if i < 2 else "u" if i < 5 else "U")
        else:
            # 5: a few chunks and one dim shard are all that is left
            for i, (x, y) in enumerate(((13, 44), (22, 43), (31, 44))):
                cv.stamp(CHUNKS[(i + 1) % len(CHUNKS)], x, y)
            cv.stamp(_recolor(_recolor(SHARD_SM, _DIM), _DIM), 37, ground - 2, outline=False)
        frames.append(cv.rows())
    return frames


BOSS = Sheet("boss", 48, 48, 6, 4, BOSS_PAL, [
    ("idle", _boss_idle()),
    ("attack", _boss_attack()),
    ("summon", _boss_summon()),
    ("death", _boss_death()),
], fx=BOSS_FX)

SHEETS = [PLAYER, PLAYER_ARM, SLIME, BAT, WISP, CASTER, GOLEM, BOSS]



# --------------------------------------------------------------------------
# Preview rendering
# --------------------------------------------------------------------------
ARM_PIVOT_IN_ARM = (1, 2)      # pivot pixel inside player_arm.png
ARM_PIVOT_IN_PLAYER = (8, 8)   # shoulder pixel inside a player frame


def _arm_overlay(cell, arm, angle):
    """Composite the arm onto a 16x16 player cell, rotated `angle` degrees (clockwise) about the pivot."""
    big = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    big.alpha_composite(arm, (16 - ARM_PIVOT_IN_ARM[0], 16 - ARM_PIVOT_IN_ARM[1]))
    if angle:
        big = big.rotate(-angle, resample=Image.NEAREST, center=(16, 16))
    tmp = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    tmp.alpha_composite(cell, (16, 16))
    tmp.alpha_composite(big, (ARM_PIVOT_IN_PLAYER[0], ARM_PIVOT_IN_PLAYER[1]))
    return tmp.crop((16, 16, 32, 32))


def render_preview(sheet, out_dir, scale=8):
    anims = sheet.frames()
    gap = 1
    cw, ch = sheet.fw + gap, sheet.fh + gap
    W = gap + sheet.cols * cw
    H = gap + len(anims) * ch
    canvas = Image.new("RGBA", (W, H), (40, 40, 48, 255))
    cell_bg = Image.new("RGBA", (sheet.fw, sheet.fh), (92, 92, 104, 255))
    for r, (label, frames) in enumerate(anims):
        for c in range(sheet.cols):
            x0, y0 = gap + c * cw, gap + r * ch
            canvas.paste(cell_bg, (x0, y0))
            if c < len(frames):
                fi = frame_image(frames[c], sheet.pal)
                canvas.alpha_composite(fi, (x0, y0))
    big = canvas.resize((W * scale, H * scale), Image.NEAREST)
    big.save(os.path.join(out_dir, f"{sheet.name}_x{scale}.png"))
    # in-game look: 3x on a cave-ish background, no grid
    bg = Image.new("RGBA", (sheet.cols * (sheet.fw + 4) + 4, len(anims) * (sheet.fh + 4) + 4), (24, 20, 30, 255))
    for r, (label, frames) in enumerate(anims):
        for c, f in enumerate(frames):
            bg.alpha_composite(frame_image(f, sheet.pal), (4 + c * (sheet.fw + 4), 4 + r * (sheet.fh + 4)))
    bg.resize((bg.width * 3, bg.height * 3), Image.NEAREST).save(os.path.join(out_dir, f"{sheet.name}_ingame_x3.png"))

    if sheet is PLAYER:
        # every player frame with the arm attached (0 deg), plus one row of aim angles
        arm = frame_image(PLAYER_ARM.frames()[0][1][0], PLAYER_ARM.pal)
        rows_n = len(anims) + 1
        comp = Image.new("RGBA", (gap + sheet.cols * cw, gap + rows_n * ch), (40, 40, 48, 255))
        for r, (label, frames) in enumerate(anims):
            for c, f in enumerate(frames):
                cell = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
                cell.alpha_composite(frame_image(f, sheet.pal))
                comp.paste(cell_bg, (gap + c * cw, gap + r * ch))
                comp.alpha_composite(_arm_overlay(cell, arm, 0), (gap + c * cw, gap + r * ch))
        idle0 = frame_image(anims[0][1][0], sheet.pal)
        for c, ang in enumerate([-90, -45, -20, 20, 45, 90]):
            comp.paste(cell_bg, (gap + c * cw, gap + len(anims) * ch))
            comp.alpha_composite(_arm_overlay(idle0, arm, ang), (gap + c * cw, gap + len(anims) * ch))
        comp.resize((comp.width * scale, comp.height * scale), Image.NEAREST).save(
            os.path.join(out_dir, f"player_with_arm_x{scale}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="directory for enlarged preview images")
    ap.add_argument("--only", help="comma separated sheet names")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None
    for sh in SHEETS:
        if only and sh.name not in only:
            continue
        img = sh.build()
        path = os.path.join(OUT_DIR, sh.name + ".png")
        img.save(path)
        print(f"wrote {os.path.relpath(path, ROOT)}  {img.width}x{img.height}")
        if args.preview:
            os.makedirs(args.preview, exist_ok=True)
            render_preview(sh, args.preview)


if __name__ == "__main__":
    main()
