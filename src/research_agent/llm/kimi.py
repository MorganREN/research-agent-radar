from typing import Any

KIMI_BASE_URL = "https://api.moonshot.cn/v1"
KIMI_THINKING_DISABLED = {"type": "disabled"}


def is_kimi_25(model: str, base_url: str | None) -> bool:
    return model.startswith("kimi-k2.5") and bool(base_url and "moonshot.cn" in base_url)


def build_kimi_extra_body(model: str, base_url: str | None) -> dict[str, Any] | None:
    if is_kimi_25(model, base_url):
        return {"thinking": KIMI_THINKING_DISABLED}
    return None


def extract_text_blocks(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        return ""

    parts = []
    for item in value:
        text = ""
        if isinstance(item, dict):
            text = item.get("text") or item.get("content") or ""
        else:
            text = getattr(item, "text", None) or getattr(item, "content", None) or ""
        if text:
            parts.append(str(text).strip())
    return "\n".join([part for part in parts if part]).strip()


def extract_message_content(message: Any) -> str:
    return extract_text_blocks(getattr(message, "content", None))


def extract_message_reasoning(message: Any) -> str:
    return extract_text_blocks(getattr(message, "reasoning_content", None))


def extract_response_content(response: Any, empty_prefix: str = "[empty assistant content]") -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        return f"{empty_prefix} no choices"

    content = extract_message_content(choices[0].message)
    if content:
        return content

    finish_reason = getattr(choices[0], "finish_reason", "unknown")
    return f"{empty_prefix} finish_reason={finish_reason}"
