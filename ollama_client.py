import json
import requests
from typing import Any, Dict, List

from config import OLLAMA_MODEL, OLLAMA_URL, SCREENSHOT_FILE


def get_available_ollama_models() -> List[str]:
    endpoints = ["/api/tags", "/v1/models"]
    for endpoint in endpoints:
        try:
            response = requests.get(f"{OLLAMA_URL}{endpoint}", timeout=10)
            if response.status_code != 200:
                continue
            data = response.json()
        except requests.RequestException:
            continue

        if isinstance(data, dict):
            if "models" in data and isinstance(data["models"], list):
                return [str(item.get("name")) for item in data["models"] if isinstance(item, dict) and item.get("name")]
            if "data" in data and isinstance(data["data"], list):
                return [str(item.get("id")) for item in data["data"] if isinstance(item, dict) and item.get("id")]
    return []


def resolve_ollama_model() -> str:
    if not OLLAMA_MODEL:
        available = get_available_ollama_models()
        if available:
            return available[0]
        raise RuntimeError(
            "No Ollama model configured and no models were discovered at the Ollama endpoint. "
            f"Check OLLAMA_MODEL and Ollama URL {OLLAMA_URL}."
        )

    available = get_available_ollama_models()
    if available and OLLAMA_MODEL not in available:
        raise RuntimeError(
            f"Model '{OLLAMA_MODEL}' was not found in Ollama. Available models: {', '.join(available)}. "
            "Pull a model with `ollama pull <model>` or set OLLAMA_MODEL to one of the available names."
        )
    return OLLAMA_MODEL


def _parse_response_json(response: requests.Response) -> Dict[str, Any]:
    text = response.text.strip()
    if not text:
        raise RuntimeError(
            f"Ollama returned an empty response body (status={response.status_code}). "
            f"Check that the model and endpoint are correct."
        )
    try:
        return response.json()
    except ValueError:
        raise RuntimeError(
            f"Failed to parse Ollama response as JSON (status={response.status_code}).\n"
            f"Response body:\n{text[:2000]}"
        )


def _ollama_post(url: str, payload: Dict[str, Any]) -> requests.Response:
    try:
        response = requests.post(url, json=payload, timeout=120)
    except requests.RequestException as exc:
        raise RuntimeError(f"Request to Ollama failed: {exc}")
    return response


def _extract_text_from_response(data: Dict[str, Any]) -> str:
    if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
        choice = data["choices"][0]
        if isinstance(choice, dict):
            if "message" in choice and isinstance(choice["message"], dict):
                return str(choice["message"].get("content", "")).strip()
            if "text" in choice:
                return str(choice["text"]).strip()
    if "text" in data:
        return str(data["text"]).strip()
    return ""


def call_ollama(prompt: str) -> str:
    model_name = resolve_ollama_model()
    chat_payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a JSON-only action planner."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }

    # Try chat endpoint first; fall back to prompt-style completion if empty or unsupported.
    chat_url = f"{OLLAMA_URL}/v1/chat/completions"
    response = _ollama_post(chat_url, chat_payload)
    if response.status_code < 400:
        data = _parse_response_json(response)
        text = _extract_text_from_response(data)
        if text:
            return text
        # Some Ollama models respond with an empty chat object; fall back to completions.

    complete_payload = {
        "model": model_name,
        "prompt": prompt,
        "temperature": 0.2,
        "max_tokens": 600,
    }
    complete_url = f"{OLLAMA_URL}/v1/completions"
    response = _ollama_post(complete_url, complete_payload)
    if response.status_code >= 400:
        raise RuntimeError(
            f"Ollama completions endpoint failed: {response.status_code}: {response.text.strip()}"
        )
    data = _parse_response_json(response)
    text = _extract_text_from_response(data)
    if text:
        return text

    raise RuntimeError(
        f"Ollama did not return text. Response: {json.dumps(data, indent=2)[:2000]}"
    )


def build_prompt(script_text: str, width: int, height: int) -> str:
    print(f"Building prompt for {width}x{height} screenshot")
    return (
        "You are a local automation assistant. "
        "The user will provide a scripted set of desktop automation steps. "
        "Return only valid JSON with an ordered list of actions. "
        "Do not include any explanation outside the JSON object.\n"
        "Screenshot metadata:\n"
        f"- path: {SCREENSHOT_FILE}\n"
        f"- resolution: {width}x{height}\n"
        "The screenshot is the current desktop. Use screen coordinates relative to this resolution.\n"
        "Supported actions: click, double_click, type, key_combo, key_press, scroll, drag, wait.\n"
        "Use keys as a JSON list for key actions, for example: {\"keys\": [\"enter\"]} or {\"keys\": [\"ctrl\", \"s\"]}.\n"
        "For wait, use the field \"seconds\" or \"time\" with the duration in seconds.\n"
        "x_coordinate and y_coordinate must be numeric values inferred from the screenshot(and relative to the - resolution: {width}x{height}) for any particular click or move events on the screen.\n"
        "The coordinate system uses bottom-left origin: 0,0, bottom-right {width},0, top-left 0,{height}, and top-right {width},{height}. x increases to the right, y increases upwards. "
        "Output format:\n"
        "{\n  \"actions\": [\n    {\"action\": \"click\", \"x\": x_coordinate, \"y\": y_coordinate, \"button\": \"left\"},\n"
        "    {\"action\": \"type\", \"text\": \"hello world\"}\n"
        "  ]\n}\n"
        "Use the script text below as the instruction guide.\n"
        f"Script:\n{script_text}\n"
    )