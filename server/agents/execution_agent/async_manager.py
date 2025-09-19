"""Async Runtime Manager for parallel execution agent processing."""

import asyncio
import uuid
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
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
    batch_id: str
    created_at: datetime = field(default_factory=datetime.now)
    future: Optional[asyncio.Future] = None


@dataclass
class _BatchState:
    """Aggregate execution state for a single interaction-agent turn."""

    batch_id: str
    created_at: datetime = field(default_factory=datetime.now)
    pending: int = 0
    results: List[ExecutionResult] = field(default_factory=list)


class AsyncRuntimeManager:
    """Manages parallel execution of multiple agents."""

    def __init__(self, timeout_seconds: int = 60):
        """Initialize the async runtime manager."""

        self.timeout_seconds = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._pending: Dict[str, PendingExecution] = {}
        self._batch_lock = asyncio.Lock()
        self._batch_state: Optional[_BatchState] = None

    async def execute_agent(
        self,
        agent_name: str,
        instructions: str,
        request_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute an agent asynchronously and buffer the result for batch dispatch."""

        if not request_id:
            request_id = str(uuid.uuid4())

        batch_id = await self._register_pending_execution(agent_name, instructions, request_id)

        try:
            logger.info("Starting execution", extra={"agent": agent_name, "request_id": request_id})
            result = await asyncio.wait_for(
                self._execute_agent_async(agent_name, instructions),
                timeout=self.timeout_seconds,
            )
            logger.info("Completed execution", extra={"agent": agent_name, "request_id": request_id})
        except asyncio.TimeoutError:
            logger.error(
                "Execution timed out",
                extra={"agent": agent_name, "request_id": request_id, "timeout": self.timeout_seconds},
            )
            result = ExecutionResult(
                agent_name=agent_name,
                success=False,
                response=f"Execution timed out after {self.timeout_seconds} seconds",
                error="Timeout",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "Execution failed unexpectedly",
                extra={"agent": agent_name, "request_id": request_id},
            )
            result = ExecutionResult(
                agent_name=agent_name,
                success=False,
                response=f"Execution failed: {exc}",
                error=str(exc),
            )
        finally:
            self._pending.pop(request_id, None)

        await self._complete_execution(batch_id, result, agent_name)
        return result

    async def execute_multiple_agents(
        self,
        executions: List[Dict[str, str]],
    ) -> List[ExecutionResult]:
        """Execute multiple agents in parallel."""

        tasks = []
        for execution in executions:
            agent_name = execution.get("agent_name", "")
            instructions = execution.get("instructions", "")
            request_id = execution.get("request_id")

            if agent_name and instructions:
                task = self.execute_agent(agent_name, instructions, request_id)
                tasks.append(task)
            else:
                tasks.append(
                    self._create_error_result(
                        agent_name or "unknown",
                        "Missing agent name or instructions",
                    )
                )

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        final_results: List[ExecutionResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent_name = executions[i].get("agent_name", "unknown")
                final_results.append(
                    ExecutionResult(
                        agent_name=agent_name,
                        success=False,
                        response=f"Unexpected error: {result}",
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        return final_results

    async def _execute_agent_async(self, agent_name: str, instructions: str) -> ExecutionResult:
        """Asynchronous execution of an agent."""

        runtime = ExecutionAgentRuntime(agent_name=agent_name)
        return await runtime.execute(instructions)

    async def _create_error_result(self, agent_name: str, error: str) -> ExecutionResult:
        """Create an error result."""

        return ExecutionResult(
            agent_name=agent_name,
            success=False,
            response=f"Error: {error}",
            error=error,
        )

    async def _register_pending_execution(
        self,
        agent_name: str,
        instructions: str,
        request_id: str,
    ) -> str:
        """Attach a new execution to the active batch, creating one when required."""

        async with self._batch_lock:
            if self._batch_state is None:
                batch_id = str(uuid.uuid4())
                self._batch_state = _BatchState(batch_id=batch_id)
                logger.debug("Opened execution batch", extra={"batch_id": batch_id})
            else:
                batch_id = self._batch_state.batch_id

            self._batch_state.pending += 1

            pending = PendingExecution(
                request_id=request_id,
                agent_name=agent_name,
                instructions=instructions,
                batch_id=batch_id,
            )
            self._pending[request_id] = pending

            return batch_id

    async def _complete_execution(
        self,
        batch_id: str,
        result: ExecutionResult,
        agent_name: str,
    ) -> None:
        """Record the execution result and dispatch when the batch finishes."""

        dispatch_payload: Optional[str] = None

        async with self._batch_lock:
            state = self._batch_state
            if state is None or state.batch_id != batch_id:
                logger.warning(
                    "Execution finished for unknown batch",
                    extra={"agent": agent_name, "batch_id": batch_id},
                )
                return

            state.results.append(result)
            state.pending -= 1

            if state.pending == 0:
                dispatch_payload = self._format_batch_payload(state.results)
                agents = [entry.agent_name for entry in state.results]
                logger.info(
                    "Execution batch completed",
                    extra={"batch_id": batch_id, "agents": agents},
                )
                self._batch_state = None

        if dispatch_payload:
            await self._dispatch_to_interaction_agent(dispatch_payload)

    def get_pending_executions(self) -> List[Dict[str, Any]]:
        """Get list of currently pending executions."""

        return [
            {
                "request_id": pending.request_id,
                "agent_name": pending.agent_name,
                "batch_id": pending.batch_id,
                "created_at": pending.created_at.isoformat(),
                "elapsed_seconds": (datetime.now() - pending.created_at).total_seconds(),
            }
            for pending in self._pending.values()
        ]

    async def shutdown(self) -> None:
        """Shutdown the runtime manager."""

        for pending in self._pending.values():
            if pending.future and not pending.future.done():
                pending.future.cancel()

        self._executor.shutdown(wait=False)

    def _format_batch_payload(self, results: List[ExecutionResult]) -> str:
        """Build the interaction-agent message summarizing all executions."""

        lines: List[str] = []
        for result in results:
            status = "SUCCESS" if result.success else "FAILED"
            response_text = result.response or "(no response provided)"
            lines.append(f"[{status}] {result.agent_name}: {response_text}")
        return "\n".join(lines)

    async def _dispatch_to_interaction_agent(self, payload: str) -> None:
        """Send the aggregated execution summary to the interaction agent."""

        from ..interaction_agent.runtime import InteractionAgentRuntime

        runtime = InteractionAgentRuntime()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(runtime.handle_agent_message(payload))
            return

        loop.create_task(runtime.handle_agent_message(payload))
