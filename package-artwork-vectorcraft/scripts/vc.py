#!/usr/bin/env python3
"""VectorCraft control-channel client (stdlib only).

The desktop app must run with `--control <port>` (see vc_launch.py). Protocol: one JSON object per line,
{"id", "method", "params"} -> {"id", "ok", "result"|"error"}. Engine commands go through
`engine.execute {command, params}`; `engine.commands` lists them with their parameter docs.

Library use:
    from vc import call, cmd
    cmd("document.open", {"path": "/abs/file.ai"})

CLI use:
    vc.py call ui.inspect
    vc.py cmd document.find '{"kind": "Type"}'
    vc.py cmd document.inspect '{}' --out /tmp/inspect.json
    vc.py help text.setStyle          # parameter doc of one engine command
"""
import json
import os
import socket
import sys

PORT = int(os.environ.get("VC_PORT", "7979"))
HOST = "127.0.0.1"
_next_id = [0]


class VCError(RuntimeError):
    pass


def call(method, params=None, timeout=180):
    """Send one request and return the parsed reply dict (never raises on ok=false)."""
    _next_id[0] += 1
    req = {"id": _next_id[0], "method": method}
    if params is not None:
        req["params"] = params
    try:
        s = socket.create_connection((HOST, PORT), timeout=timeout)
    except OSError as e:
        raise VCError(f"cannot connect to VectorCraft on {HOST}:{PORT} ({e}); start it with vc_launch.py --start")
    try:
        s.sendall((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    finally:
        s.close()
    return json.loads(buf.decode("utf-8"))


def cmd(command, params=None, timeout=180, check=True):
    """Run an engine command; return its result, or raise VCError when check and ok=false."""
    r = call("engine.execute", {"command": command, "params": params or {}}, timeout)
    if check and not r.get("ok"):
        raise VCError(f"{command}: {r.get('error')}")
    return r.get("result") if check else r


def command_doc(command):
    for c in call("engine.commands")["result"]:
        if c["id"] == command:
            return c
    return None


def _emit(obj, out):
    text = json.dumps(obj, ensure_ascii=False, indent=None if out else 1)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"{len(text)} bytes -> {out} ok={obj.get('ok', True) if isinstance(obj, dict) else True}")
    else:
        print(text)


def main(argv):
    if len(argv) < 2 or argv[0] not in ("call", "cmd", "help"):
        print(__doc__)
        return 2
    out = None
    if "--out" in argv:
        i = argv.index("--out")
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    kind, name = argv[0], argv[1]
    params = json.loads(argv[2]) if len(argv) > 2 else None
    try:
        if kind == "call":
            r = call(name, params)
        elif kind == "cmd":
            r = call("engine.execute", {"command": name, "params": params or {}})
        else:
            r = command_doc(name) or {"ok": False, "error": f"no command {name}"}
    except VCError as e:
        print(str(e), file=sys.stderr)
        return 1
    _emit(r, out)
    return 0 if (not isinstance(r, dict) or r.get("ok", True)) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
