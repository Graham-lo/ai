from __future__ import annotations

import json

from openai import OpenAI

from app.core.config import settings
from app.services.deepseek_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


def generate_deepseek_markdown(
    payload: dict,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 3000,
) -> tuple[str, str]:
    resolved_key = (api_key or settings.DEEPSEEK_API_KEY).strip()
    if not resolved_key:
        raise RuntimeError("DEEPSEEK_API_KEY not configured")

    resolved_base_url = base_url or settings.DEEPSEEK_BASE_URL
    resolved_model = model or settings.DEEPSEEK_MODEL

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    prompt = USER_PROMPT_TEMPLATE.format(payload_json_pretty=payload_json)

    client = OpenAI(api_key=resolved_key, base_url=resolved_base_url)
    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    return content.strip(), resolved_model
