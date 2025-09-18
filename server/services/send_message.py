"""Service to handle sending messages to execution agents and collecting results."""

import asyncio
from typing import List, Dict, Any, Optional

from ..agents.execution_agent.async_manager import AsyncRuntimeManager, ExecutionResult
from ..logging_config import logger
from .agent_roster import get_agent_roster


class MessageToAgentService:
    """Service to handle interaction between interaction agent and execution agents."""

    def __init__(self):
        """Initialize the service."""
        self.runtime_manager = AsyncRuntimeManager()

    async def send_messages_to_agents(
        self,
        agent_requests: List[Dict[str, str]]
    ) -> List[ExecutionResult]:
        """
        Send messages to multiple agents and collect results.

        Args:
            agent_requests: List of dicts with 'agent_name', 'instructions', and optionally 'request_id'

        Returns:
            List of ExecutionResults
        """
        if not agent_requests:
            return []

        logger.info(f"Sending messages to {len(agent_requests)} agents")

        # Add all agent names to roster
        roster = get_agent_roster()
        for request in agent_requests:
            agent_name = request.get('agent_name', '')
            if agent_name:
                roster.add_agent(agent_name)

        # Execute all agents in parallel
        results = await self.runtime_manager.execute_multiple_agents(agent_requests)

        # Log summary
        successful = sum(1 for r in results if r.success)
        logger.info(f"Execution complete: {successful}/{len(results)} agents succeeded")

        return results

    async def shutdown(self):
        """Shutdown the service."""
        await self.runtime_manager.shutdown()


# Global instance (will be initialized when needed)
_service_instance: Optional[MessageToAgentService] = None


def get_message_service() -> MessageToAgentService:
    """Get or create the message service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MessageToAgentService()
    return _service_instance


async def execute_pending_agents(
    pending_executions: Dict[str, Dict[str, Any]]
) -> List[ExecutionResult]:
    """
    Execute pending agent requests.

    Args:
        pending_executions: Dict of request_id -> execution info

    Returns:
        List of ExecutionResults
    """
    if not pending_executions:
        return []

    # Convert to list format for execution
    agent_requests = [
        {
            "agent_name": exec_info["agent_name"],
            "instructions": exec_info["instructions"],
            "request_id": request_id
        }
        for request_id, exec_info in pending_executions.items()
    ]

    service = get_message_service()
    return await service.send_messages_to_agents(agent_requests)