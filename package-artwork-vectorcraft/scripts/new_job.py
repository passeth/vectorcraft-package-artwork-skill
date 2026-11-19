#!/usr/bin/env python3
"""Create a job folder (see references/folder-structure.md) and copy the inputs into it.

    new_job.py [--root DIR] [--mode revision|new] [--request 요청서.xlsx] [--source file.ai ...]
               [--ref image.png ...] [--font file.ttf ...] [--item "채팅으로 받은 수정 사항" ...] [--name 폴더이름]

Files are copied, never moved. An existing job folder is reused: files already there are kept, and a new
file of the same name is copied as '<name> (2).<ext>'. Prints the job path and job.json as JSON.
Root: --root, else $ARTWORK_JOBS_ROOT, else ~/project/부자재작업.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_request import parse as parse_request  # noqa: E402

SUBDIRS = ["00_request", "01_source", "02_fonts", "03_work", "04_output"]


def clean(s):
    s = re.sub(r'[\\/:*?"<>|]', "", s or "")
    return re.sub(r"\s+", "", s)


def copy_in(src, folder):
    os.makedirs(folder, exist_ok=True)
    name = os.path.basename(src)
    dst = os.path.join(folder, name)
    if os.path.exists(dst):
        with open(src, "rb") as a, open(dst, "rb") as b:
            if a.read() == b.read():
                return dst
        stem, ext = os.path.splitext(name)
        n = 2
        while os.path.exists(os.path.join(folder, f"{stem} ({n}){ext}")):
            n += 1
        dst = os.path.join(folder, f"{stem} ({n}){ext}")
    shutil.copy2(src, dst)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.environ.get("ARTWORK_JOBS_ROOT", os.path.expanduser("~/project/부자재작업")))
    ap.add_argument("--mode", choices=["revision", "new"], default="revision")
    ap.add_argument("--request")
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--font", action="append", default=[])
    ap.add_argument("--item", action="append", default=[], help="revision item received outside the form")
    ap.add_argument("--name", help="job folder name (default: built from the form)")
    a = ap.parse_args()

    for f in [a.request] + a.source + a.ref + a.font:
        if f and not os.path.isfile(f):
            print(json.dumps({"error": f"not a file: {f}"}, ensure_ascii=False))
            return 2

    req = parse_request(a.request) if a.request else {"items": []}
    if a.name:
        name = clean(a.name)
    else:
        parts = [req.get("no") or datetime.date.today().strftime("%y%m%d"), req.get("productCode"),
                 req.get("productName"), req.get("component")]
        name = "_".join(clean(p) for p in parts if p)
        if a.mode == "new":
            name += "_신규"
        if name.count("_") < 1:
            print(json.dumps({"error": "give --name: the form has no product code/name to build it from"},
                             ensure_ascii=False))
            return 2
    job = os.path.join(os.path.abspath(os.path.expanduser(a.root)), name)
    for d in SUBDIRS:
        os.makedirs(os.path.join(job, d), exist_ok=True)

    copied = {}
    if a.request:
        copied["request"] = copy_in(a.request, os.path.join(job, "00_request"))
    copied["refs"] = [copy_in(f, os.path.join(job, "00_request")) for f in a.ref]
    copied["sources"] = [copy_in(f, os.path.join(job, "01_source")) for f in a.source]
    copied["fonts"] = [copy_in(f, os.path.join(job, "02_fonts")) for f in a.font]

    job_json = os.path.join(job, "03_work", "job.json")
    if os.path.exists(job_json):
        with open(job_json, encoding="utf-8") as f:
            data = json.load(f)
        data["extraItems"] = list(dict.fromkeys(data.get("extraItems", []) + a.item))
    else:
        data = {"schema": 1, "mode": a.mode, "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "request": {k: req.get(k) for k in ("no", "productCode", "productName", "component", "author",
                                                    "written", "requested", "items", "remarks")},
                "extraItems": a.item, "source": None, "importMode": None, "fonts": [], "changes": [],
                "outputs": [], "verification": [], "openQuestions": []}
    if copied["sources"] and not data.get("source"):
        data["source"] = os.path.relpath(copied["sources"][0], job)
    with open(job_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    md = os.path.join(job, "00_request", "request.md")
    if not os.path.exists(md):
        lines = [f"# {req.get('productName') or name} — {req.get('component') or ''}", "",
                 f"- 요청서번호: {req.get('no') or '-'} / 제품코드: {req.get('productCode') or '-'}",
                 f"- 작성자: {req.get('author') or '-'} / 요청일: {req.get('requested') or '-'}", "",
                 "## 수정 사항 (요청서)", ""]
        lines += [f"{i}. {t}" for i, t in enumerate(req.get("items") or [], 1)] or ["(없음)"]
        lines += ["", "## 추가 수정 사항 (요청서 밖에서 받은 것: 출처를 적는다)", ""]
        lines += [f"- {t}" for t in a.item] or ["(없음)"]
        with open(md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    print(json.dumps({"job": job, "copied": copied, "jobJson": data}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
