"""Async Runtime Manager for parallel execution agent processing."""

import asyncio
import uuid
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from datetime import datetime

from .runtime import ExecutionAgentRuntime, ExecutionResult
from ...logging_config import logger


@dataclass
class PendingExecution:
    """Track a pending execution request."""
    request_id: str
    agent_name: str
    instructions: str
    created_at: datetime = field(default_factory=datetime.now)
    future: Optional[asyncio.Future] = None


class AsyncRuntimeManager:
    """Manages parallel execution of multiple agents."""

    def __init__(self, timeout_seconds: int = 60):
        """
        Initialize the async runtime manager.

        Args:
            timeout_seconds: Timeout for each execution
        """
        self.timeout_seconds = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._pending: Dict[str, PendingExecution] = {}

    async def execute_agent(
        self,
        agent_name: str,
        instructions: str,
        request_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute an agent asynchronously.

        Args:
            agent_name: Name of the agent to execute
            instructions: Instructions for the agent
            request_id: Optional request ID for tracking

        Returns:
            ExecutionResult from the agent
        """
        if not request_id:
            request_id = str(uuid.uuid4())

        # Create pending execution record
        pending = PendingExecution(
            request_id=request_id,
            agent_name=agent_name,
            instructions=instructions
        )
        self._pending[request_id] = pending

        try:
            logger.info(f"Starting execution for agent {agent_name} (request {request_id})")

            # Run execution in thread pool (since OpenRouter client is sync)
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(
                self._executor,
                self._execute_agent_sync,
                agent_name,
                instructions
            )

            pending.future = future

            # Wait with timeout
            result = await asyncio.wait_for(future, timeout=self.timeout_seconds)

            logger.info(f"Completed execution for agent {agent_name} (request {request_id})")
            return result

        except asyncio.TimeoutError:
            logger.error(f"Execution timeout for agent {agent_name} (request {request_id})")
            return ExecutionResult(
                agent_name=agent_name,
                success=False,
                response=f"Execution timed out after {self.timeout_seconds} seconds",
                error="Timeout"
            )
        except Exception as e:
            logger.error(f"Execution failed for agent {agent_name}: {e}")
            return ExecutionResult(
                agent_name=agent_name,
                success=False,
                response=f"Execution failed: {str(e)}",
                error=str(e)
            )
        finally:
            # Clean up pending record
            self._pending.pop(request_id, None)

    async def execute_multiple_agents(
        self,
        executions: List[Dict[str, str]]
    ) -> List[ExecutionResult]:
        """
        Execute multiple agents in parallel.

        Args:
            executions: List of dicts with 'agent_name' and 'instructions'

        Returns:
            List of ExecutionResults in the same order as input
        """
        tasks = []
        for execution in executions:
            agent_name = execution.get("agent_name", "")
            instructions = execution.get("instructions", "")
            request_id = execution.get("request_id")

            if agent_name and instructions:
                task = self.execute_agent(agent_name, instructions, request_id)
                tasks.append(task)
            else:
                # Invalid execution, add error result
                tasks.append(self._create_error_result(agent_name or "unknown", "Missing agent name or instructions"))

        # Wait for all tasks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to ExecutionResults
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    agent_name = executions[i].get("agent_name", "unknown")
                    final_results.append(ExecutionResult(
                        agent_name=agent_name,
                        success=False,
                        response=f"Unexpected error: {str(result)}",
                        error=str(result)
                    ))
                else:
                    final_results.append(result)

            return final_results
        else:
            return []

    def _execute_agent_sync(self, agent_name: str, instructions: str) -> ExecutionResult:
        """Synchronous execution of an agent (runs in thread pool)."""
        runtime = ExecutionAgentRuntime(agent_name=agent_name)
        return runtime.execute(instructions)

    async def _create_error_result(self, agent_name: str, error: str) -> ExecutionResult:
        """Create an error result."""
        return ExecutionResult(
            agent_name=agent_name,
            success=False,
            response=f"Error: {error}",
            error=error
        )

    def get_pending_executions(self) -> List[Dict[str, Any]]:
        """Get list of currently pending executions."""
        return [
            {
                "request_id": p.request_id,
                "agent_name": p.agent_name,
                "created_at": p.created_at.isoformat(),
                "elapsed_seconds": (datetime.now() - p.created_at).total_seconds()
            }
            for p in self._pending.values()
        ]

    async def shutdown(self):
        """Shutdown the runtime manager."""
        # Cancel any pending futures
        for pending in self._pending.values():
            if pending.future and not pending.future.done():
                pending.future.cancel()

        # Shutdown executor
        self._executor.shutdown(wait=False)