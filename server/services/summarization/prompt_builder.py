from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Dict, List

from .state import LogEntry


@dataclass(frozen=True)
class SummaryPrompt:
    system_prompt: str
    messages: List[Dict[str, str]]


_SYSTEM_PROMPT = dedent(
    """
    You are a meticulous chief-of-staff-style memory curator for an intelligent assistant.
    Merge the existing memory with the new conversation logs so the assistant retains the
    user's goals, commitments, preferences, decisions, and other actionable facts. Remove
    small talk or redundant chatter. Capture timelines, deadlines, follow-ups, and tool
    outcomes that matter for future assistance. Respond with polished paragraphs only.
    """
).strip()


def _format_existing_summary(previous_summary: str) -> str:
    summary = (previous_summary or "").strip()
    return summary if summary else "None"


def _format_log_entries(entries: List[LogEntry]) -> str:
    lines: List[str] = []
    for entry in entries:
        label = entry.tag.replace("_", " ")
        payload = entry.payload.strip()
        index = entry.index if entry.index >= 0 else "?"
        if payload:
            lines.append(f"[{index}] {label}: {payload}")
        else:
            lines.append(f"[{index}] {label}: (empty)")
    return "\n".join(lines) if lines else "(no new logs)"


def build_summarization_prompt(previous_summary: str, entries: List[LogEntry]) -> SummaryPrompt:
    content = dedent(
        f"""
        Existing memory summary:
        {_format_existing_summary(previous_summary)}

        New conversation logs to merge:
        {_format_log_entries(entries)}

        Produce an updated memory summary that incorporates all new information. Preserve
        actionable commitments, reminders, and user instructions. If nothing new is
        relevant, return the existing summary unchanged.
        """
    ).strip()

    messages = [{"role": "user", "content": content}]
    return SummaryPrompt(system_prompt=_SYSTEM_PROMPT, messages=messages)


__all__ = ["SummaryPrompt", "build_summarization_prompt"]
