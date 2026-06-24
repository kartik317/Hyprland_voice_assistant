#!/usr/bin/env python3

import os
import re
import sys
import signal
import subprocess
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

WHISPER_CLI = os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli")
WHISPER_MODEL = os.path.expanduser("~/whisper.cpp/models/ggml-base.en.bin")

AUDIO_FILE = "/tmp/voice_note_input.wav"  # temp recording
PID_FILE = "/tmp/voice_note.pid"  # arecord PID while recording
OUTPUT_FILE = os.path.expanduser("~/.config/hypr/assistant/task.txt")

# Whisper trims these artifact strings from its output
WHISPER_GARBAGE = re.compile(r"\[BLANK_AUDIO\]|\(.*?\)|\[.*?\]", re.IGNORECASE)

# ── Helpers ───────────────────────────────────────────────────────────────────


def notify(title: str, body: str = "", urgency: str = "normal") -> None:
    """Send a desktop notification (requires libnotify)."""
    cmd = ["notify-send", "-u", urgency, "-a", "voice-note", title]
    if body:
        cmd.append(body)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def speak_info(info: str) -> None:
    piper = subprocess.Popen(
        [
            "piper-tts",
            "--model",
            str(Path("~/piper-models/en_US-amy-medium.onnx").expanduser()),
            "--output_file",
            "-",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )


    aplay = subprocess.Popen(["aplay"], stdin=piper.stdout)
    piper.stdin.write(info.encode())
    piper.stdin.close()
    piper.wait()
    aplay.wait()


def die(msg: str) -> None:
    notify("Voice Note ✗", msg, urgency="critical")
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def clean_whisper_output(raw: str) -> str:
    """Strip timestamps and junk tokens from whisper-cli stdout."""
    lines = []
    for line in raw.splitlines():
        # Strip leading timestamp blocks like [00:00:00.000 --> 00:00:05.000]
        line = re.sub(
            r"\[\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]", "", line
        )
        line = WHISPER_GARBAGE.sub("", line).strip()
        if line:
            lines.append(line)
    return " ".join(lines).strip()


# ── Core actions ──────────────────────────────────────────────────────────────


def start_recording() -> None:
    """Start recording audio to a temp file."""

    # clean previous error log
    log_file = os.path.expanduser("~/.config/hypr/assistant/error.log")
    if os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("")  # clear the log file

    if os.path.exists(PID_FILE):
        notify(
            "Voice Note",
            "Already recording — release Super+A first",
            urgency="critical",
        )
        speak_info("Already recording — release Super+A first")
        return

    # Remove stale audio file
    Path(AUDIO_FILE).unlink(missing_ok=True)

    proc = subprocess.Popen(
        [
            "arecord",
            "--quiet",
            "-r",
            "16000",  # 16 kHz — what Whisper expects
            "-c",
            "1",  # mono
            "-f",
            "S16_LE",  # 16-bit PCM little-endian
            "-t",
            "wav",
            AUDIO_FILE,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    Path(PID_FILE).write_text(str(proc.pid))
    #notify("Voice Note ", "Recording… release Super+A to stop")
    speak_info("I'm listening…")


def stop_recording() -> bool:
    if not os.path.exists(PID_FILE):
        # Key released without a matching start — silently ignore
        return False

    # ── 1. Stop arecord ───────────────────────────────────────────────────────
    pid = int(Path(PID_FILE).read_text().strip())
    Path(PID_FILE).unlink(missing_ok=True)

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # already dead — audio file still exists, carry on

    # Give arecord a moment to flush the WAV header properly
    import time

    time.sleep(0.15)

    if not Path(AUDIO_FILE).exists():
        die("Audio file not found — recording may have failed")

    # ── 2. Run whisper-cli ────────────────────────────────────────────────────
    #notify("Voice Note", "Transcribing…")
    speak_info("Transcribing…")

    if not Path(WHISPER_CLI).exists():
        die(f"whisper-cli not found at:\n{WHISPER_CLI}")
    if not Path(WHISPER_MODEL).exists():
        die(f"Model not found at:\n{WHISPER_MODEL}")

    result = subprocess.run(
        [
            WHISPER_CLI,
            "-m",
            WHISPER_MODEL,
            "-f",
            AUDIO_FILE,
            "-nt",  # no timestamps in output
            "--no-prints",
        ],
        capture_output=True,
        text=True,
    )

    # ── 3. Parse & save ───────────────────────────────────────────────────────
    raw = result.stdout
    text = clean_whisper_output(raw)

    if not text:
        #notify("Voice Note", "Nothing detected — try again", urgency="critical")
        speak_info("Nothing detected — I'm sorry, I didn't catch that. Please try again.")
        return False # return false so if there is no text, the action is not taken

    # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"{text}\n"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(entry)

    # Show the first ~70 chars in the notification
    preview = text if len(text) <= 70 else text[:67] + "…"
    #notify("Voice Note ✓", f'"{preview}"\n→ saved to task.txt')

    # Clean up temp audio
    Path(AUDIO_FILE).unlink(missing_ok=True)
    return True  # return true so if there is text, the action is taken


# ── Entrypoint ────────────────────────────────────────────────────────────────

USAGE = "[start | stop]"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(USAGE)
        sys.exit(1)

    match sys.argv[1]:
        case "start":
            start_recording()
        case "stop":
            is_success = stop_recording()
            if not is_success:
                subprocess.run(["qs", "ipc", "call", "nova", "setSpeaking", "false"])
                sys.exit(1)
            subprocess.run(
                [
                    "python3",
                    os.path.expanduser("~/.config/hypr/assistant/generate_json.py"),
                ]
            )
            subprocess.run(
                [
                    "python3",
                    os.path.expanduser("~/.config/hypr/assistant/take_action.py"),
                    os.path.expanduser("~/.config/hypr/assistant/action.json"),
                ]
            )
        case _:
            print(USAGE)
            sys.exit(1)
