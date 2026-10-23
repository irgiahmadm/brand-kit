"""Clean-geometry helpers for logo construction (import from your own construction script).

Needs: pip install skia-pathops fonttools

Why this exists: drawing logos by stacking SVG shapes with white strokes on top ("fake gaps") looks fine on
white and breaks everywhere else. Real logos need real holes. These helpers do boolean ops on paths so
gaps, knockouts and overlaps become true geometry that survives one-colour, reversed and coloured backgrounds.

Typical recipe:

    from geometry import *
    a = to_path(my_shape_d)                         # SVG path data -> Path
    b = to_path(my_shape_d, tx=150)                 # same shape moved
    coin = to_path(circle_d(180, 128, 26))
    b = knockout(b, coin, gap=11)                   # coin sits in front of b with an 11-unit gap
    a = knockout(a, union(b, coin, bridge(180, 128, 26)), gap=11)   # a sits behind everything
    a = drop_islands(a, 60)                          # remove slivers left by the cuts
    write_svg("mark.svg", [(a, "#302017", "main"), (b, "#302017", "main"), (coin, "#FD8537", "accent")])

Rules of thumb learned the hard way:
- Build curves from circular arcs; where a straight/curve meets a circle, put the Bezier control point ON the
  circle's tangent or you get a visible "shoulder" bump.
- Keep one gap size for every knockout in a mark so it reads as one system.
- After every knockout, look for tiny wedges where two cuts meet (a crevice). Either fill the crevice in the
  cutter (bridge()) or grow the front shape slightly so its halo swallows the wedge.
- Tag every path with a role (main / accent / ...) so recolouring scripts know what is what.
"""
import math
import pathops
from fontTools.svgLib.path import parse_path
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

__all__ = ["pt", "circle_d", "rect_d", "to_path", "to_d", "transform", "union", "subtract", "intersect",
           "halo", "knockout", "bridge", "drop_islands", "bounds", "write_svg"]


def pt(r, deg, cx=0.0, cy=0.0):
    """Point on a circle; screen angles (0 = right, 90 = down)."""
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def circle_d(cx, cy, r):
    return f"M{cx-r} {cy} A{r} {r} 0 1 0 {cx+r} {cy} A{r} {r} 0 1 0 {cx-r} {cy} Z"


def rect_d(x, y, w, h):
    return f"M{x} {y} H{x+w} V{y+h} H{x} Z"


def to_path(d, tx=0, ty=0, scale=1.0):
    """SVG path data (arcs allowed) -> pathops.Path, optionally scaled then moved."""
    p = pathops.Path()
    parse_path(d, TransformPen(p.getPen(), (scale, 0, 0, scale, tx, ty)))
    return p


def transform(p, a=1, b=0, c=0, d=1, e=0, f=0):
    q = pathops.Path()
    p.draw(TransformPen(q.getPen(), (a, b, c, d, e, f)))
    return q


def to_d(p, precision=2):
    pen = SVGPathPen(None, ntos=lambda v: (f"{v:.{precision}f}").rstrip("0").rstrip("."))
    p.draw(pen)
    return pen.getCommands()


def union(*ps):
    out = pathops.Path()
    for p in ps:
        out = pathops.op(out, p, pathops.PathOp.UNION)
    return out


def subtract(a, b):
    return pathops.op(a, b, pathops.PathOp.DIFFERENCE)


def intersect(a, b):
    return pathops.op(a, b, pathops.PathOp.INTERSECTION)


def halo(p, gap):
    """p grown by `gap` on every side (round joins) — the cutter for a uniform knockout gap."""
    h = pathops.Path()
    p.draw(h.getPen())
    h.stroke(gap * 2, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    h.convertConicsToQuads()          # stroke() emits conics; booleans need quads
    return pathops.op(h, p, pathops.PathOp.UNION)


def knockout(back, front, gap):
    """Cut `front` (plus a uniform gap) out of `back`: front appears to sit in front of back."""
    return subtract(back, halo(front, gap))


def bridge(cx, cy, r, length=40, direction=1):
    """Rectangle from a circle's centre outward — union it into a cutter to fill the crevice between two halos."""
    x0 = cx if direction > 0 else cx - length
    return to_path(rect_d(x0, cy - r, length, 2 * r))


def drop_islands(p, min_area=60):
    """Remove contours smaller than min_area (slivers produced by knockouts)."""
    out = pathops.Path()
    for c in p.contours:
        if abs(c.area) >= min_area:
            out = pathops.op(out, c, pathops.PathOp.UNION)
    return out


def bounds(*ps):
    bs = [p.bounds for p in ps]
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def write_svg(path, layers, pad=14, height=256, title="Logo"):
    """layers: [(Path, fill, role)] -> SVG with data-role on every path (used by make_kit.py)."""
    x0, y0, x1, y1 = bounds(*[l[0] for l in layers])
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    body = "\n".join(f'<path data-role="{role}" fill="{fill}" d="{to_d(p)}"/>' for p, fill, role in layers)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-pad:.2f} {y0-pad:.2f} {w:.2f} {h:.2f}" '
           f'width="{w/h*height:.0f}" height="{height}">\n<title>{title}</title>\n{body}\n</svg>\n')
    open(path, "w", encoding="utf-8").write(svg)
    return svg
