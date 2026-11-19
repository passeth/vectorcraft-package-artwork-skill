#!/usr/bin/env python3
"""Map a front view of a squeeze tube (a concept / mockup image) onto the flat print film.

A filled tube is flat at the crimp and round at the shoulder. At every height its cross-section is taken as
an ellipse whose FRONT half is half the circumference (pi*D/2): flat at the crimp (depth 0), a circle at the
shoulder. A point seen at horizontal offset x on that row lies at arc length s(x) from the centre line, so
content keeps its true size near the centre of round rows and the visible edges map to the panel edges.

    from tube_unwrap import TubeSpec, ConceptTube
    spec = TubeSpec(diameter=40, length=150)                      # mm
    tube = ConceptTube("01_source/concept.png", spec, x_range=(0, 640), is_tube=lambda c: ...)
    x_mm, y_mm = tube.to_film(330, 600)                          # on the front panel, from the crimp top
    box = tube.box((120, 291, 560, 641), test=lambda c: c[0] < 120)   # ink box [x, y, w, h] in mm

`python3 tube_unwrap.py <image> <diameter> <length> --sample X Y [--x-range x0 x1] [--tol 25]` detects the tube
from the colour at a point on its plain body (not on type) and prints the shape check. Detection keeps the
rows' outer edges, so type and stickers inside the tube do not matter; a cap or background of a similar colour
does — narrow --x-range to the one tube. Pillow is needed for ConceptTube (not for the math).
"""
import math
import sys


class TubeSpec:
    def __init__(self, diameter, length, seal=10.0, safe_bottom=8.0):
        self.diameter = float(diameter)
        self.length = float(length)
        self.seal = float(seal)                 # unprinted sealing/cutting end (tube maker's spec)
        self.safe_bottom = float(safe_bottom)   # keep type off the shoulder
        self.flat_width = math.pi * self.diameter      # film width = circumference
        self.panel = self.flat_width / 2                # front panel = back panel

    def __repr__(self):
        return (f"TubeSpec(D={self.diameter} mm, L={self.length} mm, film {self.flat_width:.2f} x {self.length} mm, "
                f"panel {self.panel:.2f} mm)")


def ellipse_arc(a, b, t, n=200):
    """Arc length on x = a sin u, z = b cos u from u = 0 to t (midpoint rule)."""
    s, du = 0.0, t / n
    for i in range(n):
        u = (i + 0.5) * du
        s += math.sqrt((a * math.cos(u)) ** 2 + (b * math.sin(u)) ** 2) * du
    return s


_depth_cache = {}


def depth_for(a, panel):
    """Depth b of the ellipse whose front half (u = -pi/2 .. pi/2) is `panel` long for visible half-width a."""
    key = (round(a, 3), round(panel, 3))
    if key in _depth_cache:
        return _depth_cache[key]
    if 2 * a >= panel:
        b = 0.0
    else:
        lo, hi = 0.0, panel
        for _ in range(48):
            mid = (lo + hi) / 2
            if 2 * ellipse_arc(a, mid, math.pi / 2) < panel:
                lo = mid
            else:
                hi = mid
        b = (lo + hi) / 2
    _depth_cache[key] = b
    return b


def unwrap_x(offset_mm, half_width_mm, panel):
    """Film x (mm, 0..panel) of a point seen offset_mm from the row centre on a row half_width_mm wide."""
    a = half_width_mm
    xm = max(-a, min(a, offset_mm))
    b = depth_for(a, panel)
    s = ellipse_arc(a, b, math.asin(xm / a)) if b > 0 else xm * (panel / 2) / a
    return panel / 2 + s


class ConceptTube:
    """One tube in a concept image. Rows are found from is_tube(rgb) inside x_range; y_top is the crimp edge,
    y_bottom the shoulder (both auto-detected unless given). Vertical scale: (y_bottom - y_top) px = spec.length."""

    def __init__(self, image_path, spec, x_range, is_tube, y_top=None, y_bottom=None, min_pixels=50):
        from PIL import Image
        self.im = Image.open(image_path).convert("RGB")
        self.px = self.im.load()
        self.spec = spec
        x0, x1 = x_range
        rows = {}
        for y in range(self.im.height):
            xs = [x for x in range(x0, x1) if is_tube(self.px[x, y])]
            if len(xs) >= min_pixels:
                rows[y] = (min(xs), max(xs))
        if not rows:
            raise ValueError("no tube rows found: check x_range and is_tube")
        self.y_top = y_top if y_top is not None else min(rows)
        self.y_bottom = y_bottom if y_bottom is not None else max(rows)
        self.rows = rows
        self.k = (self.y_bottom - self.y_top) / spec.length       # px per mm

    def row(self, y):
        y = min(max(int(round(y)), self.y_top), self.y_bottom)
        while y not in self.rows and y < self.y_bottom:
            y += 1
        return self.rows[y]

    def to_film(self, x, y):
        l, r = self.row(y)
        half = (r - l) / 2 / self.k
        return (unwrap_x((x - (l + r) / 2) / self.k, half, self.spec.panel),
                (y - self.y_top) / (self.y_bottom - self.y_top) * self.spec.length)

    def box(self, px_box, test):
        """Ink box [x, y, w, h] in film mm of the pixels passing test(rgb) inside px_box (x0, y0, x1, y1).
        The film is a rectangle, but in the image the tube looks wider at the flat crimp (pi*D/2) than at the round
        shoulder (D), so pixels map to film mm differently on each row: every row's ink extent is mapped with its
        own row's width and centre, and the box spans their film-space extremes."""
        x0, y0, x1, y1 = px_box
        film_x, ys = [], []
        for y in range(y0, y1 + 1):
            xs = [x for x in range(x0, x1 + 1) if test(self.px[x, y])]
            if xs:
                film_x += [self.to_film(min(xs), y)[0], self.to_film(max(xs) + 1, y)[0]]
                ys.append(y)
        if not ys:
            raise ValueError(f"no matching pixels in {px_box}")
        top = self.to_film(x0, min(ys))[1]
        bottom = self.to_film(x0, max(ys) + 1)[1]
        return [min(film_x), top, max(film_x) - min(film_x), bottom - top]

    def report(self):
        """Shape check: width ratio shoulder/crimp vs the physical 2/pi, and implied length from the crimp width."""
        top = self.rows[min(self.rows, key=lambda y: abs(y - (self.y_top + 0.1 * (self.y_bottom - self.y_top))))]
        bot = self.rows[min(self.rows, key=lambda y: abs(y - (self.y_top + 0.9 * (self.y_bottom - self.y_top))))]
        wt, wb = top[1] - top[0], bot[1] - bot[0]
        k_flat = wt / self.spec.panel
        warn = []
        if self.y_top <= 1 or self.y_bottom >= self.im.height - 2:
            warn.append("the tube reaches the image edge: the background probably matches the body colour "
                        "(lower --tol, or narrow --x-range)")
        if abs(wb / wt - 2 / math.pi) > 0.15:
            warn.append("shoulder/crimp width ratio is far from a real tube (2/pi): check the detection or the spec")
        if abs((self.y_bottom - self.y_top) / k_flat - self.spec.length) > 0.1 * self.spec.length:
            warn.append("the length implied by the crimp width differs from the spec by more than 10 %")
        return {"warnings": warn, "yTop": self.y_top, "yBottom": self.y_bottom, "pxPerMmFromLength": round(self.k, 3),
                "pxPerMmFromCrimpWidth": round(k_flat, 3),
                "impliedLengthMm": round((self.y_bottom - self.y_top) / k_flat, 1),
                "shoulderToCrimpWidth": round(wb / wt, 3), "physicalRoundToFlat": round(2 / math.pi, 3)}


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("diameter", type=float)
    ap.add_argument("length", type=float)
    ap.add_argument("--sample", nargs=2, type=int, required=True, metavar=("X", "Y"),
                    help="a point on the tube's plain body colour")
    ap.add_argument("--x-range", nargs=2, type=int, metavar=("X0", "X1"))
    ap.add_argument("--tol", type=int, default=25, help="colour distance (sum of channel differences)")
    a = ap.parse_args()
    from PIL import Image
    im = Image.open(a.image).convert("RGB")
    ref = im.getpixel(tuple(a.sample))

    def body(c):
        return sum(abs(c[i] - ref[i]) for i in range(3)) <= a.tol

    xr = tuple(a.x_range) if a.x_range else (0, im.width)
    t = ConceptTube(a.image, TubeSpec(a.diameter, a.length), xr, body)
    print(json.dumps({"spec": repr(t.spec), "bodyColour": "#%02x%02x%02x" % ref, **t.report()}, indent=1))
