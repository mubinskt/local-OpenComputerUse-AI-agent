# Local Desktop Automation Agent

A modular Python app for desktop automation using a local Ollama model.
It captures the desktop screenshot, sends a script from `scripts/`, receives a JSON action plan, and can execute local clicks/typing/drag/scroll actions.

## What this repo contains

- `main.py` — application entry point
- `ui.py` — Tkinter user interface and event handling
- `ollama_client.py` — Ollama API prompt building and request handling
- `action_executor.py` — action parsing, validation, and execution logic
- `script_manager.py` — workflow script discovery and loading
- `utils.py` — screenshot capture and plan persistence
- `config.py` — configuration and path constants
- `requirements.txt` — Python dependencies
- `scripts/` — workflow script files for automation
- `last_actions.json` — saved action plan output

## Recommended Ollama model

Use a local instruction model that works well with your machine.

- Recommended: `llama2-13b`
- For large machines: `llama2-70b`
- For smaller footprint: `mistral-7b`

Install a model in Ollama with:

```bash
ollama pull llama2-13b
```

List available local Ollama models:

```bash
ollama list
```

If the app reports a missing model, set `OLLAMA_MODEL` to one of the installed names.

## Setup

```powershell
cd c:\GithubAI\local-OpenComputerUse-AI-agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

Set the Ollama model and API URL if needed, then launch the app:

```powershell
set OLLAMA_MODEL=llava:7b
set OLLAMA_URL=http://127.0.0.1:11434
python main.py
```

If you are using PowerShell and want the settings to persist for the session:

```powershell
$env:OLLAMA_MODEL = "llava:7b" // qwen2.5vl:7b
$env:OLLAMA_URL = "http://127.0.0.1:11434"
python main.py
```

## Script-driven workflow

1. Add a plain text `.txt` script to the `scripts/` folder.
2. Select the script in the app dropdown.
3. The app previews the script content.
4. Click `Capture Screenshot & Generate Plan`.
5. Review the generated JSON action plan.
6. Click `Execute Plan` to run it.

The app now also supports dedicated functional test execution. Select a script and click `Run Functional Test` to execute script-defined steps, capture designated screenshots, and log each step's success or failure.

The app takes and saves screenshots during generation and before each execution step. Screenshot files are stored in `screenshots/`, and metadata is recorded in `screenshot_log.json`.
Functional test step results are logged to `functional_test_log.json` when using `Run Functional Test`.

## Supported actions

- `click`
- `double_click`
- `type`
- `key_combo`
- `key_press`
- `scroll`
- `drag`
- `wait`

## Functional test script directives

The app also understands directive lines in `.txt` scripts:

- `SCREENSHOT: label` — capture a screenshot at this point and record it in `screenshot_log.json`
- `WAIT x` — pause for `x` seconds before continuing

Use these directives when you need the test script to define explicit screenshot points and timing.

## JSON format

The model should return a JSON object like:

```json
{
  "actions": [
    { "action": "click", "x": 400, "y": 300, "button": "left" },
    { "action": "type", "text": "hello world" },
    { "action": "key_press", "keys": ["ctrl", "s"] },
    { "action": "wait", "seconds": 1.5 }
  ]
}
```

For `key_press` or `key_combo`, the model can also provide a string like `"Ctrl+S"`.
The app now normalizes those values into usable key lists.
If your display is not the same resolution as the training/reference system, the executor can scale `x`/`y` coordinates to the current screen size. Set `BASE_SCREEN_WIDTH` and `BASE_SCREEN_HEIGHT` in the environment if you want to use a different reference resolution, and keep `SCALE_COORDINATES=true` to enable coordinate scaling.

You can also use percentage coordinates instead of absolute pixels:

```json
{ "action": "click", "x_percent": 5, "y_percent": 10 }
```

If your reference coordinates come from the bottom edge, use `y_bottom` or `y_bottom_percent`:

```json
{ "action": "click", "x": 100, "y_bottom": 200 }
{ "action": "click", "x_percent": 5, "y_bottom_percent": 10 }
```

If your model outputs Y values that are reversed relative to the screen, the executor now flips top-left coordinates automatically by default. You can control this with `FLIP_Y` in the environment.

You can also express values from the right edge with `x_right` or `x_right_percent`:

```json
{ "action": "click", "x_right": 100, "y_bottom": 200 }
```

And, if you want image-based targeting, use `target_image` with a screenshot of the UI element:

```json
{ "action": "click", "target_image": "images/start_button.png" }
```

Image search requires optional OpenCV support for `pyautogui` image matching.
A copy of the latest generated action plan is saved to `last_actions.json`.

## Notes

- This is a local-only app and does not depend on any backend service.
- The UI now loads scripts from `scripts/` instead of manual text input.
- Confirm the action plan before executing to avoid unintended clicks.
- Use a vision-capable Ollama model if you want better screenshot understanding.
