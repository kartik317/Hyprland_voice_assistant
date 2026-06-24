#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from transcription import notify
from difflib import get_close_matches

DISPATCH_TIMEOUT = 5  # seconds — prevents silent infinite hangs


def speak():
    subprocess.run(
        ["python3", os.path.expanduser("~/.config/hypr/assistant/speak.py")]
    )


def run(*args, timeout=DISPATCH_TIMEOUT) -> str:
    try:
        result = subprocess.run(
            list(args), capture_output=True, text=True, env=os.environ, timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        save_error_log(f"Timed out running: {' '.join(args)}")
        print(f"  ✗ timed out: {' '.join(args)}", file=sys.stderr)
        return ""


def save_error_log(message: str):
    """Save an error message to a log file."""
    log_file = os.path.expanduser("~/.config/hypr/assistant/error.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a") as f:
        f.write(f"{message}\n")


def dispatch(lua_expr: str, timeout=DISPATCH_TIMEOUT) -> bool:
    """Run hyprctl dispatch with a Lua dispatcher expression."""
    cmd = ["hyprctl", "dispatch", lua_expr]
    print(f"  → {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=os.environ, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        save_error_log(f"Dispatch timed out: {lua_expr}")
        print(f"  ✗ timed out: {lua_expr}", file=sys.stderr)
        return False

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if stdout:
        print(f"  stdout: {stdout}")
    if stderr:
        save_error_log(f"stderr: {stderr}")
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


def get_app_workspace(app: str) -> int | None:
    """Return the workspace ID where the given app is running, or None if not found."""
    raw = run("hyprctl", "clients", "-j")
    clients = json.loads(raw) if raw else []
    app_lower = app.lower()
    for client in clients:
        identifiers = [
            client.get("class", ""),
            client.get("initialClass", ""),
            client.get("title", ""),
            client.get("initialTitle", ""),
        ]
        if any(app_lower in ident.lower() for ident in identifiers):
            return client.get("workspace", {}).get("id")
    return None


def get_workspace_windows(ws_id: int) -> list[str]:
    """Return window addresses currently on the given workspace."""
    raw = run("hyprctl", "clients", "-j")
    clients = json.loads(raw) if raw else []
    return [
        client.get("address")
        for client in clients
        if client.get("workspace", {}).get("id") == ws_id and client.get("address")
    ]


def get_proper_app_name(app: str) -> str:
    """Return the proper app name from apps.json, or the original app name if not found."""
    apps_file = os.path.expanduser("~/.config/hypr/assistant/apps.json")
    try:
        with open(apps_file) as f:
            apps_mapping = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        save_error_log(f"Could not load apps mapping from {apps_file}")
        print(f"Warning: Could not load apps mapping from {apps_file}", file=sys.stderr)
        return app

    matches = get_close_matches(app.lower(), apps_mapping.keys(), n=1, cutoff=0.6)
    if matches:
        return apps_mapping[matches[0]]
    return apps_mapping.get(app.lower(), app)


def handle(data: dict):
    """Wraps the real handler so speak() always fires exactly once, on any path."""
    try:
        _handle(data)
    finally:
        speak()


def _handle(data: dict):
    action = data.get("action")
    app = data.get("app")
    workspace = data.get("workspace")

    if action == "open_app":
        if not app:
            save_error_log("Error: 'app' field is required for open_app")
            print("Error: 'app' field is required", file=sys.stderr)
            sys.exit(1)
        if workspace is None:
            workspace = get_free_workspace()
            print(f"No workspace specified — using free workspace {workspace}")
        print(f"Switching to workspace {workspace}...")
        dispatch(f'hl.dsp.focus({{ workspace = "{workspace}" }})')
        time.sleep(0.1)
        app = get_proper_app_name(app)
        print(f"Launching '{app}'...")
        dispatch(f'hl.dsp.exec_cmd("{app}")')

    elif action == "switch_workspace":
        if workspace is None:
            save_error_log("Error: 'workspace' field is required for switch_workspace")
            print("Error: 'workspace' field is required for switch_workspace", file=sys.stderr)
            sys.exit(1)
        print(f"Switching to workspace {workspace}...")
        dispatch(f'hl.dsp.focus({{ workspace = "{workspace}" }})')

    elif action == "find_app":
        if not app:
            save_error_log("Error: 'app' field is required for find_app")
            print("Error: 'app' field is required for find_app", file=sys.stderr)
            sys.exit(1)
        app = get_proper_app_name(app)
        print(f"Searching for '{app}'...")
        ws_id = get_app_workspace(app)
        if ws_id is None:
            raw_app = data.get("app", "")
            ws_id = get_app_workspace(raw_app)
        if ws_id is None:
            print(f"'{app}' is not currently open.", file=sys.stderr)
            save_error_log(f"App '{app}' not found")
            notify(f"App '{app}' not found")
            sys.exit(1)
        print(f"Found '{app}' on workspace {ws_id}, switching...")
        dispatch(f'hl.dsp.focus({{ workspace = "{ws_id}" }})')

    elif action == "move_window":
        from_ws = data.get("from")
        to_ws = data.get("to")
        if from_ws is None or to_ws is None:
            save_error_log("Error: 'from' and 'to' fields are required for move_window")
            print("Error: 'from' and 'to' fields are required for move_window", file=sys.stderr)
            sys.exit(1)

        addresses = get_workspace_windows(from_ws)
        if not addresses:
            print(f"No windows found on workspace {from_ws}.", file=sys.stderr)
            save_error_log(f"No windows found on workspace {from_ws}")
            notify(f"No windows on workspace {from_ws}")
            sys.exit(1)

        print(f"Moving {len(addresses)} window(s) from workspace {from_ws} to {to_ws}...")
        for addr in addresses:
            dispatch(f'hl.dsp.window.move({{ workspace = "{to_ws}", window = "address:{addr}" }})')
    elif action == "talk":
        return  # No action needed; speak() will handle the talking

    else:
        save_error_log(f"Unknown action: {action!r}")
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
        save_error_log(f"Invalid JSON: {e}")
        print(f"Invalid JSON: {e}", file=sys.stderr)
        notify(f"Invalid JSON: {e}")
        sys.exit(1)

    handle(payload)
    subprocess.run(["qs", "ipc", "call", "nova", "setSpeaking", "false"])