"""Simplified Execution Agent Runtime."""

import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .agent import ExecutionAgent
from .tools import get_tool_schemas, get_tool_registry
from ...config import get_settings
from ...openrouter_client import request_chat_completion, OpenRouterError
from ...logging_config import logger


@dataclass
class ExecutionResult:
    """Result from an execution agent."""
    agent_name: str
    success: bool
    response: str
    error: Optional[str] = None
    tools_executed: List[str] = None


class ExecutionAgentRuntime:
    """Manages the execution of a single agent request."""

    def __init__(self, agent_name: str):
        settings = get_settings()
        self.agent = ExecutionAgent(agent_name)
        self.api_key = settings.openrouter_api_key
        self.model = settings.default_model or "openrouter/auto"
        self.tool_registry = get_tool_registry()
        self.tool_schemas = get_tool_schemas()

        if not self.api_key:
            raise ValueError("OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable.")

    def execute(self, instructions: str) -> ExecutionResult:
        """Execute the agent with given instructions."""
        try:
            # Build system prompt with history
            system_prompt = self.agent.build_system_prompt_with_history()

            # Start conversation with the instruction
            messages = [
                {"role": "user", "content": instructions}
            ]

            # First LLM call: What tools should I use?
            logger.info(f"Execution agent {self.agent.name}: Deciding on tools")
            response = self._make_llm_call(system_prompt, messages, with_tools=True)

            # Add the assistant's response to messages
            assistant_message = response.get("choices", [{}])[0].get("message", {})
            messages.append({"role": "assistant", "content": assistant_message.get("content", "") or "I'll execute the following tools."})

            # Extract and execute tools
            tool_calls = self._extract_tool_calls(response)
            tools_executed = []

            if tool_calls:
                # Build execution report
                execution_report = "Tool Execution Results:\n\n"

                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("arguments", {})
                    tools_executed.append(tool_name)

                    logger.info(f"Executing {tool_name}")

                    # Try to execute
                    success, result = self._execute_tool(tool_name, tool_args)

                    if not success and "error" in result:
                        # Log the error details
                        logger.warning(f"Tool {tool_name} failed: {result.get('error', 'Unknown error')}")
                        logger.debug(f"Failed with args: {json.dumps(tool_args, indent=2)}")

                        # Retry once with LLM help
                        logger.info(f"Retrying {tool_name} after error")
                        success, result = self._retry_tool(
                            tool_name,
                            tool_args,
                            result["error"],
                            system_prompt,
                            messages
                        )

                        if success:
                            logger.info(f"Retry successful for {tool_name}")
                        else:
                            logger.error(f"Retry failed for {tool_name}: {result.get('error', 'Unknown error')}")

                    # Add to execution report
                    if success:
                        execution_report += f"✓ {tool_name}: Success\n"
                        execution_report += f"  Result: {json.dumps(result, indent=2)[:500]}\n\n"
                    else:
                        execution_report += f"✗ {tool_name}: Failed\n"
                        execution_report += f"  Error: {result.get('error', 'Unknown error')}\n\n"

                    # Record in log
                    self.agent.record_tool_execution(
                        tool_name,
                        json.dumps(tool_args),
                        json.dumps(result) if success else str(result.get('error', ''))
                    )

                # Add execution report to messages
                messages.append({"role": "user", "content": execution_report + "\nBased on these results, provide a summary of what was accomplished."})

                # Second LLM call: Analyze and summarize
                logger.info(f"Execution agent {self.agent.name}: Analyzing results")
                final_response = self._make_llm_call(system_prompt, messages, with_tools=False)
                response_text = final_response.get("choices", [{}])[0].get("message", {}).get("content", "")

            else:
                # No tools needed, use initial response
                response_text = assistant_message.get("content", "No action required.")

            # Record final response
            self.agent.record_response(response_text)

            return ExecutionResult(
                agent_name=self.agent.name,
                success=True,
                response=response_text,
                tools_executed=tools_executed or []
            )

        except Exception as e:
            logger.error(f"Execution agent {self.agent.name} failed: {e}")
            error_msg = str(e)
            self.agent.record_response(f"Error: {error_msg}")

            return ExecutionResult(
                agent_name=self.agent.name,
                success=False,
                response=f"Failed to complete task: {error_msg}",
                error=error_msg
            )

    def _make_llm_call(self, system_prompt: str, messages: List[Dict], with_tools: bool) -> Dict:
        """Make an LLM call."""
        tools_to_send = self.tool_schemas if with_tools else None
        logger.info(f"Execution agent calling with model: {self.model}, tools: {len(tools_to_send) if tools_to_send else 0}")
        return request_chat_completion(
            model=self.model,
            messages=messages,
            system=system_prompt,
            api_key=self.api_key,
            tools=tools_to_send,
            temperature=0.7
        )

    def _extract_tool_calls(self, response: Dict) -> List[Dict]:
        """Extract tool calls from LLM response."""
        tool_calls = []
        message = response.get("choices", [{}])[0].get("message", {})
        raw_tools = message.get("tool_calls", [])

        for tool in raw_tools:
            function = tool.get("function", {})
            name = function.get("name", "")
            args = function.get("arguments", "")

            # Parse arguments if string
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except json.JSONDecodeError:
                    args = {}

            if name:
                tool_calls.append({"name": name, "arguments": args})

        return tool_calls

    def _execute_tool(self, tool_name: str, arguments: Dict) -> Tuple[bool, Any]:
        """Execute a tool. Returns (success, result)."""
        tool_func = self.tool_registry.get(tool_name)
        if not tool_func:
            return False, {"error": f"Unknown tool: {tool_name}"}

        try:
            result = tool_func(**arguments)
            return True, result
        except Exception as e:
            return False, {"error": str(e)}

    def _retry_tool(
        self,
        tool_name: str,
        original_args: Dict,
        error: str,
        system_prompt: str,
        conversation: List[Dict]
    ) -> Tuple[bool, Any]:
        """Retry a failed tool with LLM assistance."""
        # Build retry context
        retry_messages = conversation + [
            {
                "role": "user",
                "content": f"The tool {tool_name} failed with error: {error}\n"
                          f"Original arguments: {json.dumps(original_args)}\n"
                          f"Please provide corrected arguments for {tool_name}."
            }
        ]

        try:
            # Ask LLM for corrected call
            response = self._make_llm_call(system_prompt, retry_messages, with_tools=True)
            retry_calls = self._extract_tool_calls(response)

            # Find the retry for our tool
            for call in retry_calls:
                if call.get("name") == tool_name:
                    return self._execute_tool(tool_name, call.get("arguments", {}))

            return False, {"error": f"LLM did not provide corrected {tool_name} call"}

        except Exception as e:
            return False, {"error": f"Retry failed: {str(e)}"}