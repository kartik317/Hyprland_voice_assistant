from pathlib import Path
import ollama
import subprocess

task = Path("~/.config/hypr/assistant/task.txt").expanduser().read_text()

error_logs = Path("~/.config/hypr/assistant/error.log").expanduser().read_text()

error_section = f"ERROR:\n{error_logs}" if error_logs.strip() else "STATUS: success"

system_prompt = f"""You are Nova, a casual Linux assistant. Be concise — max two sentences.

{error_section}

TASK: {task}

If ERROR is shown above: tell the user the task failed and briefly explain why from the error.
If STATUS is success: confirm the task is done, sound happy and confident.
Do not mention JSON. Do not repeat yourself."""

#print(error_logs)

response = ollama.generate(model="gemma3:1b", prompt=system_prompt)

#print(response["response"])

piper = subprocess.Popen(
    [
        "piper-tts",
        "--model",
        str(Path("~/piper-models/en_US-amy-medium.onnx").expanduser()),
        "--output_file",
        "-"
    ],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)
aplay = subprocess.Popen(
    ["aplay"],
    stdin=piper.stdout
)
piper.stdin.write(response['response'].encode())
piper.stdin.close()
piper.wait()
aplay.wait()