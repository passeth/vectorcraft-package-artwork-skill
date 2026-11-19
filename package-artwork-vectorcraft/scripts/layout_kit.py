#!/usr/bin/env python3
"""Building blocks for making print artwork in VectorCraft from a designer sheet / mockup image (new mode).

Import it from a job's own build script (03_work/build_*.py) so the build is recorded and can be re-run:

    import sys; sys.path.insert(0, "<skill>/scripts")
    from layout_kit import Ref, Doc, ean13_pattern

    ref = Ref("01_source/sheet.png", ppi=300, background=(140, 135, 133))   # px -> pt, ink detection
    doc = Doc()
    box = ref.tight((540, 1050, 1030, 1122))                                # measured ink box, pt
    tid, info = doc.fit_text("PRODUCT NAME", "Helvetica Neue", "Bold", box, swatch="WHITE INK", size=21)

Measured coordinates are document points with the origin at the artboard's top-left (the space of
document.inspect bounds), which is the reference image placed 1:1 at (0, 0). Requires Pillow for Ref.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vc import cmd  # noqa: E402


# --------------------------------------------------------------------------------------------- reference
class Ref:
    """A raster reference (designer sheet export). ppi decides px -> pt; background is the colour that is not ink."""

    def __init__(self, path, ppi=300, background=(255, 255, 255), ink_threshold=60):
        from PIL import Image
        self.path = path
        self.im = Image.open(path).convert("RGB")
        self.px = self.im.load()
        self.pt = 72.0 / ppi
        self.bg = background
        self.th = ink_threshold

    def strength(self, c):
        return sum(abs(c[i] - self.bg[i]) for i in range(3))

    def is_ink(self, c):
        return self.strength(c) > self.th

    def tight(self, box, test=None):
        """Tight ink box in pt [x, y, w, h] inside px box (x0, y0, x1, y1), optionally filtered by test(rgb)."""
        x0, y0, x1, y1 = box
        xs, ys = [], []
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                c = self.px[x, y]
                if self.is_ink(c) and (test is None or test(c)):
                    xs.append(x)
                    ys.append(y)
        if not xs:
            raise ValueError(f"no ink in {box}")
        p = self.pt
        return [min(xs) * p, min(ys) * p, (max(xs) - min(xs) + 1) * p, (max(ys) - min(ys) + 1) * p]

    def rows(self, box, test=None):
        """Horizontal ink bands (text lines) in a px box: [[y0, y1, x0, x1], ...] in px."""
        x0, y0, x1, y1 = box
        out, cur = [], None
        for y in range(y0, y1 + 1):
            xs = [x for x in range(x0, x1 + 1) if self.is_ink(self.px[x, y]) and (test is None or test(self.px[x, y]))]
            if xs:
                cur = cur or [y, y, min(xs), max(xs)]
                cur[1], cur[2], cur[3] = y, min(cur[2], min(xs)), max(cur[3], max(xs))
            elif cur:
                out.append(cur)
                cur = None
        if cur:
            out.append(cur)
        return out

    def mask(self, box, out_path, test=None, upscale=4):
        """Black-on-white mask of the ink in a px box, upscaled, for Image Trace (logo mode)."""
        from PIL import Image
        x0, y0, x1, y1 = box
        vals = []
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                c = self.px[x, y]
                s = self.strength(c)
                if test is not None and s > self.th and not test(c):
                    s = 0
                vals.append(s)
        smax = max(vals) or 1
        m = Image.new("L", (x1 - x0 + 1, y1 - y0 + 1))
        m.putdata([max(0, 255 - int(v * 255 / smax)) for v in vals])
        m.resize((m.width * upscale, m.height * upscale), Image.LANCZOS).save(out_path)
        p = self.pt
        return [x0 * p, y0 * p, (x1 - x0 + 1) * p, (y1 - y0 + 1) * p]

    def compare(self, box, out_dir, label, threshold=70):
        """Export the same px region from the open document and save reference | ours | difference."""
        from PIL import Image, ImageChops
        os.makedirs(out_dir, exist_ok=True)
        x0, y0, x1, y1 = box
        ref = self.im.crop((x0, y0, x1 + 1, y1 + 1))
        vc_path = os.path.join(out_dir, f"{label}_vc.png")
        p = self.pt
        cmd("document.export", {"path": vc_path, "rect": [x0 * p, y0 * p, (x1 - x0 + 1) * p, (y1 - y0 + 1) * p],
                                "ppi": 72 / p, "background": "white"})
        ours = Image.open(vc_path).convert("RGB").resize(ref.size)
        d = ImageChops.difference(ref, ours).convert("L").point(lambda v: 255 if v > threshold else 0)
        diff = Image.composite(Image.new("RGB", ref.size, (230, 30, 30)), ref.point(lambda v: int(v * .5 + 120)), d)
        side = Image.new("RGB", (ref.width * 3 + 20, ref.height), (255, 255, 255))
        for i, im in enumerate((ref, ours, diff)):
            side.paste(im, (i * (ref.width + 10), 0))
        path = os.path.join(out_dir, f"{label}_side.png")
        side.save(path)
        return {"side": path, "changedShare": round(sum(1 for v in d.getdata() if v) / (ref.width * ref.height), 4)}


# ----------------------------------------------------------------------------------------------- document
class Doc:
    """Helpers over the open VectorCraft document."""

    def fill(self, ids, swatch=None, color=None, stroke_none=True):
        params = {"ids": ids}
        if swatch:
            params["swatch"] = swatch
        elif color:
            params["color"] = color
        if len(params) > 1:
            cmd("paint.setFill", params)
        if stroke_none:
            cmd("paint.setStroke", {"ids": ids, "none": True})

    def rect(self, box, swatch=None, color=None):
        x, y, w, h = box
        rid = cmd("shape.rectangle", {"x": x, "y": y, "width": w, "height": h})["id"]
        self.fill([rid], swatch, color)
        return rid

    def layer(self, name, top=True):
        lid = cmd("layer.new", {"name": name, "top": top})["id"]
        cmd("layer.setCurrent", {"id": lid})
        return lid

    def ink_bounds(self, obj_id):
        """True ink bounds of a type object (document.inspect reports the em box): outline a copy, measure, delete."""
        cp = cmd("object.move", {"ids": [obj_id], "dx": 0, "dy": 0, "copy": True})["ids"]
        cmd("select.set", {"ids": cp})
        out = cmd("type.createOutlines", {})["ids"]
        nodes = cmd("document.inspect", {"ids": out})["nodes"]
        x0 = min(n["bounds"]["x"] for n in nodes)
        y0 = min(n["bounds"]["y"] for n in nodes)
        x1 = max(n["bounds"]["x"] + n["bounds"]["width"] for n in nodes)
        y1 = max(n["bounds"]["y"] + n["bounds"]["height"] for n in nodes)
        cmd("edit.clear", {"ids": out})
        cmd("select.none", {})
        return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}

    def style_prefix(self, tid, text, prefix, style="Bold"):
        """Restyle `prefix` of a type object; text ranges are UTF-8 byte offsets."""
        i = text.index(prefix)
        start = len(text[:i].encode("utf-8"))
        cmd("text.setRangeStyle", {"id": tid, "start": start, "end": start + len(prefix.encode("utf-8")), "style": style})

    def fit_text(self, text, font, style, target, swatch=None, color=None, size=10, tracking=0, align="left",
                 width_by="tracking", max_tracking=(-30, 300), bold=(), rounds=3):
        """Point type whose INK box matches target [x, y, w, h] (pt).

        Height sets the size. Width: width_by="tracking" (falls back to horizontal scale when the tracking it
        needs is tighter than max_tracking[0], so letters are not crushed), "hscale" (tracking stays), or None.
        """
        x, y, w, h = target
        tid = cmd("text.create", {"x": x, "y": y + h, "text": text, "font": font, "style": style, "size": size})["id"]
        cmd("text.setStyle", {"ids": [tid], "fill": "#000000", "tracking": tracking})
        for p in bold:
            self.style_prefix(tid, text, p)
        hscale = 100.0
        n = max(1, len(text) - 1)
        for _ in range(rounds):
            b = self.ink_bounds(tid)
            size *= h / b["height"]
            cmd("text.setStyle", {"ids": [tid], "size": round(size, 3)})
            if not width_by:
                continue
            b = self.ink_bounds(tid)
            if width_by == "tracking":
                want = tracking + (w - b["width"]) / n / size * 1000
                if want < max_tracking[0]:
                    width_by, tracking = "hscale", max_tracking[0]
                    cmd("text.setStyle", {"ids": [tid], "tracking": tracking})
                else:
                    tracking = min(max_tracking[1], want)
                    cmd("text.setStyle", {"ids": [tid], "tracking": round(tracking, 1)})
                    continue
            b = self.ink_bounds(tid)
            hscale *= w / b["width"]
            cmd("text.setFormat", {"ids": [tid], "hScale": round(hscale, 2)})
        b = self.ink_bounds(tid)
        dx = {"left": x - b["x"], "right": (x + w) - (b["x"] + b["width"]),
              "center": (x + w / 2) - (b["x"] + b["width"] / 2)}[align]
        cmd("object.move", {"ids": [tid], "dx": dx, "dy": y - b["y"]})
        self.fill([tid], swatch, color)
        b = self.ink_bounds(tid)
        return tid, {"size": round(size, 3), "tracking": round(tracking, 1), "hScale": round(hscale, 2),
                     "ink": [round(b[k], 2) for k in ("x", "y", "width", "height")],
                     "target": [round(v, 2) for v in target]}

    def paragraph(self, lines, target, font, size, leading, tracking=-25, last_lines=(), bold=(), swatch=None,
                  color=None):
        """Area type with the designer's line breaks: one paragraph per line, all justified except last_lines.

        VectorCraft has no 'justify, last line left', so each line is its own paragraph. Horizontal scale is
        chosen so the widest line fits the frame (no extra wraps). target [x, y, w, h]: x/w the column,
        y the ink top of the first line.
        """
        x, y, w, _ = target
        widest = 0.0
        for line in lines:
            t = cmd("text.create", {"x": 0, "y": 0, "text": line, "font": font, "style": "Regular", "size": size})["id"]
            cmd("text.setStyle", {"ids": [t], "tracking": tracking})
            for p in bold:
                if line.startswith(p):
                    self.style_prefix(t, line, p)
            widest = max(widest, cmd("document.inspect", {"ids": [t]})["nodes"][0]["bounds"]["width"])
            cmd("edit.clear", {"ids": [t]})
        hscale = min(100.0, 100.0 * (w - 1.0) / widest)
        text = "\n".join(lines)
        tid = cmd("text.create", {"x": x, "y": y, "text": text, "font": font, "style": "Regular", "size": size,
                                  "area": {"width": w, "height": leading * len(lines) + 12}})["id"]
        cmd("text.setStyle", {"ids": [tid], "leading": leading, "tracking": tracking, "fill": "#000000",
                              "justify": "justifyAll"})
        cmd("text.setFormat", {"ids": [tid], "hScale": round(hscale, 2)})
        offs, pos = [], 0
        for line in lines:
            nb = len(line.encode("utf-8"))
            offs.append((pos, pos + nb))
            pos += nb + 1
        for i in last_lines:
            cmd("text.setStyle", {"ids": [tid], "justify": "left", "start": offs[i][0], "end": offs[i][1]})
        for p in bold:
            for i, line in enumerate(lines):
                if line.startswith(p):
                    cmd("text.setRangeStyle", {"id": tid, "start": offs[i][0],
                                               "end": offs[i][0] + len(p.encode("utf-8")), "style": "Bold"})
        b = self.ink_bounds(tid)
        cmd("object.move", {"ids": [tid], "dx": x - b["x"], "dy": y - b["y"]})
        self.fill([tid], swatch, color)
        b = self.ink_bounds(tid)
        return tid, {"size": size, "leading": leading, "tracking": tracking, "hScale": round(hscale, 2),
                     "lines": len(lines), "ink": [round(b[k], 2) for k in ("x", "y", "width", "height")]}

    def trace(self, mask_path, rect_pt, swatch=None, color=None, noise=4):
        """Place a black-on-white mask at rect_pt and trace it in Logo mode; returns the traced group id."""
        img = cmd("file.place", {"path": mask_path, "link": False, "rect": rect_pt})
        img_id = img["ids"][0] if "ids" in img else img["id"]
        r = cmd("imageTrace.makeAndExpand", {"id": img_id, "params": {"mode": "logo", "logoColors": ["#000000"],
                                                                         "ignoreWhite": True, "noise": noise}})
        self.fill([r["id"]], swatch, color)
        return r["id"]

    def ean13(self, code, x, top, module, height, guard_extra=0.0, swatch=None, color=None, name=None):
        """EAN-13 bars as filled rectangles (no quiet zone drawn). Returns the group id and the spec."""
        pat = ean13_pattern(code)
        guards = set(range(0, 3)) | set(range(45, 50)) | set(range(92, 95))
        bars, i = [], 0
        while i < 95:
            if pat[i] == "1":
                j = i
                while j < 95 and pat[j] == "1":
                    j += 1
                bars.append(self.rect([x + i * module, top, (j - i) * module,
                                       height + (guard_extra if i in guards else 0)], swatch, color))
                i = j
            else:
                i += 1
        cmd("select.set", {"ids": bars})
        gid = cmd("object.group", {})["id"]
        cmd("object.setProps", {"id": gid, "name": name or f"EAN-13 {code}"})
        cmd("select.none", {})
        mm = module / 72 * 25.4
        return gid, {"code": code, "moduleMm": round(mm, 4), "magnificationPct": round(mm / 0.33 * 100, 1),
                     "belowGs1Minimum": mm < 0.264}


# ------------------------------------------------------------------------------------------------ barcode
_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
_R = ["".join("1" if b == "0" else "0" for b in c) for c in _L]
_G = ["".join(reversed(c)) for c in _R]
_PAR = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_check_digit(first12):
    d = [int(c) for c in first12]
    return (10 - sum(v * (3 if i % 2 else 1) for i, v in enumerate(d)) % 10) % 10


def ean13_pattern(code):
    """95 modules ('1' = bar) of a 13-digit EAN; raises on a wrong check digit."""
    if len(code) != 13 or not code.isdigit():
        raise ValueError("EAN-13 needs 13 digits")
    if ean13_check_digit(code[:12]) != int(code[12]):
        raise ValueError(f"check digit of {code} should be {ean13_check_digit(code[:12])}")
    d = [int(c) for c in code]
    left = "".join((_L if p == "L" else _G)[v] for p, v in zip(_PAR[d[0]], d[1:7]))
    return "101" + left + "01010" + "".join(_R[v] for v in d[7:]) + "101"
