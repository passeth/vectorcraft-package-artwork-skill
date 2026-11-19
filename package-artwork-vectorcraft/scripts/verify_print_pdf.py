#!/usr/bin/env python3
"""Check a print PDF before it goes out (stdlib only).

    verify_print_pdf.py <print.pdf> [--expect-spots "PANTONE 7499 C,WHITE INK"] [--original 01_source/x.ai]

Reports and checks: fonts and text operators (an outlined file has none), spot colours (Separation and
DeviceN names), raster images, pages and their MediaBox/TrimBox/BleedBox. With --expect-spots every named
spot must be there; with --original the spots must equal the original's. Exit 1 when a check fails.
"""
import argparse
import json
import re
import sys
import zlib


def streams(data):
    for m in re.finditer(rb"stream\r?\n", data):
        hdr = data[max(0, m.start() - 600):m.start()]
        lens = re.findall(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", hdr)
        if not lens:
            continue
        raw = data[m.end():m.end() + int(lens[-1])]
        if b"/FlateDecode" in hdr[hdr.rfind(b"<<"):]:
            try:
                yield hdr, zlib.decompress(raw)
            except zlib.error:
                continue
        else:
            yield hdr, raw


def spot_names(blob):
    names = set()
    for n in re.findall(rb"/Separation\s*/([^\s/\[\]()<>]+)", blob):
        names.add(n)
    for arr in re.findall(rb"/DeviceN\s*\[([^\]]*)\]", blob):
        names.update(re.findall(rb"/([^\s/\[\]()<>]+)", arr))
    out = set()
    for n in names:
        s = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), n).decode("utf-8", "replace")
        if s not in ("All", "None"):
            out.add(s)
    return out


def inspect(path):
    data = open(path, "rb").read()
    rep = {"file": path, "version": data[:8].decode("latin-1", "replace").strip(),
           "objectStreams": b"/ObjStm" in data}
    rep["fontObjects"] = len(re.findall(rb"/Type\s*/Font\b", data))
    rep["fontFiles"] = len(re.findall(rb"/FontFile[23]?\b", data))
    bt = tf = 0
    spots = spot_names(data)
    for _, s in streams(data):
        bt += len(re.findall(rb"(?<![A-Za-z])BT(?![A-Za-z])", s))
        tf += len(re.findall(rb"(?<![A-Za-z])Tf(?![A-Za-z])", s))
        spots |= spot_names(s)
    rep["textBlocks"], rep["fontSelects"] = bt, tf
    rep["spots"] = sorted(spots)
    rep["images"] = len(re.findall(rb"/Subtype\s*/Image\b", data))
    rep["pages"] = len(re.findall(rb"/Type\s*/Page\b(?!s)", data))
    rep["boxes"] = {k.decode(): v.decode().split() for k, v in
                    re.findall(rb"/(MediaBox|TrimBox|BleedBox)\s*\[([^\]]*)\]", data)[:6]}
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--expect-spots")
    ap.add_argument("--original")
    a = ap.parse_args()
    rep = inspect(a.pdf)
    fails = []
    if rep["fontObjects"] or rep["fontFiles"] or rep["textBlocks"] or rep["fontSelects"]:
        fails.append("live text or fonts remain (not fully outlined)")
    if rep["objectStreams"]:
        fails.append("object streams present: font/text checks may be incomplete")
    if a.expect_spots:
        missing = [s for s in (x.strip() for x in a.expect_spots.split(",")) if s and s not in rep["spots"]]
        if missing:
            fails.append(f"expected spot colours missing: {missing}")
    if a.original:
        orig = inspect(a.original)["spots"]
        rep["originalSpots"] = orig
        if sorted(orig) != rep["spots"]:
            fails.append(f"spot colours differ from the original: {orig} vs {rep['spots']}")
    rep["ok"] = not fails
    rep["failures"] = fails
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
