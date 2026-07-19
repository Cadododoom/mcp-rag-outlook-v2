# Walkthrough — Version 1.0 System Architecture and Verification Release

We have successfully integrated the **Unsloth parameter optimizations** for the Qwen 3.6 35B model variants, the **5-minute decay window** and **active running persistence** features in the virtual context manager widget, updated the architecture documentation to **Version 1.0** in both repositories, verified full operability, and synchronized the updates to GitHub.

---

## 1. Unsloth Model Parameter Optimizations (Version 1.0)

To ensure the best possible inference quality, we implemented a **Dynamic Model Parameter Interceptor** in the authorization proxy server. The proxy intercepts completions requests and always force overwrites the sampling parameters to the optimal Unsloth presets before forwarding to the vLLM backend:

1.  **Thinking/Reasoning Model Variant (`Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4`):**
    *   `temperature`: `0.6` (for precise coding and reasoning)
    *   `top_p`: `0.95`
    *   `top_k`: `20`
    *   `min_p`: `0.0`
    *   `presence_penalty`: `0.0`
    *   `repetition_penalty`: `1.0` (disabled)
2.  **Fast/Non-Thinking Model Variant (`Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4-Fast`):**
    *   `temperature`: `0.7` (optimized instruct settings)
    *   `top_p`: `0.8`
    *   `top_k`: `20`
    *   `min_p`: `0.0`
    *   `presence_penalty`: `1.5`
    *   `repetition_penalty`: `1.0` (disabled)

---

## 2. Active Persistence & Session Decay (Version 1.0)

We resolved a critical edge case where active background subagents would decay and disappear from the widget stack if they ran for more than 5 minutes without writing messages.

*   **Active Persistence:** The database tracker (`tracker.py`) now reads the `ended_at` column from the Hermes `sessions` table. If `ended_at IS NULL` (meaning a subagent or main agent session is still active and running), the tracker dynamically overrides its `last_active` timestamp to the current system time (`time.time()`). This ensures active sessions **never decay** while running.
*   **5-Minute Completed Decay:** Once a session finishes and `ended_at` is set, the decay timer starts ticking from `max(last_active, ended_at)`. After 5 minutes (300 seconds) of completion, it is filtered out of the widget panels, keeping your desktop window clear when subagents are no longer in use.
*   **Widget Process Relaunch:** The running `widget.py` process on your desktop has been automatically located, terminated, and restarted under a background process group to apply these updates immediately.

---

## 3. Published Architecture Documentation (`ARCHITECTURE.md`)

Detailed documentation has been updated to Version 1.0 in:
*   **AI Workstation Backup Repository:** [ARCHITECTURE.md](file:///home/theworks/gdrive_local/AI_Workstation_Backup/ARCHITECTURE.md)
*   **MCP RAG Outlook Repository:** [ARCHITECTURE.md](file:///home/theworks/.gemini/antigravity/scratch/mcp-rag-outlook/ARCHITECTURE.md)

---

## 4. Automated Test Verification

Three verification test suites validate parameter enforcement, decay logic, and container operability:

### Parameter Verification (`verify_parameters.py`)
Mocks completion queries to both model variants (streaming and non-streaming) and asserts parameter routing:
*   **Result:** `Ran 4 tests in 0.066s -> OK`

### Session Decay Verification (`verify_decay.py`)
Mocks running and completed sessions to verify filtering:
*   **Result:** `Filtered active sessions: running_session & completed_active_session (completed_decayed_session filtered out) -> GREEN`

### System Health Verification (`verify_system_v1.py`)
*   **Result:** `🎉 VERIFICATION STATUS: SUCCESS (All Checks Passed!)`

---

## 5. Multi-Repository Synchronization

*   **`AI_Workstation_Backup`:** Committed and pushed dynamic parameters ([commit 64ea3a9](https://github.com/Cadododoom/AI_Workstation_Backup/commit/64ea3a9)).
*   **`mcp-rag-outlook-v2`:** Committed and pushed dynamic parameters ([commit 1461ee1](https://github.com/Cadododoom/mcp-rag-outlook-v2/commit/1461ee1)).
