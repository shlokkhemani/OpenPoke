# Important Email Watcher Plan

## Objectives
- Surface genuinely important incoming Gmail messages to the user without manual prompting.
- Reuse existing Gmail tooling and interaction-agent flow so delivery feels native to the current product.
- Keep the implementation modular so other components (e.g., execution agents) can reuse Gmail parsing/cleaning helpers.

## High-Level Architecture
1. **Shared Gmail helpers** – Centralise email cleaning/normalisation logic that already exists under the execution-agent search task so both the watcher and existing features depend on the same code.
2. **Seen-message store** – Maintain a rotating JSON list of recently processed Gmail message IDs on disk (under `data/`). Skip LLM work for IDs we have already handled; treat the first poll after startup as a warm-up that only seeds the store.
3. **LLM classifier + summariser** – Single OpenRouter call per unseen email that returns `{important: bool, summary?: str}`. Only important emails trigger downstream messaging.
4. **Watcher service** – Background async loop (mirroring `TriggerScheduler`) that polls Gmail every minute, fetches the past 10 minutes of `label:INBOX` mail, runs filtering/classification/summarisation, and forwards important summaries to the interaction agent.
5. **Interaction-agent injection** – Deliver one `handle_agent_message` call per important email so the interaction agent narrates updates using its existing style and logging pipeline.

## Detailed Implementation Steps

### 1. Extract Gmail processing utilities
- Create a new module (e.g., `server/services/gmail_processing.py`).
- Move/re-export `EmailTextCleaner` and related parsing helpers from `server/agents/execution_agent/tasks/search_email/email_cleaner.py` and `_email_from_composio` logic so we can construct a unified email record (`GmailSearchEmail` or simplified dataclass).
- Update the search-email task to import the moved utilities, ensuring no behaviour change (keep function signatures identical where possible).
- Provide functions such as:
  - `clean_message_dict(message: Dict[str, Any]) -> Optional[GmailEmail]` (returns cleaned subject/sender/timestamp/body/etc.).
  - `clean_messages(messages: Sequence[Dict[str, Any]]) -> List[GmailEmail]` helper for batch use.
- Ensure helper code remains timezone-aware and keeps attachment/context extraction as today.

### 2. Implement seen-message store
- Add `server/services/gmail_seen_store.py` (or similar) implementing a small class:
  - Constructor accepts file path (default `data/gmail_seen.json`).
  - Methods: `load()`, `mark_seen(message_ids: Iterable[str])`, `is_seen(message_id)`, `prune(max_entries=300)`.
  - Internal state held in memory with thread-safe locking (like other stores) and persisted as a JSON array.
- On instantiation, load existing IDs; ignore missing/corrupt files gracefully.
- First poll should detect an empty in-memory store and mark fetched IDs as seen without classification (set a `_warmed_up` flag or compare previously loaded IDs).

### 3. Design LLM classifier & summary call
- Reuse `get_settings().default_model` and `.openrouter_api_key` just like agent runtimes.
- Define a function schema or Pydantic model describing output: `{ "important": bool, "summary": Optional[str] }` where `summary` is only allowed when `important` is true.
- Prompt contents should include:
  - Brief instructions emphasising the rubric: surface emails that require attention/action (replies, meeting notices, OTPs, deadlines) and ignore low-impact confirmations/promotions/newsletters.
  - Structured context: sender, subject, timestamp, cleaned body text, important metadata (labels, attachments).
- Implement `classify_and_summarize(email: GmailEmail) -> Optional[str]` returning the summary string when important.
- Ensure error handling/logging for LLM failures and skip on exceptions.

### 4. Build ImportantEmailWatcher service
- Create `server/services/important_email_watcher.py` containing an async class similar to `TriggerScheduler`:
  - Constructor parameters: poll interval (default 60s), Gmail helpers, seen store.
  - Start/stop methods managing an asyncio task and lock.
  - `_poll_once` logic:
    1. Call `gmail_fetch_emails` via shared helper with query `label:INBOX newer_than:10m`, `include_payload=True`, `max_results` (optional cap, e.g., 50).
    2. If Gmail not connected, log and return.
    3. Convert messages using shared cleaner.
    4. On first run (store empty), mark IDs as seen and exit.
    5. For each unseen email (descending order), run classifier; when summary is returned, send it downstream and mark ID seen.
    6. After processing, prune store to ~300 IDs using helper.
  - Ensure emails are processed sequentially to maintain order; optionally skip ones lacking message IDs.
- Provide logging for start/stop, poll results, classification counts, and LLM errors.

### 5. Interaction agent integration
- For each important summary, instantiate/obtain `InteractionAgentRuntime` (reusing pattern from `ExecutionBatchManager._dispatch_to_interaction_agent`).
- Call `runtime.handle_agent_message(summary)` without awaiting the result in the poll loop (either fire-and-forget via loop.create_task or await sequentially; choose the safest approach for rate control).
- Summary text should already include sender/subject/timestamp/actionable guidance so the interaction agent can respond naturally.

### 6. Wire into FastAPI lifecycle
- Expose a singleton getter `get_important_email_watcher()` in `server/services/__init__.py` similar to triggers.
- In `server/app.py` startup event, `await watcher.start()` alongside the existing trigger scheduler; in shutdown, `await watcher.stop()`.
- Ensure idempotent start/stop semantics + defensive checks (no double-start).

### 7. Configuration & file paths
- Add new settings entry if needed for the seen-store path; otherwise derive from existing `data` directory using `Settings.resolve_path`.
- Confirm directory creation (mirroring other stores) before writing JSON.

### 8. Logging & observability
- Use `logger.info` for watcher lifecycle, `logger.debug` for poll summaries, `logger.warning` for Gmail/LLM failures, and `logger.error` only for unexpected crashes.
- Consider structured fields: message IDs processed, counts of important vs skipped.

### 9. Testing & validation roadmap
- Unit tests (or manual harness) for seen-store pruning and warm-up behaviour.
- Integration smoke test (manual) to simulate Gmail responses and ensure summaries flow to conversation log.
- Monitor logs after deployment to ensure the watcher stays alive and respects poll intervals.

## Future Enhancements & Considerations
- Dynamic poll intervals based on user activity or Gmail push notifications (webhooks).
- Add user-facing controls (enable/disable proactive surfacing, adjust importance rubric).
- Cache Gmail history IDs to avoid scanning windows when Gmail query granularity is limited.
- Extend classifier prompt with user-specific preferences or allow outranking via heuristics (e.g., senders on VIP list).
- Sharing the LLM prompt/config via settings for quick adjustments without redeploying.
