#!/usr/bin/env python3
"""Find the font files a job needs, copy them into <job>/02_fonts and register them in VectorCraft.

    fonts.py --job DIR [--from-pdf 01_source/x.ai] [--from-doc] [--want "Family[:Style]" ...]
             [--search DIR ...] [--dry-run]

What is wanted:
  --from-pdf  the fonts the original's PDF page uses (BaseFont PostScript names, subset prefix removed);
  --from-doc  the open VectorCraft document's missing fonts (text.missingFonts);
  --want      fonts the revision introduces, e.g. --want "Noto Serif KR" (family names VectorCraft lists).
Where to look: <job>/02_fonts, then each --search folder (e.g. the team font library), ~/Library/Fonts,
/Library/Fonts. Files are matched on their name table (family, style, full and PostScript names).
Matching files are copied into 02_fonts (inside the automation read root) and registered with
text.findFontFiles + text.addFontFiles, which copy them into VectorCraft's own Fonts folder (app-scoped,
not a system install). Register fonts BEFORE opening a .ai: its editing data binds fonts when it opens.
Only use fonts the company is licensed to use. Fonts already installed are left alone.
"""
import argparse
import json
import os
import re
import shutil
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vc import VCError, cmd  # noqa: E402

FONT_EXT = (".ttf", ".otf", ".ttc", ".otc")


def norm(s):
    return re.sub(r"[^0-9a-z]", "", (s or "").lower())


def name_tables(path):
    """Yield {nameID: set(strings)} for each face in a font file."""
    with open(path, "rb") as f:
        data = f.read()
    offsets = [0]
    if data[:4] == b"ttcf":
        n = struct.unpack(">I", data[8:12])[0]
        offsets = list(struct.unpack(">%dI" % n, data[12:12 + 4 * n]))
    for off in offsets:
        num = struct.unpack(">H", data[off + 4:off + 6])[0]
        tables = {}
        for i in range(num):
            tag, _, toff, tlen = struct.unpack(">4sIII", data[off + 12 + 16 * i:off + 28 + 16 * i])
            tables[tag] = (toff, tlen)
        if b"name" not in tables:
            continue
        noff, _ = tables[b"name"]
        _, count, so = struct.unpack(">HHH", data[noff:noff + 6])
        names = {}
        for i in range(count):
            pid, eid, lid, nid, ln, o = struct.unpack(">HHHHHH", data[noff + 6 + 12 * i:noff + 18 + 12 * i])
            if nid not in (1, 2, 4, 6, 16, 17):
                continue
            raw = data[noff + so + o:noff + so + o + ln]
            try:
                s = raw.decode("utf-16-be") if pid in (0, 3) else raw.decode("mac_roman")
            except UnicodeDecodeError:
                continue
            names.setdefault(nid, set()).add(s.strip())
        yield names


def index_fonts(folders):
    faces = []
    seen = set()
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith(".") and not d.endswith(".app")]
            for fn in files:
                if not fn.lower().endswith(FONT_EXT):
                    continue
                p = os.path.join(root, fn)
                if os.path.realpath(p) in seen:
                    continue
                seen.add(os.path.realpath(p))
                try:
                    for names in name_tables(p):
                        fam = (names.get(16) or names.get(1) or {""})
                        sty = (names.get(17) or names.get(2) or {""})
                        # (family, style) pairs from the same record: typographic (16/17) and legacy (1/2).
                        # Matching on pairs keeps "Noto Sans CJK KR Black / Regular" (legacy) from passing
                        # for "Noto Sans CJK KR / Regular".
                        pairs = {(norm(f), norm(s)) for f in names.get(16, set()) for s in names.get(17, set())}
                        pairs |= {(norm(f), norm(s)) for f in names.get(1, set()) for s in names.get(2, set())}
                        if names.get(16) and not names.get(17):
                            pairs |= {(norm(f), norm(s)) for f in names[16] for s in names.get(2, set())}
                        faces.append({"file": p, "families": {norm(x) for x in names.get(1, set()) | names.get(16, set())},
                                      "styles": {norm(x) for x in names.get(2, set()) | names.get(17, set())},
                                      "pairs": pairs,
                                      "ps": {norm(x) for x in names.get(6, set())},
                                      "full": {norm(x) for x in names.get(4, set())},
                                      "family": sorted(fam)[0], "style": sorted(sty)[0]})
                except Exception:
                    continue
    return faces


def matches(face, want):
    if want.get("ps"):
        p = norm(want["ps"])
        return p in face["ps"] or p in face["full"] or any(f + s == p for f in face["families"] for s in face["styles"])
    fam, sty = norm(want["family"]), norm(want.get("style"))
    if not sty:
        return any(f == fam for f, _ in face["pairs"])
    return (fam, sty) in face["pairs"] or any(fam + sty == x for x in face["ps"] | face["full"])


def pdf_fonts(path):
    data = open(path, "rb").read()
    names = set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+._-]+)", data))
    out = set()
    for n in names:
        n = re.sub(r"^[A-Z]{6}\+", "", n.decode("latin-1"))
        n = re.sub(r"-Identity-[HV]$", "", n)
        out.add(n)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job", required=True)
    ap.add_argument("--from-pdf")
    ap.add_argument("--from-doc", action="store_true")
    ap.add_argument("--want", action="append", default=[])
    ap.add_argument("--search", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    fonts_dir = os.path.join(os.path.abspath(a.job), "02_fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    wants = []
    if a.from_pdf:
        wants += [{"ps": n, "source": "pdf"} for n in pdf_fonts(a.from_pdf)]
    if a.from_doc:
        for f in cmd("text.missingFonts", {}).get("fonts", []):
            wants.append({"family": f["family"], "style": f.get("style"), "source": "document"})
    for w in a.want:
        fam, _, sty = w.partition(":")
        wants.append({"family": fam.strip(), "style": sty.strip() or None, "source": "revision"})

    available = None
    try:
        available = {norm(f) for f in cmd("text.fontList", {})["families"]}
    except VCError:
        pass

    search = [fonts_dir] + [os.path.abspath(os.path.expanduser(d)) for d in a.search] + \
             [os.path.expanduser("~/Library/Fonts"), "/Library/Fonts"]
    faces = index_fonts(search)
    report, to_register = [], {}
    for w in wants:
        hits = [f for f in faces if matches(f, w)]
        row = dict(w)
        if not hits:
            row["status"] = "not found"
        else:
            best = sorted(hits, key=lambda f: (not f["file"].startswith(fonts_dir), f["file"]))[0]
            row.update({"file": best["file"], "family": best["family"], "style": best["style"]})
            system = best["file"].startswith(os.path.expanduser("~/Library/Fonts")) or best["file"].startswith("/Library/Fonts")
            if system:
                row["status"] = "installed on the system"
            else:
                dst = os.path.join(fonts_dir, os.path.basename(best["file"]))
                if not a.dry_run and os.path.abspath(best["file"]) != os.path.abspath(dst):
                    if not os.path.exists(dst):
                        shutil.copy2(best["file"], dst)
                row["jobCopy"] = dst
                row["status"] = "to register"
                to_register[(best["family"], best["style"])] = dst
        report.append(row)

    registered = {}
    if to_register and not a.dry_run:
        fonts_param = [{"family": f, "style": s} for (f, s) in to_register]
        cmd("text.findFontFiles", {"folder": fonts_dir, "fonts": fonts_param})
        for _ in range(120):
            st = cmd("text.findFontFiles", {})
            if st.get("state") == "done":
                break
            time.sleep(0.5)
        files = sorted({p for f in st.get("fonts", []) for p in f.get("files", [])})
        if files:
            registered = cmd("text.addFontFiles", {"files": files})
        for row in report:
            if row.get("status") == "to register":
                fam_ok = available is None or norm(row["family"]) in available
                row["status"] = "registered" if row.get("jobCopy") in files else ("already available" if fam_ok else "not registered")
    out = {"fontsDir": fonts_dir, "fonts": report,
           "registered": {k: registered.get(k) for k in ("copied", "kept", "skipped")} if registered else None}
    try:
        out["documentMissingFonts"] = cmd("text.missingFonts", {}).get("fonts")
    except VCError:
        pass
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
