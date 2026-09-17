"""Subset the self-hosted webfont from its upstream TTF.

Run this only when the family or the required glyph coverage changes; the
output (`ui/static/fonts/*.woff2`) is committed, so a normal checkout needs no
font tooling and no network.

    pip install fonttools brotli
    curl -sSL -o /tmp/fontsrc/roboto-var.ttf \\
      'https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto%5Bwdth%2Cwght%5D.ttf'
    python tools/build_fonts.py /tmp/fontsrc

ONE family now: Roboto, for every role. It replaced a three-family system
(Instrument Serif display / IBM Plex Mono readouts / IBM Plex Sans body, six
static woff2s, 102 KB).

Why the VARIABLE font rather than static instances: the interface asks for
four weights (400, 500, 600, 700 — counted in dashboard.css). Four statics
would be four files and, worse, a mapping question every time a weight is
added. One variable file declared `font-weight: 100 900` resolves every weight
exactly, and comes out smaller than the four statics would. `wdth` is pinned
to 100 before subsetting: nothing here sets `font-stretch`, so the axis was
only carrying bytes.

Why we subset ourselves rather than use a CDN's pre-cut files:

The obvious route is @fontsource / Google Fonts' own `latin` + `latin-ext`
woff2s. That was tried and is *not* sufficient here — measured, not assumed:
Google's `latin` range carries U+2191 and U+2193 but **not** U+2192, and
carries no subscript digits at all, while this interface draws a subscript two
in every "GtCO2" figure. EXTRA_CODEPOINTS below is therefore not decoration:
each entry is a character this UI actually renders. Keep it in sync with the
interface, and re-run.

WHAT THIS BUILD PROVES, per file, failing if it cannot:
  1. every codepoint in REQUIRED_TEXT is present;
  2. the digits are equal-advance.
(2) is not cosmetic. Chart axes, chart tooltips and the Sankey readout are
drawn on a canvas, and canvas 2D has no way to request tabular figures — so
a number that changes cannot be kept from shifting sideways unless the digits
are naturally the same width. Roboto's are (all 1151/2048). It used to be a
comment; a comment cannot fail a build.
"""

import pathlib
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/fontsrc")
OUT = pathlib.Path(__file__).resolve().parent.parent / "ui" / "static" / "fonts"

# Upstream, for reference when regenerating:
#   Roboto  https://github.com/google/fonts ofl/roboto (Apache-2.0),
#           the variable Roboto[wdth,wght].ttf
SOURCES = [
    ("roboto-var.ttf", "roboto-var.woff2", "text"),
]

# Google Fonts' own `latin` and `latin-ext` ranges, so the coverage is the
# familiar one and the unicode-range in dashboard.css can stay conventional.
LATIN = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
    "U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,"
    "U+2212,U+2215,U+FEFF,U+FFFD"
)
LATIN_EXT = (
    "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,"
    "U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,"
    "U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF"
)

# Characters this UI draws that neither range covers. Each one is load-bearing:
#   U+2082  subscript two — "GtCO₂", in the KPI figure, the GHG gauge and the
#           emissions chart's tooltip unit.
#   U+2026  horizontal ellipsis — CSS text-overflow renders its own, but the
#           status/insight strings also use a literal one.
# (U+2212, the true minus the chart tooltips require for negative values, and
# U+2013/U+2014 for the level spans and group titles, are already inside
# `latin` — verified.)
EXTRA_CODEPOINTS = [0x2082, 0x2026]

# Codepoints the build proves are present afterwards.
#
# U+2192, the rightwards arrow, is deliberately NOT here and is worth the
# explanation, because it used to be: **Roboto contains no arrows at all.**
# Checked against the upstream TTF rather than inferred from a subset — of its
# 927 codepoints, U+2190 through U+2193 are all absent, as are U+25B2/U+25BC.
# The interface needs an arrow (the Insights panel's "9.6 GtCO₂ → 8.5 GtCO₂")
# and two triangles (that panel's up/down badges), so those three are drawn as
# an inline SVG and as CSS borders instead of as glyphs — the same answer this
# project already reached for the card-header caret, and a better one than a
# second family loaded for three characters: a shape cannot fall back to
# whatever the OS happens to have.
REQUIRED_TEXT = [
    0x2212,  # minus, chart tooltip negatives (a real minus, not a hyphen)
    0x2082,  # subscript two, the "GtCO₂" unit
    0x2013,  # en dash, level spans "L3–4"
    0x2014,  # em dash, group titles "Supply — Conventional Energy"
    0x2026,  # ellipsis
    0x00B7,  # middot, row separators
    0x00B0,  # degree
    0x00A9,  # copyright, the footer
    0x00D7,  # multiplication sign
]


def unicodes_arg():
    ranges = f"{LATIN},{LATIN_EXT}," + ",".join(f"U+{c:04X}" for c in EXTRA_CODEPOINTS)
    return ranges.replace("U+", "")


def build(src_name, out_name):
    src = SRC / src_name
    dst = OUT / out_name

    # Pin wdth, keep wght variable. Done before subsetting so the dropped axis
    # takes its deltas with it.
    font = TTFont(src)
    axes = {a.axisTag for a in font["fvar"].axes} if font.get("fvar") else set()
    pinned = SRC / ("_pinned-" + src_name)
    if "wdth" in axes:
        instancer.instantiateVariableFont(font, {"wdth": 100}, inplace=True)
    font.save(pinned)

    args = [
        str(pinned),
        f"--unicodes={unicodes_arg()}",
        "--flavor=woff2",
        f"--output-file={dst}",
        # Narrow feature set, but `tnum`/`lnum` are retained where the source
        # has them. Roboto *does* ship `tnum`, unlike IBM Plex which needed no
        # such feature (its digits were already equal-advance). Roboto's are
        # too — see the digit-advance check below — so `tnum` is belt-and-
        # braces for the DOM and irrelevant to the canvas, which cannot ask.
        "--layout-features=kern,liga,tnum,zero,frac,sups,subs,onum,lnum",
        "--no-hinting",
        "--desubroutinize",
        "--name-IDs=1,2,3,4,5,6",
        "--drop-tables+=DSIG",
    ]
    subset.main(args)
    pinned.unlink(missing_ok=True)
    return dst


def verify(path):
    """Returns (glyph count, missing codepoints, digit advances, axes)."""
    font = TTFont(path)
    cmap = font.getBestCmap()
    missing = [f"U+{c:04X}" for c in REQUIRED_TEXT if c not in cmap]
    hmtx = font["hmtx"]
    advances = sorted({hmtx[cmap[ord(d)]][0] for d in "0123456789" if ord(d) in cmap})
    fvar = font.get("fvar")
    axes = {a.axisTag: (a.minValue, a.maxValue) for a in fvar.axes} if fvar else {}
    return len(cmap), missing, advances, axes


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    failures = []
    for src_name, out_name, _role in SOURCES:
        if not (SRC / src_name).exists():
            failures.append(f"{src_name}: source TTF missing under {SRC}")
            continue
        dst = build(src_name, out_name)
        size = dst.stat().st_size
        total += size
        glyphs, missing, advances, axes = verify(dst)
        axis_str = ",".join(f"{t} {lo:g}-{hi:g}" for t, (lo, hi) in axes.items()) or "static"
        print(f"{out_name:24} {size / 1024:6.1f} KB  {glyphs:4d} glyphs  [{axis_str}]")
        print(f"{'':24} digit advances: {advances}")
        if missing:
            failures.append(f"{out_name}: missing {','.join(missing)}")
        if len(advances) != 1:
            failures.append(
                f"{out_name}: digits are NOT equal-advance ({advances}) — canvas-drawn "
                f"numbers would shift as values change, and canvas 2D cannot request "
                f"tabular figures. Pick a face with uniform digit widths."
            )
    print(f"{'total':24} {total / 1024:6.1f} KB")
    if failures:
        raise SystemExit("FAILED:\n  " + "\n  ".join(failures))


if __name__ == "__main__":
    main()
