#!/bin/bash
qs ipc call nova setSpeaking true
source ~/.config/hypr/assistant/.venv/bin/activate 
python3 ~/.config/hypr/assistant/transcribe_talk.py start
