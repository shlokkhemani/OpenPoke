"""Interaction Agent Runtime - handles LLM calls and execution agent coordination."""

import asyncio
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .agent import build_system_prompt, prepare_message_with_history
from .tools import get_tool_schemas, handle_tool_call, _pending_executions
from ...config import get_settings
from ...services.conversation_log import get_conversation_log
from ...services.send_message import execute_pending_agents
from ...openrouter_client import request_chat_completion, OpenRouterError
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

    async def execute(self, user_message: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> InteractionResult:
        """
        Execute the interaction agent with a user message.

        Args:
            user_message: The user's message
            temperature: LLM temperature
            max_tokens: Maximum tokens for response

        Returns:
            InteractionResult with the agent's response
        """
        try:
            # Load conversation transcript BEFORE recording the new message
            # This way we only get the history, not the current message
            transcript_before = self.conversation_log.load_transcript()

            # NOW record the user message for future history
            self.conversation_log.record_user_message(user_message)

            # Build system prompt (no history, just personality + active agents)
            system_prompt = build_system_prompt()

            # Prepare messages with history included as tags, current message separate
            messages = prepare_message_with_history(user_message, transcript_before, message_type="user")

            # Log the messages array for debugging
            logger.info("=" * 80)
            logger.info("OPENROUTER PAYLOAD DEBUG:")
            logger.info("-" * 40)
            logger.info(f"MESSAGES ARRAY (includes history as tags): {json.dumps(messages, indent=2)}")
            logger.info("=" * 80)

            logger.info(f"Interaction agent: Processing user message (length: {len(user_message)})")

            # First LLM call: Process user message and decide on tools
            response = await self._make_llm_call(
                system_prompt=system_prompt,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                with_tools=True
            )

            # Process response and tool calls
            assistant_response, has_execution_agents = self._process_initial_response(response)

            # If execution agents were used, wait for results and make second LLM call
            if has_execution_agents and _pending_executions:
                final_response = await self._handle_execution_agents(
                    user_message=user_message,
                    initial_response=assistant_response,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                execution_count = len(_pending_executions)
                _pending_executions.clear()
            else:
                final_response = assistant_response
                execution_count = 0

            # Record only the final reply (what user sees)
            self.conversation_log.record_reply(final_response)

            return InteractionResult(
                success=True,
                response=final_response,
                execution_agents_used=execution_count
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

    async def _make_llm_call(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        with_tools: bool
    ) -> Dict[str, Any]:
        """Make an LLM call via OpenRouter."""
        return request_chat_completion(
            model=self.model,
            messages=messages,
            system=system_prompt,
            api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=self.tool_schemas if with_tools else None
        )

    def _process_initial_response(self, response: Dict[str, Any]) -> tuple[str, bool]:
        """
        Process the initial LLM response and handle tool calls.

        Returns:
            Tuple of (assistant_response, has_execution_agents)
        """
        assistant_chunks = []
        tool_responses = []
        has_execution_agents = False

        # Extract message content
        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message") or {}

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            assistant_chunks.append(content)

        # Process tool calls
        tool_calls = message.get("tool_calls") or []
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                name = str(tool_call.get("function", {}).get("name") or "").strip()
                arguments = tool_call.get("function", {}).get("arguments")

                # Check if this is an execution agent call
                if name == "send_message_to_agent":
                    has_execution_agents = True

                # Handle the tool call
                acknowledgement = handle_tool_call(name, arguments)
                if acknowledgement:
                    tool_responses.append(acknowledgement)

        # Combine chunks and tool responses
        if tool_responses:
            assistant_chunks.append("\n".join(tool_responses))

        assistant_text = "".join(assistant_chunks).strip()
        return assistant_text, has_execution_agents

    async def _handle_execution_agents(
        self,
        user_message: str,
        initial_response: str,
        system_prompt: str,
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """
        Handle execution agent results and make second LLM call.

        Returns:
            Final response after analyzing execution results
        """
        logger.info(f"Executing {len(_pending_executions)} agents")

        # Execute all pending agents
        execution_results = await execute_pending_agents(_pending_executions)

        # Get transcript BEFORE recording agent messages
        # This way the agent messages are not in the history, but will be the "current" messages
        transcript_before_agents = self.conversation_log.load_transcript()

        # NOW record execution agent messages (internal, not shown to user)
        for result in execution_results:
            self.conversation_log.record_agent_message(
                f"[{result.agent_name}] {result.response}"
            )

        # Prepare a simple textual summary in case the model returns no content
        results_lines = []
        for result in execution_results:
            status = "SUCCESS" if result.success else "FAILED"
            snippet = (result.response or "").strip()
            results_lines.append(f"[{status}] {result.agent_name}: {snippet}")
        results_report = "\n".join(results_lines) if results_lines else "No execution agent output."

        # Make second LLM call to analyze results
        logger.info("Making second LLM call to analyze execution results")

        # Build the current content: agent results + instruction
        agent_results = "\n".join([
            f"<agent message>[{result.agent_name}] {result.response}</agent message>"
            for result in execution_results
        ])

        analysis_prompt = f"{agent_results}\n\nBased on the above execution agent results, provide a response to the user."

        # Include history (before agents) as tags, with agent results as current message
        analysis_messages = prepare_message_with_history(analysis_prompt, transcript_before_agents, message_type="agent")

        logger.info("=" * 80)
        logger.info("SECOND LLM CALL PAYLOAD DEBUG:")
        logger.info("-" * 40)
        logger.info(f"MESSAGES ARRAY FOR SECOND CALL (includes history): {json.dumps(analysis_messages, indent=2)}")
        logger.info("=" * 80)

        try:
            analysis_response = await self._make_llm_call(
                system_prompt=system_prompt,
                messages=analysis_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                with_tools=True
            )

            final_content, additional_agents = self._process_initial_response(analysis_response)

            if additional_agents:
                logger.warning("Second LLM call attempted to schedule additional agents; ignoring.")
                _pending_executions.clear()

            if final_content.strip():
                return final_content.strip()
            else:
                # Fallback to results summary
                return results_report

        except Exception as e:
            logger.warning(f"Second LLM call failed: {e}")
            # Fallback to showing raw results
            return results_report
