from pathlib import Path
import ollama
import json
import re

system_prompt = (
    Path("~/.config/hypr/assistant/prompts/system_prompt.txt").expanduser().read_text()
)
user_prompt = Path("~/.config/hypr/assistant/task.txt").expanduser().read_text()
prompt = f"""
{system_prompt}
User command:
{user_prompt}
"""
response = ollama.generate(
    model="gemma3:1b",
    prompt=prompt,
    format={
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "app": {"type": ["string", "null"]},
            "workspace": {"type": ["integer", "null"]},
            "from": {"type": ["integer", "null"]},
            "to": {"type": ["integer", "null"]}
        }
    },
    options={
        "num_predict": 64,   # your JSON object is tiny, cap generation
        "num_ctx": 512,      # your prompt+examples are well under this; smaller ctx = faster prefill/less KV-cache alloc
        "temperature": 0,    # deterministic, marginally faster sampling
    }
)

action = json.loads(response.response)

with open(Path("~/.config/hypr/assistant/action.json").expanduser(), "w") as f:
    json.dump(action, f, indent=4)
#print(response.response)
#print(user_prompt)