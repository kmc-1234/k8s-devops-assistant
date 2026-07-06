from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .models import Diagnosis


def maybe_add_ai_summary(diagnosis: Diagnosis) -> Diagnosis:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return diagnosis

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = _build_prompt(diagnosis)
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are an internal Kubernetes SRE assistant. "
                    "Summarize findings, likely root cause, risk, and next safe kubectl commands. "
                    "Do not suggest destructive commands unless you clearly label them as manual actions requiring approval."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        diagnosis.ai_summary = f"AI summary unavailable: {exc}"
        return diagnosis

    diagnosis.ai_summary = _extract_text(body) or "AI summary unavailable: empty response"
    return diagnosis


def _build_prompt(diagnosis: Diagnosis) -> str:
    compact = diagnosis.as_dict()
    return json.dumps(compact, indent=2)


def _extract_text(response: dict) -> str | None:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]

    parts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip() or None

