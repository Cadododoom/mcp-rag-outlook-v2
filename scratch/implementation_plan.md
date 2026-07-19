# Implementation Plan — Multi-Agent Context Tracking & Tree Traversal

We will enhance the desktop context widget to support tracking multiple concurrent subagent sessions, traversing connected conversation families bidirectionally, and fixing SQLite query safety errors.

## Proposed Changes

### Context Widget Core

#### [MODIFY] [tracker.py](file:///home/theworks/teamwork_projects/floating_context_widget/tracker.py)
* **Bidirectional Family Tree Traversal:** Refactor `get_session_family_ids` to run a Breadth-First Search (BFS) traversing both parent pointers and child pointers. This ensures that any parent session, child session, or sibling subagent session resolves to the exact same family ID list.
* **SQL Query Safety Fix:** Update `calculate_hermes_family_conversation_tokens` to use `COALESCE` when summing character lengths:
  ```sql
  SELECT SUM(COALESCE(length(content), 0) + COALESCE(length(tool_calls), 0)) FROM messages WHERE session_id IN (...)
  ```
  This prevents `NULL` values in `tool_calls` or `content` from zeroing out the entire row's contribution.
* **Multi-Session Support:**
  * Refactor `get_latest_hermes_session` and `get_latest_opencode_session` to `get_recent_hermes_sessions` and `get_recent_opencode_sessions` fetching up to 5 recently active sessions.
  * Refactor `get_all_sessions` to combine and return all recent sessions.

#### [MODIFY] [widget.py](file:///home/theworks/teamwork_projects/floating_context_widget/widget.py)
* Update poller loop to consume the list of all recent sessions.
* Sort active sessions by `last_active` descending so the most recently active session is always rendered at the top of the stack.
* Cap the maximum concurrent rendered panels/tiles to **3** to keep the UI clean.

---

## Verification Plan

### Automated Tests
* Run the mock widget integration test suite to verify that the concurrent tracking, session switching, limits lookups, and family calculation logics are fully functional:
  ```bash
  /home/theworks/teamwork_projects/floating_context_widget/verify.py
  ```

### Manual Verification
* Run the widget on the desktop (`export DISPLAY=:0.0 && /home/theworks/teamwork_projects/floating_context_widget/widget.py`) and verify that when subagents are spawned, multiple stacked panels are rendered correctly.
