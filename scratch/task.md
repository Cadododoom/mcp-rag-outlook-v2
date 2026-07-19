# Task Checklist — Multi-Agent Context Tracking

- `[x]` Refactor `get_session_family_ids` to traverse parent and child relations bidirectionally (BFS).
- `[x]` Fix the `calculate_hermes_family_conversation_tokens` SQL query to use `COALESCE`.
- `[x]` Refactor `tracker.py` to retrieve up to 5 recently active sessions from Hermes and OpenCode.
- `[x]` Update `widget.py` to draw up to 3 stacked active panels sorted by recency.
- `[x]` Verify mock integration tests in `verify.py` and run manual UI test.
