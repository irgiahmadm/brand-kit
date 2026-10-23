"""Turn text set in a (variable) font into outlined SVG path data — wordmarks must never depend on installed fonts.

Usage:  python outline_text.py "Scrimpanzee" SpaceGrotesk.ttf --axes wght=700 --cap 120 -o wordmark.svg
Library: from outline_text import outline  ->  pathops.Path with baseline at y=0, caps reaching y=-cap

Get Google fonts as TTF from https://github.com/google/fonts (ofl/<family>/<Family>[axes].ttf) and check the
licence allows logo use (OFL does). Put downloaded fonts in their own folder.
Kerning: GPOS kerning is applied for plain pairs when present; check the spacing visually anyway and nudge
with --tracking if needed (optical spacing beats metrics in a logo).
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from geometry import to_path, to_d, bounds


def _kern_pairs(font):
    pairs = {}
    if "GPOS" not in font:
        return pairs
    try:
        for lookup in font["GPOS"].table.LookupList.Lookup:
            if lookup.LookupType != 2:
                continue
            for st in lookup.SubTable:
                if getattr(st, "Format", None) == 1 and hasattr(st, "PairSet"):
                    firsts = st.Coverage.glyphs
                    for i, ps in enumerate(st.PairSet):
                        for rec in ps.PairValueRecord:
                            v = getattr(rec.Value1, "XAdvance", 0) if rec.Value1 else 0
                            if v:
                                pairs[(firsts[i], rec.SecondGlyph)] = v
    except Exception:
        pass
    return pairs


def load_font(font_path, axes=None):
    f = TTFont(font_path)
    if "fvar" in f:
        defaults = {a.axisTag: a.defaultValue for a in f["fvar"].axes}
        defaults.update(axes or {})
        f = instancer.instantiateVariableFont(f, defaults)
    return f


def outline(text, font_path, cap, axes=None, tracking=0.0):
    f = load_font(font_path, axes)
    gs, cmap, hmtx = f.getGlyphSet(), f.getBestCmap(), f["hmtx"]
    cap_h = getattr(f["OS/2"], "sCapHeight", 0) or f["head"].unitsPerEm * 0.7
    s = cap / cap_h
    kern = _kern_pairs(f)
    x, ds, prev = 0.0, [], None
    for ch in text:
        g = cmap.get(ord(ch))
        if g is None:
            raise SystemExit(f"glyph for {ch!r} missing in {font_path}")
        if prev:
            x += kern.get((prev, g), 0) * s
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}")
        gs[g].draw(TransformPen(pen, (s, 0, 0, -s, x, 0)))
        ds.append(pen.getCommands())
        x += hmtx[g][0] * s + tracking * cap
        prev = g
    return to_path(" ".join(d for d in ds if d))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text"); ap.add_argument("font")
    ap.add_argument("--axes", nargs="*", default=[], help="e.g. wght=600 wdth=100")
    ap.add_argument("--cap", type=float, default=100); ap.add_argument("--tracking", type=float, default=0)
    ap.add_argument("--fill", default="#000"); ap.add_argument("-o", "--out", default="wordmark.svg")
    a = ap.parse_args()
    axes = {k: float(v) for k, v in (x.split("=") for x in a.axes)}
    p = outline(a.text, a.font, a.cap, axes, a.tracking)
    x0, y0, x1, y1 = bounds(p); pad = a.cap * 0.1
    open(a.out, "w", encoding="utf-8").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-pad:.2f} {y0-pad:.2f} {x1-x0+2*pad:.2f} {y1-y0+2*pad:.2f}">'
        f'<path data-role="text" fill="{a.fill}" d="{to_d(p)}"/></svg>\n')
    print("wrote", a.out)
