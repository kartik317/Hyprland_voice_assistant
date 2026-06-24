#!/bin/bash
qs ipc call nova setSpeaking true
source ~/.config/hypr/assistant/.venv/bin/activate 
python3 ~/.config/hypr/assistant/transcription.py start