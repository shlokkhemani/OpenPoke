# Conversation Summarization + Working Memory Plan

## Phase 1 – Foundations & Configuration
- [x] **Review Current Logging**
  - Confirm existing conversation log format (`server/services/conversation_log.py`).
  - Inventory entry tags (`user message`, `agent message`, `replies`, `wait`, etc.).
- [x] **Define Settings Hooks**
  - Extend `server/config.py` settings object with:
    - `conversation_summary_threshold` (default `100`).
    - `conversation_summary_tail_size` (default `10`).
    - `working_memory_log_path` (default alongside conversation log).
  - Ensure settings expose resolved path helpers and derived booleans (e.g., `summary_enabled`).
- [x] **Outline Failure Handling**
  - Decide retry limits (single retry on next message) and disable behaviour (threshold `0`).
  - Document logging expectations (`summary_started`, `summary_success`, `summary_failed`).

## Phase 2 – Summarization Package Structure
- [x] **Create `server/services/summarization/` Package**
  - Mirror layout style from `server/services/triggers/` (`__init__`, helpers split by concern).
  - Modules to add:
    - `working_memory_log.py` – persistence for summary + tail entries.
    - `state.py` – dataclasses/Pydantic models (`SummaryState`, tail entry DTOs).
    - `prompt_builder.py` – prompt template construction utilities.
    - `scheduler.py` – async scheduling & concurrency guard.
    - `summarizer.py` – OpenRouter interaction + retry handling.
- [x] **Expose Package API**
  - Update `server/services/summarization/__init__.py` to surface key functions/classes.
  - Wire `server/services/__init__.py` to export `get_working_memory_log`, `schedule_summarization`, etc.

- [x] **WorkingMemoryLog Implementation**
  - Implement in `summarization/working_memory_log.py` with capabilities:
    - Persist summary text + metadata (`last_index`, timestamp).
    - Store trailing raw entries (always last `tail_size` entries).
    - Rewrite-on-update semantics (atomic write).
  - Provide helpers:
    - `load_summary_state()` returns summary text, last index, tail messages.
    - `write_summary_state(summary_text, last_index, tail_entries)` rewrites file atomically.
- [x] **Service Layer Integration**
  - Singleton accessor in new package; update `server/services/__init__.py` accordingly.
  - Ensure thread lock pattern mirrors existing services.
- [x] **Utility Types**
  - Define DTOs in `summarization/state.py` for summary metadata and log entry snapshots.

- [x] **Summarizer Flow**
  - Implement `summarization/summarizer.py`:
    - `should_summarize(conversation_log, summary_state)` using thresholds.
    - `summarize(previous_summary, new_entries)` invoking `request_chat_completion` with fixed prompt (via `prompt_builder`).
    - Handle success/failure logging; leave retry to scheduler.
  - Prompt builder uses assistant-centric template (retain user prefs/events, drop fluff).
- [x] **Async Scheduler**
  - Implement `summarization/scheduler.py`:
    - `schedule_summarization()` uses `asyncio.create_task`.
    - Guard against concurrent runs with lock/flag.
    - On completion, persist updated working memory state.
    - On failure, mark for retry next append.

## Phase 5 – Conversation Log Hooks
- [x] **Extend ConversationLog**
  - Add entry counting / tail extraction helpers (may live in new utility module to avoid bloating file).
  - Trigger scheduler from `record_user_message`, `record_reply`, etc., when threshold crossed and summarization enabled.
  - Pass current entry index to scheduler for tail slicing.
- [x] **Tail Extraction Utility**
  - Helper (e.g., `summarization/utils.py`) to fetch last `tail_size` entries (any tag) for working memory.
- [x] **Summary Persistence**
  - After summarization success:
    - Update working memory log with `<previous_conversation_summary>` entry and trailing raw logs.
    - Record `last_summarized_index` (line count consumed) so subsequent runs only feed new entries + previous summary.
    - Keep raw conversation log untouched for UI.

## Phase 6 – Interaction Agent Integration
- [x] **Modify Prompt Assembly**
  - Update `server/agents/interaction_agent/runtime.py` to load transcript from working memory package when available, falling back to raw log if summary disabled.
  - Ensure `_run_interaction_loop` still handles user/agent messages consistently.
- [x] **System Prompt Helper**
  - Adjust `server/agents/interaction_agent/agent.py::_render_conversation_history` to render:
    - `<previous_conversation_summary>` block for summary text.
    - `<recent_log>` or original `<tag>` entries for tail logs.

- [x] **Chat History Endpoint**
  - Confirm `/api/v1/chat/history` continues returning raw log (no summary exposure).
- [x] **Models & Serialization**
  - Introduce internal models in `summarization/state.py` as needed without affecting API schemas.

- [x] **Unit Tests** *(not required per user instruction)*
  - WorkingMemoryLog read/write & restart persistence.
  - Summarizer prompt construction + success/failure paths (mocked OpenRouter).
  - Scheduler concurrency guard & retry flagging.
- [x] **Integration / Behavioural Tests** *(not required per user instruction)*
  - End-to-end: append > threshold entries, verify working memory file contents and interaction agent usage.
  - Retry path: force summarizer failure -> ensure next append triggers retry.
  - Disable: threshold `0` → no summarization triggered.
- [ ] **Manual QA Checklist**
  - Drive conversation past threshold, inspect logs & working memory file, verify prompt assembly.
  - Restart server, confirm summary state persists and working memory reloads correctly.

## Phase 9 – Documentation & Cleanup
- [ ] **Update Developer Docs**
  - Document new `summarization` package, configuration defaults, dual-log behaviour.
- [ ] **Add Comments**
  - Brief explanatory comments where logic is non-obvious (async scheduling, tail slicing).
- [ ] **Review Logging Configuration**
  - Ensure log messages mimic existing patterns (`logger.info`/`logger.error`) for observability.
