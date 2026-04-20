from __future__ import annotations

from openai import OpenAI

from .config import get_openai_config


def call_openai(system_prompt: str, user_prompt: str) -> str:
    config = get_openai_config()
    client = OpenAI(api_key=config.api_key)

    request = {
        "model": config.model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if config.reasoning_effort:
        request["reasoning"] = {"effort": config.reasoning_effort}

    response = client.responses.create(**request)
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    data = response.model_dump()
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    if not chunks:
        raise RuntimeError("OpenAI response did not contain output text.")
    return "\n".join(chunks)
