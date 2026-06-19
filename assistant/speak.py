from pathlib import Path
import ollama
import subprocess

task = Path("~/.config/hypr/assistant/task.txt").expanduser().read_text()

error_logs = Path("~/.config/hypr/assistant/error.log").expanduser().read_text()

system_prompt = f"""You are Nova, a casual Linux assistant. Be concise — max two sentences.

if you see an ERROR in here, the task has failed. Briefly explain why from the error logs.
{error_logs}

if there is no ERROR, the task has succeeded. Confirm the task is done, sound happy and confident.

TASK: {task}

Do not mention JSON. Do not repeat yourself. Do not use emojis."""

#print(error_logs)

response = ollama.generate(model="gemma3:4b", prompt=system_prompt)

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