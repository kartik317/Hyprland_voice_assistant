from pathlib import Path
import ollama
import subprocess
import json
import re
import queue
import threading

task = Path("~/.config/hypr/assistant/task.txt").expanduser().read_text()
error_logs = Path("~/.config/hypr/assistant/error.log").expanduser().read_text()

PIPER_MODEL = Path("~/piper-models/en_US-amy-medium.onnx").expanduser()


def get_system_prompt():
    action_path = Path("~/.config/hypr/assistant/action.json").expanduser().read_text()
    action = json.loads(action_path)
    if action.get("action") == "talk":
        talk_prompt = (
            Path("~/.config/hypr/assistant/prompts/talk_prompt.txt")
            .expanduser()
            .read_text()
        )
        return f"{talk_prompt}\n\nHere is what user says: {task}"
    else:
        return f"""You are Nova, a playful Linux assistant.
if you see an ERROR in here, the task has failed. Briefly explain why from the error logs max two sentences.
{error_logs}
if there is no ERROR, the task has succeeded. Confirm the task is done, sound happy and confident.
Here is the task: '{task}'
if there is no task, say "No task provided".
Do not mention JSON. Do not repeat yourself"""

#print(get_system_prompt())

# strip markdown-y symbols gemma3 likes to sneak in, before TTS ever sees them
_SANITIZE_RE = re.compile(r"[*_`#]")


def sanitize(text: str) -> str:
    return _SANITIZE_RE.sub("", text).strip()


# split buffered text into complete sentences, keep any trailing partial sentence
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def speak_sentence(sentence: str):
    sentence = sanitize(sentence)
    if not sentence:
        return
    piper = subprocess.Popen(
        ["piper-tts", "--model", str(PIPER_MODEL), "--output_file", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    aplay = subprocess.Popen(["aplay", "-q"], stdin=piper.stdout)
    piper.stdin.write(sentence.encode())
    piper.stdin.close()
    piper.wait()
    aplay.wait()


def tts_worker(sentence_q: "queue.Queue[str | None]"):
    while True:
        sentence = sentence_q.get()
        if sentence is None:
            sentence_q.task_done()
            break
        speak_sentence(sentence)
        sentence_q.task_done()


def stream_and_speak(prompt: str) -> str:
    sentence_q: "queue.Queue[str | None]" = queue.Queue()
    worker = threading.Thread(target=tts_worker, args=(sentence_q,), daemon=True)
    worker.start()

    buffer = ""
    full_response = []

    try:
        for chunk in ollama.generate(model="gemma3:4b", prompt=prompt, stream=True):
            piece = chunk.get("response", "")
            if not piece:
                continue
            full_response.append(piece)
            buffer += piece

            parts = _SENTENCE_SPLIT_RE.split(buffer)
            if len(parts) > 1:
                *complete_sentences, buffer = parts
                for sentence in complete_sentences:
                    sentence_q.put(sentence)
    finally:
        if buffer.strip():
            sentence_q.put(buffer)
        sentence_q.put(None)
        sentence_q.join()
        worker.join()

    return "".join(full_response)

if __name__ == "__main__":
    response_text = stream_and_speak(get_system_prompt())
    #print(response_text)
