#!/usr/bin/env python3
"""Check or start the VectorCraft desktop app with its control port (macOS).

    vc_launch.py --status
    vc_launch.py --start --root <job folder> [--read-root <dir> ...] [--write-root <dir> ...]

--root gives the job folder as both read and write root, so the control channel can touch nothing else.
The script never quits a running VectorCraft: when the app runs without the control port it exits with
code 3 and the agent must look at the window (open, unsaved documents?) and ask the user before quitting.
App path: $VECTORCRAFT_APP (default /Applications/VectorCraft.app). Port: $VC_PORT (default 7979).
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vc import PORT, VCError, call  # noqa: E402

APP = os.environ.get("VECTORCRAFT_APP", "/Applications/VectorCraft.app")
BIN = os.path.join(APP, "Contents", "MacOS", "VectorCraft")


def running_pids():
    r = subprocess.run(["pgrep", "-f", BIN], capture_output=True, text=True)
    return [int(p) for p in r.stdout.split()]


def control_status():
    try:
        r = call("ui.inspect", timeout=10)
    except VCError:
        return None
    res = r.get("result") or {}
    return {"documents": res.get("documents"), "activeDocument": res.get("activeDocument"),
            "fileDialog": res.get("fileDialog")}


def version():
    try:
        out = subprocess.run([BIN, "--version"], capture_output=True, text=True, timeout=10)
        return (out.stdout or out.stderr).strip()
    except Exception:
        return None


def status():
    return {"app": APP, "installed": os.path.exists(BIN), "version": version() if os.path.exists(BIN) else None,
            "pids": running_pids(), "port": PORT, "control": control_status()}


def start(roots, read_roots, write_roots, log_path):
    st = status()
    if not st["installed"]:
        return 4, {**st, "error": "VectorCraft is not installed at " + APP}
    if st["control"] is not None:
        return 0, {**st, "note": "already running with the control port; roots of the running app stay as they were"}
    if st["pids"]:
        return 3, {**st, "error": "VectorCraft is running without the control port. Check its window for open or "
                                  "unsaved documents, ask the user, quit it, then run --start again."}
    args = [BIN, "--control", str(PORT)]
    for d in roots + read_roots:
        args += ["--automation-read-root", os.path.abspath(d)]
    for d in roots + write_roots:
        args += ["--automation-write-root", os.path.abspath(d)]
    for d in roots + read_roots + write_roots:
        if not os.path.isdir(d):
            return 2, {"error": f"root folder does not exist: {d}"}
    log = open(log_path, "a") if log_path else subprocess.DEVNULL
    subprocess.Popen(args, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(60):
        time.sleep(0.5)
        if control_status() is not None:
            return 0, {**status(), "started": True, "readRoots": roots + read_roots, "writeRoots": roots + write_roots}
    return 1, {**status(), "error": "the app started but the control port did not answer within 30 s"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--start", action="store_true")
    ap.add_argument("--root", action="append", default=[], help="job folder: read and write root")
    ap.add_argument("--read-root", action="append", default=[])
    ap.add_argument("--write-root", action="append", default=[])
    ap.add_argument("--log", help="append the app's stdout/stderr here (default: <first root>/03_work/vectorcraft.log)")
    a = ap.parse_args()
    if a.start:
        log = a.log or (os.path.join(a.root[0], "03_work", "vectorcraft.log")
                        if a.root and os.path.isdir(os.path.join(a.root[0], "03_work")) else None)
        code, res = start(a.root, a.read_root, a.write_root, log)
    else:
        code, res = 0, status()
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
