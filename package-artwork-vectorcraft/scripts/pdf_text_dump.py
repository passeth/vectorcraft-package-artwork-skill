#!/usr/bin/env python3
"""List the text a PDF-compatible .ai / PDF page draws, with the exact settings the designer used.

    pdf_text_dump.py <file.ai|file.pdf> [--page 1] [--json]

For every text show: font (BaseFont), point size, tracking (Tc as 1/1000 em, what Illustrator calls
tracking), horizontal scale, the baseline position (PDF points, y up AND y down from the top as VectorCraft
reports it), and the text (decoded through ToUnicode when the font has one, else hex glyph ids).
Use it to read the original's real values before changing a font or matching a style: VectorCraft's
PDF-part import can only estimate tracking. stdlib only; classic (non object-stream) PDFs such as
Illustrator writes them.
"""
import json
import re
import sys
import zlib

OBJ_RE = re.compile(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)


def load_objects(data):
    objs = {}
    for m in OBJ_RE.finditer(data):
        num = int(m.group(1))
        body = m.group(3)
        s = re.search(rb"\bstream\r?\n", body)
        if s:
            objs[num] = {"dict": body[:s.start()], "raw": body[s.end():]}
        else:
            objs[num] = {"dict": body, "raw": None}
    return objs


def ref(d, key):
    m = re.search(rb"/" + key + rb"\s*(\d+)\s+\d+\s+R", d)
    return int(m.group(1)) if m else None


def stream(objs, num):
    o = objs[num]
    d, raw = o["dict"], o["raw"]
    if raw is None:
        return b""
    m = re.search(rb"/Length\s+(\d+)(\s+\d+\s+R)?", d)
    if m and m.group(2):
        length = int(re.search(rb"\d+", objs[int(m.group(1))]["dict"]).group(0))
    elif m:
        length = int(m.group(1))
    else:
        length = len(raw)
    raw = raw[:length]
    if b"/FlateDecode" in d:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompressobj().decompress(raw)
    return raw


def sub_dict(objs, d, key):
    """Return the bytes of dictionary `key` inside d, following an indirect reference."""
    r = ref(d, key)
    if r is not None and re.search(rb"/" + key + rb"\s*\d+\s+\d+\s+R", d):
        return objs[r]["dict"]
    i = d.find(b"/" + key)
    if i < 0:
        return b""
    j = d.find(b"<<", i)
    depth, k = 0, j
    while k < len(d):
        if d[k:k + 2] == b"<<":
            depth += 1
            k += 2
        elif d[k:k + 2] == b">>":
            depth -= 1
            k += 2
            if depth == 0:
                return d[j:k]
        else:
            k += 1
    return d[j:]


def parse_cmap(text):
    m = {}
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", text, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            m[a.upper()] = bytes.fromhex(b.decode()).decode("utf-16-be", "replace")
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", text, re.S):
        for a, b, c in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            lo, hi, start = int(a, 16), int(b, 16), int(c, 16)
            width = len(a)
            for i in range(hi - lo + 1):
                m[("%0*X" % (width, lo + i)).encode()] = chr(start + i)
    return m


TOKEN = re.compile(rb"\s*(%[^\r\n]*|\((?:\\.|[^\\()]|\((?:\\.|[^\\()])*\))*\)|<[0-9A-Fa-f\s]*>|\[|\]|<<|>>"
                   rb"|/[^\s/\[\]()<>{}%]*|[-+]?(?:\d+\.?\d*|\.\d+)|[A-Za-z'\"*]+[0-9]?)", re.S)


def unescape_lit(b):
    b = b[1:-1]
    out, i = bytearray(), 0
    esc = {b"n": 10, b"r": 13, b"t": 9, b"b": 8, b"f": 12, b"(": 40, b")": 41, b"\\": 92}
    while i < len(b):
        c = b[i:i + 1]
        if c == b"\\" and i + 1 < len(b):
            n = b[i + 1:i + 2]
            if n in esc:
                out.append(esc[n])
                i += 2
                continue
            o = re.match(rb"[0-7]{1,3}", b[i + 1:])
            if o:
                out.append(int(o.group(0), 8) & 255)
                i += 1 + len(o.group(0))
                continue
            i += 1
            continue
        out += c
        i += 1
    return bytes(out)


def decode(strbytes, font):
    cmap, two = font.get("cmap"), font.get("twoByte")
    if two:
        hexs = [strbytes[i:i + 2].hex().upper().encode() for i in range(0, len(strbytes) - 1, 2)]
    else:
        hexs = ["%02X".encode() % c for c in strbytes]
    if cmap:
        return "".join(cmap.get(h, "?") for h in hexs)
    if not two:
        return strbytes.decode("latin-1")
    return "<" + " ".join(h.decode() for h in hexs) + ">"


def run(path, page_no=1):
    data = open(path, "rb").read()
    objs = load_objects(data)
    pages = [n for n, o in sorted(objs.items()) if re.search(rb"/Type\s*/Page\b(?!s)", o["dict"])]
    if not pages:
        raise SystemExit("no page objects found (object streams are not supported)")
    page = objs[pages[page_no - 1]]["dict"]
    mb = re.search(rb"/MediaBox\s*\[\s*([-\d.\s]+)\]", page)
    height = float(mb.group(1).split()[3]) if mb else 0.0
    res = sub_dict(objs, page, b"Resources")
    fonts_d = sub_dict(objs, res, b"Font")
    fonts = {}
    for name, num in re.findall(rb"/([^\s/<>\[\]]+)\s+(\d+)\s+\d+\s+R", fonts_d):
        fd = objs[int(num)]["dict"]
        bf = re.search(rb"/BaseFont\s*/([^\s/<>\[\]]+)", fd)
        tu = ref(fd, b"ToUnicode")
        fonts[name.decode()] = {
            "baseFont": bf.group(1).decode() if bf else "?",
            "twoByte": b"/Type0" in fd or b"Identity-H" in fd,
            "cmap": parse_cmap(stream(objs, tu)) if tu else None,
        }
    contents = [int(x) for x in re.findall(rb"(\d+)\s+\d+\s+R", (re.search(rb"/Contents\s*(\[[^\]]*\]|\d+\s+\d+\s+R)",
                                                                              page).group(1)))]
    content = b"\n".join(stream(objs, n) for n in contents)

    out, stack = [], []
    st = {"font": None, "size": 1.0, "Tc": 0.0, "Tw": 0.0, "Tz": 100.0, "TL": 0.0}
    tm = lm = [1, 0, 0, 1, 0, 0]
    in_text = False
    for m in TOKEN.finditer(content):
        t = m.group(1)
        if not t or t.startswith(b"%"):
            continue
        if t in (b"[", b"<<"):
            stack.append(t)
            continue
        if t in (b"]", b">>"):
            items = []
            while stack and stack[-1] not in (b"[", b"<<"):
                items.insert(0, stack.pop())
            if stack:
                stack.pop()
            stack.append(("arr", items))
            continue
        if t[:1] in b"(<" or t[:1] == b"/" or re.match(rb"[-+.\d]", t):
            stack.append(t)
            continue
        op, args, stack = t, stack, []
        num = lambda a: float(a)  # noqa: E731
        if op == b"BT":
            in_text, tm, lm = True, [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0]
        elif op == b"ET":
            in_text = False
        elif op == b"Tf" and len(args) >= 2:
            st["font"], st["size"] = args[-2][1:].decode(), num(args[-1])
        elif op in (b"Tc", b"Tw", b"Tz", b"TL") and args:
            st[op.decode()] = num(args[-1])
        elif op == b"Tm" and len(args) >= 6:
            tm = lm = [num(a) for a in args[-6:]]
        elif op in (b"Td", b"TD") and len(args) >= 2:
            tx, ty = num(args[-2]), num(args[-1])
            if op == b"TD":
                st["TL"] = -ty
            lm = [lm[0], lm[1], lm[2], lm[3], lm[4] + tx * lm[0] + ty * lm[2], lm[5] + tx * lm[1] + ty * lm[3]]
            tm = lm
        elif op in (b"T*", b"'", b'"'):
            ty = -st["TL"]
            lm = [lm[0], lm[1], lm[2], lm[3], lm[4] + ty * lm[2], lm[5] + ty * lm[3]]
            tm = lm
        if in_text and op in (b"Tj", b"TJ", b"'", b'"') and args:
            a = args[-1]
            parts = a[1] if isinstance(a, tuple) else [a]
            raw = b""
            for p in parts:
                if isinstance(p, bytes) and p[:1] == b"(":
                    raw += unescape_lit(p)
                elif isinstance(p, bytes) and p[:1] == b"<":
                    raw += bytes.fromhex(re.sub(rb"\s", b"", p[1:-1]).decode() or "")
            f = fonts.get(st["font"], {"baseFont": st["font"], "twoByte": False, "cmap": None})
            scale_y = (tm[2] ** 2 + tm[3] ** 2) ** 0.5
            scale_x = (tm[0] ** 2 + tm[1] ** 2) ** 0.5
            size = st["size"] * scale_y
            out.append({
                "font": re.sub(r"^[A-Z]{6}\+", "", f["baseFont"]),
                "sizePt": round(size, 4),
                "tracking": round(st["Tc"] / st["size"] * 1000, 1) if st["size"] else None,
                "hScalePct": round(scale_x / scale_y * st["Tz"], 2) if scale_y else None,
                "x": round(tm[4], 3), "yPdf": round(tm[5], 3), "yTop": round(height - tm[5], 3),
                "text": decode(raw, f),
            })
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    page = int(sys.argv[sys.argv.index("--page") + 1]) if "--page" in sys.argv else 1
    rows = run(args[0], page)
    if "--json" in sys.argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"{r['font']:<32} {r['sizePt']:>8}pt  track {r['tracking']!s:>6}  h {r['hScalePct']!s:>6}%  "
                  f"x {r['x']:>8} yTop {r['yTop']:>8}  {r['text']}")
