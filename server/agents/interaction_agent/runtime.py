"""Interaction Agent Runtime - handles LLM calls for user and agent turns."""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

from .agent import build_system_prompt, prepare_message_with_history
from .tools import get_tool_schemas, handle_tool_call
from ...config import get_settings
from ...services.conversation_log import get_conversation_log
from ...openrouter_client import request_chat_completion
from ...logging_config import logger


@dataclass
class InteractionResult:
    """Result from the interaction agent."""
    success: bool
    response: str
    error: Optional[str] = None
    execution_agents_used: int = 0


class InteractionAgentRuntime:
    """Manages the interaction agent's request processing."""

    def __init__(self):
        """Initialize the interaction agent runtime."""
        settings = get_settings()
        self.api_key = settings.openrouter_api_key
        self.model = settings.default_model or "openrouter/auto"
        self.conversation_log = get_conversation_log()
        self.tool_schemas = get_tool_schemas()

        if not self.api_key:
            raise ValueError("OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable.")

    async def execute(self, user_message: str) -> InteractionResult:
        """
        Execute the interaction agent with a user message.

        Args:
            user_message: The user's message

        Returns:
            InteractionResult with the agent's response
        """
        try:
            # Load conversation transcript BEFORE recording the new message
            # This way we only get the history, not the current message
            transcript_before = self.conversation_log.load_transcript()

            # NOW record the user message for future history
            self.conversation_log.record_user_message(user_message)

            # Build system prompt (static instructions only)
            system_prompt = build_system_prompt()

            # Prepare message that contains history, roster, and the latest user turn
            messages = prepare_message_with_history(user_message, transcript_before, message_type="user")

            logger.info("Processing user message through interaction agent")

            allowed_tool_names: Set[str] = {"send_message_to_agent"}
            response = await self._make_llm_call(
                system_prompt=system_prompt,
                messages=messages,
                tool_schemas=self._tool_subset(allowed_tool_names)
            )

            assistant_response, tool_used = self._process_model_response(response, allowed_tool_names)

            final_response = ""
            if not tool_used:
                raw_reply = assistant_response.strip()
                if raw_reply:
                    self.conversation_log.record_reply(raw_reply)
                    final_response = raw_reply

            return InteractionResult(
                success=True,
                response=final_response,
            )

        except Exception as e:
            logger.error(f"Interaction agent failed: {e}")
            error_msg = str(e)

            # Still try to record the error
            try:
                self.conversation_log.record_reply(f"Error: {error_msg}")
            except:
                pass

            return InteractionResult(
                success=False,
                response=f"I encountered an error: {error_msg}",
                error=error_msg
            )

    async def handle_agent_message(
        self,
        agent_message: str,
    ) -> InteractionResult:
        """Process a message reported by an execution agent."""
        transcript_before = self.conversation_log.load_transcript()
        self.conversation_log.record_agent_message(agent_message)

        system_prompt = build_system_prompt()
        messages = prepare_message_with_history(agent_message, transcript_before, message_type="agent")

        allowed_tool_names: Set[str] = {"send_draft"}
        response = await self._make_llm_call(
            system_prompt=system_prompt,
            messages=messages,
            tool_schemas=self._tool_subset(allowed_tool_names)
        )

        assistant_response, _ = self._process_model_response(response, allowed_tool_names)

        raw_reply = assistant_response.strip()
        final_response = raw_reply

        if raw_reply:
            self.conversation_log.record_reply(raw_reply)

        return InteractionResult(success=True, response=final_response)

    async def _make_llm_call(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tool_schemas: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Make an LLM call via OpenRouter."""
        return request_chat_completion(
            model=self.model,
            messages=messages,
            system=system_prompt,
            api_key=self.api_key,
            tools=tool_schemas
        )

    def _process_model_response(
        self,
        response: Dict[str, Any],
        allowed_tool_names: Set[str]
    ) -> tuple[str, bool]:
        """Extract assistant text and execute allowed tool calls."""
        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message") or {}

        content = message.get("content")
        assistant_text = content if isinstance(content, str) else ""

        tool_used = False
        tool_calls = message.get("tool_calls") or []
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                name = str(tool_call.get("function", {}).get("name") or "").strip()
                arguments = tool_call.get("function", {}).get("arguments")

                if not name:
                    continue

                if name not in allowed_tool_names:
                    logger.warning(
                        "Ignoring disallowed tool call from interaction agent",
                        extra={"tool": name}
                    )
                    continue

                tool_used = True
                try:
                    handle_tool_call(name, arguments)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error("Tool call failed", extra={"tool": name, "error": str(exc)})

        return assistant_text, tool_used

    def _tool_subset(self, allowed_names: Set[str]) -> Optional[List[Dict[str, Any]]]:
        """Return schemas matching allowed tool names."""
        schemas = []
        for schema in self.tool_schemas:
            function_block = schema.get("function")
            if not function_block:
                continue

            if function_block.get("name") in allowed_names:
                schemas.append(schema)
        return schemas or None
