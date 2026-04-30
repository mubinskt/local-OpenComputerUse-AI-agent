# Local Desktop Automation Agent

A minimal standalone Python app for single-user desktop automation.
It captures the screen, sends the instruction to a local Ollama model, receives a JSON action plan, and executes clicks/typing/drag/scroll locally.

## What this repo contains

- `main.py` — Tkinter GUI app
- `requirements.txt` — Python dependencies
- `README.md` — quickstart and usage
- `.gitignore`

## Recommended Ollama model

Use a local instruction model that is fast enough for your machine.

- Recommended: `llama2-13b`
- If you have a beefy machine: `llama2-70b`
- If you need a smaller footprint: `mistral-7b`

Install in Ollama with:

```bash
ollama pull llama2-13b
```

If you want true screenshot vision support later, choose an Ollama vision-capable model when available.

You can list available local Ollama models with:

```bash
ollama list
```

If the app reports a missing model, use one of the installed model names or pull a new one.

## Setup

```bash
cd local-desktop-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Set the Ollama model and API URL if needed:

```bash
set OLLAMA_MODEL=llama2-13b
set OLLAMA_URL=http://127.0.0.1:11434
python main.py
```

## How it works

1. Enter a natural language instruction.
2. Capture a screenshot of your desktop.
3. The app sends the instruction plus screenshot metadata to Ollama.
4. Ollama returns a JSON action plan.
5. Review the JSON and confirm before execution.

## Supported actions

- `click`
- `double_click`
- `type`
- `key_combo`
- `key_press`
- `scroll`
- `drag`
- `wait`

## JSON format

The model should return a JSON object like:

```json
{
  "actions": [
    { "action": "click", "x": 400, "y": 300, "button": "left" },
    { "action": "type", "text": "hello world" },
    { "action": "key_combo", "keys": ["ctrl", "s"] }
  ]
}
```

A copy of the last generated action plan is saved to `last_actions.json`.

## Notes

- This is a local-only app and does not depend on any backend service.
- The prompt currently sends screenshot metadata and path; if you want full image understanding, use a vision-capable model in Ollama.
- Confirm the action plan before execution to avoid unintended clicks.
