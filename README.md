# Hyprland Voice Assistant

A local, privacy-first voice assistant for Hyprland. Speak a command, and It transcribes it with whisper.cpp, turns it into a structured action with a local LLM (Ollama), executes it against your compositor via `hyprctl`, and replies out loud using Piper TTS.

## How It Works

1. `transcription.py` records audio and transcribes it with whisper.cpp
2. `generate_json.py` sends the transcript to a local Ollama model (gemma3) and returns a structured JSON action
3. `take_action.py` executes the action — launching apps, switching workspaces, moving windows — via `hyprctl`
4. `speak.py` generates a spoken response using Piper TTS, played back with `aplay`

## Features

- Fully local — no cloud APIs, no internet required after setup
- Open apps, switch workspaces, and move windows by voice
- Tunable system prompt (`system_prompt.txt`) for controlling assistant behavior
- App lookup table (`apps.json`) for matching spoken app names to launch commands

## Prerequisites

- Linux with Hyprland
- Python 3.10+
- [Ollama](https://ollama.com)
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp)
- A working microphone and `aplay`/ALSA setup

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/kartik317/Hyprland_voice_assistant
cd Hyprland_voice_assistant/assistant
```

### 2. Set up the Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Install and configure Ollama

```bash
# Arch Linux
sudo pacman -S ollama

# Pull and test the model
ollama pull gemma3:4b
ollama run gemma3:4b
```

### 4. Install whisper.cpp

```bash
# Arch Linux (AUR)
yay -S whisper
```

Download the English model:

```bash
cd whisper.cpp
./models/download-ggml-model.sh base.en
```

Or download it directly from Hugging Face:

```bash
wget -O models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

Test that it works:

```bash
./build/bin/whisper-cli \
  -m models/ggml-base.en.bin \
  -f /path/to/your/audiofile.wav
```

## Usage

Start listening:

```bash
python transcription.py start
```

Give a voice command, for example:

> "Open Firefox"

Stop listening:

```bash
python transcription.py stop
```

## Project Structure

```
├── assistant
│   ├── action.json         # Last generated action (JSON)
│   ├── apps.json            # App name → launch command mapping
│   ├── error.log            # Runtime error log
│   ├── generate_json.py     # LLM step: transcript → structured action
│   ├── speak.py             # TTS playback via Piper + aplay
│   ├── system_prompt.txt    # LLM system prompt
│   ├── take_action.py       # Executes actions via hyprctl
│   ├── task.txt             # Latest transcribed task
│   └── transcription.py     # Entry point: records + transcribes audio
├── README.md
└── requirements.txt
```

## Configuration

- **`apps.json`** — maps spoken app names to launch commands, e.g. `{"firefox": "firefox", "files": "nautilus"}`
- **`system_prompt.txt`** — controls how the LLM interprets commands and formats its JSON output. Tune this if the model returns malformed or inconsistent actions.

## Troubleshooting

- **No audio output** — verify `aplay` works standalone (`aplay test.wav`) and that the Piper voice model is downloaded
- **Malformed JSON / actions not executing** — check `error.log`; small models are sensitive to prompt structure, so review `system_prompt.txt`
- **Window/workspace actions failing** — confirm your Hyprland version's dispatch syntax matches what `take_action.py` expects (Hyprland 0.55+ uses Lua-based dispatchers)

## License

Add a license of your choice — MIT is a common pick for personal projects like this.