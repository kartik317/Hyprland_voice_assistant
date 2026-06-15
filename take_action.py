#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from transcription import notify


def run(*args) -> str:
    result = subprocess.run(list(args), capture_output=True, text=True, env=os.environ)
    return result.stdout.strip()


def dispatch(lua_expr: str) -> bool:
    """Run hyprctl dispatch with a Lua dispatcher expression."""
    cmd = ["hyprctl", "dispatch", lua_expr]
    print(f"  → {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ)

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if stdout:
        print(f"  stdout: {stdout}")
    if stderr:
        print(f"  stderr: {stderr}", file=sys.stderr)

    success = result.returncode == 0 and "ok" in stdout.lower()
    print(f"  {'✓ ok' if success else '✗ failed'}")
    return success


def get_free_workspace() -> int:
    """Return the lowest workspace ID (1-10) with no open windows."""
    raw = run("hyprctl", "workspaces", "-j")
    workspaces = json.loads(raw) if raw else []
    occupied = {ws["id"] for ws in workspaces if ws.get("windows", 0) > 0}
    for i in range(1, 11):
        if i not in occupied:
            return i
    return max(occupied, default=0) + 1


def handle(data: dict):
    action = data.get("action")
    app = data.get("app")
    workspace = data.get("workspace")

    if action == "open_app":
        if not app:
            print("Error: 'app' field is required", file=sys.stderr)
            sys.exit(1)

        if workspace is None:
            workspace = get_free_workspace()
            print(f"No workspace specified — using free workspace {workspace}")

        # New Hyprland 0.55+ Lua dispatcher syntax
        print(f"Switching to workspace {workspace}...")
        dispatch(f'hl.dsp.focus({{ workspace = "{workspace}" }})')

        time.sleep(0.1)

        print(f"Launching '{app}'...")
        dispatch(f'hl.dsp.exec_cmd("{app}")')

    else:
        print(f"Unknown action: {action!r}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.exists(arg):
            with open(arg) as f:
                raw = f.read()
        else:
            raw = arg  # treat as raw JSON string
    else:
        raw = sys.stdin.read()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        notify(f"Invalid JSON: {e}")
        sys.exit(1)

    handle(payload)
