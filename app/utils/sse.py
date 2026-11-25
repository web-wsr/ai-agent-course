import json
from typing import Any

THINKING_TEXT = "正在理解你的问题..."


def format_sse(
    data: Any,
    event: str | None = None,
    event_id: str | None = None,
    retry: int | None = None,
) -> str:
    lines = []

    if event_id is not None:
        lines.append(f"id: {event_id}")

    if event is not None:
        lines.append(f"event: {event}")

    if retry is not None:
        lines.append(f"retry: {retry}")

    if isinstance(data, str):
        payload = data
    else:
        payload = json.dumps(data, ensure_ascii=False)

    for line in payload.splitlines():
        lines.append(f"data: {line}")

    return "\n".join(lines) + "\n\n"


def format_thinking_event(
    content: str = THINKING_TEXT,
    message_id: str | None = None,
) -> str:
    """流式开始时的思考中提示，前端展示为灰色提示，收到首个 message 后隐藏。"""
    data = {"content": content}

    if message_id is not None:
        data["message_id"] = message_id

    return format_sse(event="thinking", data=data)


def format_done_event(data: dict | None = None) -> str:
    return format_sse(event="done", data=data or {"finish_reason": "stop"})


def format_error_event(
    message: str,
    code: int = 500,
    data: dict | None = None,
) -> str:
    return format_sse(
        event="error",
        data={
            "message": message,
            "code": code,
            "detail": data or {},
        },
    )
