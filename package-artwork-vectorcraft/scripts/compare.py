#!/usr/bin/env python3
"""Compare a region of the original file (rendered by Apple PDFKit) with the open VectorCraft document.

    compare.py --original 01_source/x.ai --out-dir 03_work/compare --label pdfpart
               [--rect x y w h] [--scale 3] [--doc-index N] [--other output.pdf]

Writes <label>_orig.png, <label>_vc.png (or the --other file rendered by PDFKit), <label>_diff.png (changed
areas in red over the original) and prints JSON: changed-pixel share and the changed regions in document
points (top-left origin, as document.inspect bounds). Uses:
  * choosing the import mode: compare each open import with the original; the one with no regions wins;
  * after edits: the regions must be exactly the areas you meant to change.
Different renderers anti-alias edges differently, so tiny scattered regions are noise; read the images.
--out-dir must be inside the VectorCraft write root (the job folder). Pillow is needed for the diff.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vc import cmd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def pdfkit(src, out, rect, scale):
    args = ["swift", os.path.join(HERE, "render_pdf.swift"), src, out, "--scale", str(scale)]
    if rect:
        args += ["--rect"] + [str(v) for v in rect]
    subprocess.run(args, check=True)


def diff(a_path, b_path, out_path, scale, rect, cell=6, thresh=60, min_frac=0.04):
    from PIL import Image, ImageChops
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if b.size != a.size:
        b = b.resize(a.size)
    d = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > thresh else 0)
    w, h = d.size
    px = d.load()
    changed = sum(1 for y in range(h) for x in range(w) if px[x, y])
    gw, gh = (w + cell - 1) // cell, (h + cell - 1) // cell
    grid = [[False] * gw for _ in range(gh)]
    for gy in range(gh):
        for gx in range(gw):
            n = tot = 0
            for y in range(gy * cell, min(h, gy * cell + cell)):
                for x in range(gx * cell, min(w, gx * cell + cell)):
                    tot += 1
                    n += 1 if px[x, y] else 0
            grid[gy][gx] = tot and n / tot >= min_frac
    seen, regions = set(), []
    for gy in range(gh):
        for gx in range(gw):
            if grid[gy][gx] and (gx, gy) not in seen:
                stack, cells = [(gx, gy)], []
                seen.add((gx, gy))
                while stack:
                    cx, cy = stack.pop()
                    cells.append((cx, cy))
                    for nx in range(cx - 2, cx + 3):
                        for ny in range(cy - 2, cy + 3):
                            if 0 <= nx < gw and 0 <= ny < gh and grid[ny][nx] and (nx, ny) not in seen:
                                seen.add((nx, ny))
                                stack.append((nx, ny))
                if len(cells) < 2:
                    continue
                x0 = min(c[0] for c in cells) * cell / scale + rect[0]
                y0 = min(c[1] for c in cells) * cell / scale + rect[1]
                x1 = (max(c[0] for c in cells) + 1) * cell / scale + rect[0]
                y1 = (max(c[1] for c in cells) + 1) * cell / scale + rect[1]
                regions.append([round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)])
    red = Image.new("RGB", a.size, (230, 30, 30))
    overlay = Image.composite(red, a.point(lambda v: int(v * 0.55 + 115)), d)
    overlay.save(out_path)
    return {"changedPixelShare": round(changed / (w * h), 5), "regions": sorted(regions, key=lambda r: (r[1], r[0]))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default="cmp")
    ap.add_argument("--rect", nargs=4, type=float, help="x y w h in points, top-left origin (default: artboard 0)")
    ap.add_argument("--scale", type=float, default=3.0)
    ap.add_argument("--doc-index", type=int, help="activate this VectorCraft document first")
    ap.add_argument("--other", help="compare with this PDF/.ai rendered by PDFKit instead of the open document")
    a = ap.parse_args()
    out = os.path.abspath(a.out_dir)
    os.makedirs(out, exist_ok=True)
    rect = a.rect
    if rect is None:
        ab = cmd("document.inspect", {"depth": 0})["artboards"][0] if not a.other else None
        rect = [ab["x"], ab["y"], ab["width"], ab["height"]] if ab else None
    o_png = os.path.join(out, f"{a.label}_orig.png")
    v_png = os.path.join(out, f"{a.label}_{'other' if a.other else 'vc'}.png")
    pdfkit(os.path.abspath(a.original), o_png, rect, a.scale)
    if a.other:
        pdfkit(os.path.abspath(a.other), v_png, rect, a.scale)
    else:
        if a.doc_index is not None:
            cmd("document.activate", {"index": a.doc_index})
        params = {"path": v_png, "ppi": 72 * a.scale, "background": "white"}
        if rect:
            params["rect"] = rect
        cmd("document.export", params)
    res = {"original": o_png, "compared": v_png, "rect": rect}
    try:
        res.update(diff(o_png, v_png, os.path.join(out, f"{a.label}_diff.png"), a.scale, rect or [0, 0, 0, 0]))
        res["diff"] = os.path.join(out, f"{a.label}_diff.png")
    except ImportError:
        res["note"] = "Pillow is not installed: compare the two images by eye"
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
