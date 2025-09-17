from __future__ import annotations

from pathlib import Path

_INTERACTION_SYSTEM_PROMPT: str = ""


def get_interaction_system_prompt() -> str:
    global _INTERACTION_SYSTEM_PROMPT
    if _INTERACTION_SYSTEM_PROMPT:
        return _INTERACTION_SYSTEM_PROMPT
    try:
        here = Path(__file__).parent
        prompt_path = here / "agents" / "interaction_agent" / "system_prompt.md"
        _INTERACTION_SYSTEM_PROMPT = prompt_path.read_text(encoding="utf-8").strip()
    except Exception:
        _INTERACTION_SYSTEM_PROMPT = ""
    return _INTERACTION_SYSTEM_PROMPT
