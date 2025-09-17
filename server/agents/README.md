# Agents

This folder contains agent-specific assets used by the backend, organized by agent type. Each agent directory includes:

- `system_prompt.md`: The agent's role and behavior instructions.
- `tools.py`: Tool schemas (OpenAI-compatible) and a registry of Python callables for execution.

Integrations can import these modules to attach tools and the system prompt to OpenRouter/OpenAI-style chat requests.

