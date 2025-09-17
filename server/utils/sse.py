from __future__ import annotations

import json
from typing import Dict, Iterable, Iterator


def sse_iter(deltas: Iterable[Dict[str, object]]) -> Iterator[bytes]:
    def send_event(payload: str) -> bytes:
        return f"data: {payload}\n\n".encode("utf-8")

    for delta in deltas:
        if delta.get("type") == "content":
            chunk = {
                "id": "chatcmpl-stream",
                "object": "chat.completion.chunk",
                "choices": [
                    {"index": 0, "delta": {"content": delta.get("text", "")}, "finish_reason": None}
                ],
            }
            yield send_event(json.dumps(chunk))
        elif delta.get("type") == "event" and delta.get("event") == "done":
            yield send_event("[DONE]")
            break
        else:
            continue
