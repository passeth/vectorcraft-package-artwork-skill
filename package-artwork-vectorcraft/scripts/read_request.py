#!/usr/bin/env python3
"""Read a '부자재 문안수정 요청서' .xlsx (stdlib only) and print its fields and revision items as JSON.

    read_request.py <요청서.xlsx>

Labels are matched with their spaces removed (요 청 일 -> 요청일); a label's value is the next filled cell to
its right on the same row. Revision items are the filled rows under the header row that holds '수정사항',
up to the '비고' row. Excel date serials become YYYY-MM-DD.
"""
import datetime
import html
import json
import re
import sys
import zipfile

LABELS = {
    "요청서번호": "no", "작성자": "author", "작성일": "written", "요청일": "requested",
    "제품명": "productName", "제품코드": "productCode", "적용대상부자재": "component",
    "담당디자이너": "designer", "완료여부": "done", "완료일": "doneDate",
}
DATE_KEYS = {"written", "requested", "doneDate"}


def col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def read_cells(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        xml = z.read("xl/sharedStrings.xml").decode("utf-8")
        for si in re.findall(r"<si>(.*?)</si>", xml, re.S):
            shared.append(html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
    sheet = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))[0]
    xml = z.read(sheet).decode("utf-8")
    cells = {}
    for m in re.finditer(r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', xml, re.S):
        col, row, attrs, inner = m.groups()
        if not inner:
            continue
        v = re.search(r"<v>(.*?)</v>", inner, re.S)
        if 't="s"' in attrs and v:
            val = shared[int(v.group(1))]
        elif 't="inlineStr"' in attrs:
            val = html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", inner, re.S)))
        elif v:
            val = html.unescape(v.group(1))
        else:
            continue
        val = val.strip()
        if val:
            cells.setdefault(int(row), {})[col_index(col + row)] = val
    return cells


def excel_date(v):
    try:
        n = float(v)
    except ValueError:
        return v
    if 20000 < n < 80000:
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(n))).isoformat()
    return v


def parse(path):
    cells = read_cells(path)
    out = {"title": None, "items": []}
    header_row = remarks_row = None
    for r in sorted(cells):
        row = cells[r]
        for c in sorted(row):
            key = re.sub(r"\s+", "", row[c])
            if out["title"] is None and "요청서" in key and len(key) <= 20 and key not in LABELS:
                out["title"] = row[c]
            if key in LABELS:
                vals = [row[c2] for c2 in sorted(row) if c2 > c and re.sub(r"\s+", "", row[c2]) not in LABELS]
                val = vals[0] if vals else None
                if val and LABELS[key] in DATE_KEYS:
                    val = excel_date(val)
                if val and re.fullmatch(r"년\s*월\s*일", re.sub(r"\s+", "", val).replace("년월일", "년 월 일")):
                    val = None
                out[LABELS[key]] = val
            if key == "수정사항":
                header_row = r
            if key == "비고" and header_row and remarks_row is None:
                remarks_row = r
    if header_row:
        for r in sorted(cells):
            if r <= header_row or (remarks_row and r >= remarks_row):
                continue
            texts = [v for c, v in sorted(cells[r].items()) if not re.fullmatch(r"\d+", v)]
            if texts:
                out["items"].append(" ".join(texts))
    if remarks_row:
        rest = [v for c, v in sorted(cells[remarks_row].items()) if re.sub(r"\s+", "", v) != "비고"]
        out["remarks"] = " ".join(rest) or None
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    print(json.dumps(parse(sys.argv[1]), ensure_ascii=False, indent=1))
