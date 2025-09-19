# Trigger Functionality Implementation Plan

- [ ] Document architecture decisions and confirm data flow between interaction, execution, and scheduler components (ensures everyone shares the same mental model before coding).
- [ ] Set up SQLite trigger store under `server/data/` with automatic schema creation on startup (gives us durable persistence without external dependencies).
- [ ] Build a trigger repository/service layer to encapsulate CRUD operations and enforce agent scoping (keeps database logic isolated and reusable).
- [ ] Implement timezone capture mechanism from the web client to server so triggers store canonical zoneinfo strings (lets recurrence calculations respect local time while defaulting to UTC when missing).
- [ ] Add `createTrigger`, `updateTrigger`, and `listTriggers` execution-agent tools that call the trigger service (empowers agents to manage reminders while hiding implementation details from the LLM).
- [ ] Derive `next_trigger` server-side from recurrence rules using `dateutil.rrule` utilities (prevents LLM mistakes and keeps scheduling consistent with server time).
- [ ] Introduce a background scheduler loop polling every 10 seconds to dispatch due triggers via `ExecutionAgentRuntime` (ensures reminders actually fire while reusing existing agent execution flow).
- [ ] Update execution agent system prompt (and related docs) to describe the new trigger tools and expectations (teaches the agent how and when to use them).
- [ ] Extend the "clear history" action to wipe the trigger table alongside conversation data (keeps user resets comprehensive and predictable).
- [ ] Add targeted tests or manual verification scripts to exercise create/update/list flows and a mock trigger firing cycle (gives confidence before shipping).

