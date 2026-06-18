from pathlib import Path
import ollama
import json
import re

system_prompt = (
    Path("~/.config/hypr/assistant/system_prompt.txt").expanduser().read_text()
)
user_prompt = Path("~/.config/hypr/assistant/task.txt").expanduser().read_text()
prompt = f"""
{system_prompt}
User command:
{user_prompt}
"""
response = ollama.generate(
    model="gemma3:1b",
    prompt=prompt
)

raw = response.response
json_str = re.search(r'\{.*\}', raw, re.DOTALL).group()
action = json.loads(json_str)

with open(Path("~/.config/hypr/assistant/action.json").expanduser(), "w") as f:
    json.dump(action, f, indent=4)
