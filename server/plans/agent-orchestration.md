# Interaction & Execution Agent Orchestration Plan

## Phase 1 · Baseline Assessment & Guardrails
- [x] Catalogue current message-handling paths (notably `services/chat.py`) to understand entry points and determine which pieces will be replaced outright.
- [x] Inventory existing persistence helpers (`services/history.py`) and decide what can be removed once the new logging system lands.
- [x] Review execution-agent tooling (`agents/execution_agent/tools.py`, `services/gmail.py`) to plan how the new architecture will invoke them.
- [x] Outline the revised response contract now that SSE streaming will be removed in favor of blocking responses.

## Phase 2 · Conversation & Prompt Infrastructure
- [x] Replace legacy chat history with an append-only writer targeting `data/conversation/poke_conversation.log`, enforcing UTF-8, newline separation, and `<user message>/<agent message>/<replies>` ordering.
- [x] Build a log service with `record_user_message`, `record_agent_message`, and `record_reply` helpers plus `load_transcript` for prompt assembly.
- [x] Add strict tag validation and whitespace normalization to keep the transcript canonical and injection-resistant.
- [x] Construct a system-prompt composer that injects: (a) static persona instructions, (b) full conversation transcript, and (c) `<active_agents>` roster block so the model receives history via the system field while preserving the OpenRouter message array API.

## Phase 3 · Execution-Agent Journal Persistence
- [x] Establish `data/execution_agents/` as the home for per-agent logs; implement deterministic filename sanitization (e.g., `slugify(name) + .log`).
- [x] Provide lightweight append helpers that record `<request>` and `<action performed>` entries with ISO timestamps.
- [ ] Create loaders that rebuild the last 10 actions per agent on startup to seed the roster immediately.
- [x] Ensure writes are serialized with per-agent locks so multiple requests cannot interleave writes.

## Phase 4 · Active-Agent Roster Management
- [x] Introduce a roster manager that owns `{ name, recentActions }` records, sourcing data from the execution-agent logs and updating in-memory state reactively.
- [x] Persist roster metadata to `data/execution_agents/roster.json` (or similar) so agent identities and recent history survive restarts.
- [x] Define serialization for the system prompt using dedicated tags (e.g., `<active_agents>` with nested `<agent>` blocks) that slot into the composed system instructions.
- [ ] Expose management hooks for future lifecycle operations (retire, rename) even if not immediately surfaced.

## Phase 5 · Interaction Agent Message Flow
- [x] Rebuild the `/chat` pipeline to use blocking OpenRouter completions, removing streaming-related code (`StreamingResponse`, `sse_iter`, etc.).
- [x] Return plain-text assistant responses (instead of `{ ok, message }` JSON) so the UI can render content directly while maintaining error JSON for failures.
- [x] Ensure the OpenRouter payload retains the user message array while injecting the composed system prompt and `sendmessageto_agent` tool schema only.
- [x] Implement transcript truncation safeguards only if absolutely required by token limits, otherwise rely on the append-only log as-is.
- [x] Update logging/telemetry to reflect synchronous request handling.
- [x] Validate baseline web app flow (message send/receive + history) without tool calls, confirming persistence aligns with new log format.

## Phase 6 · `sendmessageto_agent` Tool Implementation
- [x] Define the tool schema with `agent_name` and `instructions` parameters and register it with the interaction agent.
- [x] Implement the handler to create or update execution-agent state, append `<request>` entries, and dispatch instructions to the execution runtime.
- [x] Return a structured acknowledgement including identifiers needed for downstream tracking.
- [ ] Cover edge cases (invalid names, empty instructions, file-write failures) with targeted tests.

## Phase 7 · Execution Agent Runtime Wiring
- [ ] Implement the execution-agent dispatcher that consumes instructions from `sendmessageto_agent`, runs the appropriate Gmail tool, and writes `<action performed>` entries with outcomes and errors.
- [x] Update or replace existing Gmail service helpers to align with the new data flow (structured responses, error propagation);
      now exposed via `execute_gmail_tool` and used by the execution-agent tool registry.
- [x] Replace execution-agent tool definitions with Gmail Composio actions (create draft, send draft, forward, reply) to match the revised flow and append outcome summaries to the per-agent journal.
- [ ] Provide hooks for future expansion (multiple toolkits, parallel agents) while keeping the current scope focused on Gmail.

## Phase 8 · Output & Display Logic
- [ ] Define how the interaction agent emits regular assistant replies versus draft displays (`<display_draft>` blocks) in the synchronous response body.
- [ ] Implement the path for `display_draft` messages: when the execution agent submits a draft, relay it to the user as a dedicated message after confirmation.
- [ ] Validate the end-to-end flow with mocked completions to ensure transcripts, prompts, and outputs stay in sync.

## Phase 9 · Documentation & Developer Experience
- [ ] Rewrite developer docs to describe the new architecture: conversation logging, roster lifecycle, tool invocation, prompt composition strategy, and synchronous response contract.
- [ ] Add targeted inline comments highlighting non-obvious synchronization or serialization choices.
- [ ] Produce onboarding notes detailing how to reset state (clearing logs, roster) and how to inspect agent journals.

## Phase 10 · Validation & Launch Readiness
- [ ] Build automated tests covering log writing/reading, roster reconstruction, prompt assembly, and tool invocation paths.
- [ ] Run manual end-to-end simulations (user ↔ interaction agent ↔ execution agent ↔ Gmail tool) verifying logs and outputs.
- [ ] Prepare deployment checklist: ensure `data/conversation` and `data/execution_agents` directories exist with correct permissions, remove superseded history files, and update environment configs.
- [ ] Schedule a post-launch review to capture observations and prioritize next-phase improvements (multi-user support, agent retirement policies, additional tooling).
