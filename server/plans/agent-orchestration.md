# Interaction & Execution Agent Orchestration Plan

## Phase 1 · Baseline Assessment & Guardrails
- [x] Catalogue current message-handling paths (notably `services/chat.py`) to understand entry points and determine which pieces will be replaced outright.
- [x] Inventory existing persistence helpers (`services/history.py`) and decide what can be removed once the new logging system lands.
- [x] Review execution-agent tooling (`agents/execution_agent/tools.py`, `services/gmail.py`) to plan how the new architecture will invoke them.
- [x] Outline the revised response contract now that SSE streaming will be removed in favor of blocking responses.

## Phase 2 · Conversation & Prompt Infrastructure
- [x] Replace legacy chat history with an append-only writer targeting `data/conversation/poke_conversation.log`, enforcing UTF-8, newline separation, and `<user_message>/<agent_message>/<poke_reply>` ordering.
- [x] Build a log service with `record_user_message`, `record_agent_message`, and `record_reply` helpers plus `load_transcript` for prompt assembly.
- [x] Add strict tag validation and whitespace normalization to keep the transcript canonical and injection-resistant.
- [x] Construct a system-prompt composer that injects: (a) static persona instructions, (b) full conversation transcript, and (c) `<active_agents>` roster block so the model receives history via the system field while preserving the OpenRouter message array API.

## Phase 3 · Execution-Agent Journal Persistence
- [x] Establish `data/execution_agents/` as the home for per-agent logs; implement deterministic filename sanitization (e.g., `slugify(name) + .log`).
- [x] Provide lightweight append helpers that record `<agent_request>` and `<agent_action>` entries with timestamps.
- [x] Load recent actions for each agent during startup so the roster seeds itself directly from the journals.
- [x] Ensure writes are serialized with per-agent locks so multiple requests cannot interleave writes.

## Phase 4 · Active-Agent Roster Management
- [x] Introduce a roster manager that owns `{ name, recentActions }` records, sourcing data from the execution-agent logs and updating in-memory state reactively.
- [x] Persist roster metadata to `data/execution_agents/roster.json` (or similar) so agent identities and recent history survive restarts.
- [x] Define serialization for the system prompt using dedicated tags (e.g., `<active_agents>` with nested `<agent>` blocks) that slot into the composed system instructions.
- [ ] Expose management hooks for future lifecycle operations (retire, rename) even if not immediately surfaced.

## Phase 5 · Interaction Agent Message Flow
- [x] Rebuild the `/chat` pipeline to use blocking OpenRouter completions, removing streaming-related code (`StreamingResponse`, `sse_iter`, etc.).
- [x] Simplify the OpenRouter client to use standard JSON responses, eliminating SSE delta handling entirely.
- [x] Return plain-text assistant responses (instead of `{ ok, message }` JSON) so the UI can render content directly while maintaining error JSON for failures.
- [x] Ensure the OpenRouter payload retains the user message array while injecting the composed system prompt and `sendmessageto_agent` tool schema only.
- [x] Introduce dedicated `agents/interaction_agent` helpers for prompt composition, history trimming, and tool dispatch to keep FastAPI surface minimal.
- [x] Implement transcript truncation safeguards only if absolutely required by token limits, otherwise rely on the append-only log as-is.
- [x] Update logging/telemetry to reflect synchronous request handling.
- [x] Validate baseline web app flow (message send/receive + history) without tool calls, confirming persistence aligns with new log format.

## Phase 6 · `sendmessageto_agent` Tool Implementation
- [x] Define the tool schema with `agent_name` and `instructions` parameters and register it with the interaction agent.
- [x] Implement the handler to create or update execution-agent state, append `<request>` entries, and dispatch instructions to the execution runtime.
- [x] Return a structured acknowledgement including identifiers needed for downstream tracking.
- [x] Emit OpenRouter `tool_call` deltas from the client wrapper so interaction tools are surfaced without bespoke SSE parsing.
- [ ] Cover edge cases (invalid names, empty instructions, file-write failures) with targeted tests.

## Phase 7 · Execution Agent Runtime Implementation
- [x] Update `send_message_to_agent` tool to accept human-readable agent names in the parameter description, supporting both new agent creation and reusing existing agents from the roster.
- [x] Create `ExecutionAgent` class with: (a) system prompt template for instructions, (b) conversation history loading from logs (simplified to read directly from logs), (c) current request from interaction agent, (d) optional conversation limit parameter.
- [x] Build execution agent LLM flow with two-step process:
  - First LLM call: System prompt + agent history + current request → Decide which tools to execute
  - Execute tools with retry mechanism (one retry on error, passing error message back to LLM with full context)
  - Second LLM call: Analyze tool results → Generate response for interaction agent
- [x] Implement `ExecutionAgentRuntime` class that manages individual agent executions:
  - Builds system prompt with embedded history from logs
  - Handles OpenRouter API calls with Gmail tool schemas
  - Records all requests, actions, tool responses, and agent responses using XML-style tags
  - Simplified to show complete conversation trail in each LLM call
- [x] Create `AsyncRuntimeManager` to orchestrate parallel execution:
  - Spawns async tasks for each `send_message_to_agent` call
  - Tracks futures with unique request IDs
  - Implements 60-second timeout with proper error handling
  - Returns `ExecutionResult` containing agent name, success status, response message, and any errors
- [x] Create `InteractionAgentRuntime` to mirror execution agent architecture:
  - Moved all interaction logic from chat.py for symmetry
  - Handles tool calls and execution agent coordination
  - Makes second LLM call when execution agents are used
- [x] Update interaction agent to handle execution agent invocations:
  - Detects when tool calls include execution agents (0, 1, or multiple)
  - Collects all execution results asynchronously
  - Records execution agent messages as `<agent_message>` tags (internal)
  - Makes second LLM call to analyze execution results and craft final user response
  - Records only final response as `<poke_reply>` tag (shown to users)
- [x] Remove API key and model parameters throughout codebase:
  - All components now load from environment variables via get_settings()
  - Cleaner initialization without parameter threading
- [x] Restructure logging to use XML-style tags consistently:
  - Execution agents: `<agent_request>`, `<agent_action>`, `<tool_response>`, `<agent_response>`
  - Interaction agent: `<user_message>`, `<agent_message>`, `<poke_reply>`
- [x] Gmail tool integration already complete (`execution_agent/tools.py` has all 4 operations)
- [x] Execution logging system with XML tags (`services/execution_log.py`)
- [ ] **Draft Display & Confirmation Flow:**
  - Execution agent must return full draft content (to, subject, body) not just draft ID
  - Interaction agent must format and display draft clearly to user
  - System must wait for user confirmation before calling `gmail_execute_draft`
  - Never auto-send emails without explicit user approval

## Phase 8 · Message Ordering & Response Coordination
- [ ] Implement simple message ordering:
  - Assign sequential `message_id` to each incoming user message
  - Block responses for message N+1 until message N completes
  - Release responses in correct order
- [ ] Update `/chat` endpoint to enforce ordering:
  - Process messages sequentially (simple queue)
  - When execution agents used: Wait for all results → Second LLM call → Final response
  - When no execution agents: Direct response after first LLM call
- [ ] **Draft Display Enhancement:**
  - Add special formatting for email drafts in responses
  - Preserve draft IDs in conversation context for follow-up actions
  - Enable "send the draft" or "modify the draft" commands to work with context

## Phase 9 · Basic Error Handling
- [ ] Handle execution agent failures gracefully:
  - One retry for tool execution errors (pass error back to LLM)
  - 60-second timeout for execution agents
  - If all execution agents fail, interaction agent still provides response
- [ ] Ensure partial success works:
  - Some agents succeed, others fail → Interaction agent analyzes available results
  - Include error information in final response

## Phase 10 · Manual Testing & Validation
- [ ] Test core workflows manually:
  - Create new agent with specific task
  - Reuse existing agent from roster
  - Multiple agents working on single request
  - Message ordering (send two messages quickly, verify order)
  - Agent with old history still functioning
- [ ] Basic documentation:
  - README with architecture overview
  - How to run and test the system
  - Known limitations
