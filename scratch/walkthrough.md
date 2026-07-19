# Walkthrough — Option A Calibration, vLLM Benchmark & RAG Toggle

We have successfully re-calibrated the workstation PC to **Option A** parameters, validated performance characteristics under different loads, built a dynamic context size toggle in the desktop widget, and pushed all updates to the remote repositories.

---

## 1. Option A Calibration (112k/110k/4-Agent)

We have updated the context parameters across all active configuration and backup files:

1. **vLLM Engine Config (`docker-compose.yml`):**
   * Changed `--max-model-len` to **`112,000`** tokens.
   * Changed `--max-num-seqs` to **`4`** concurrent sequences (matching CUDA graph limits).
2. **Auth-Proxy Config (`docker-compose.yml`):**
   * Configured `MAX_CONTEXT_TOKENS` to **`110,000`** tokens.
   * Configured `MAX_MODEL_LEN` to **`112,000`** tokens.
3. **Active and Backup Configurations:**
   * Updated `physical_context_length` to **`110,000`** in `config.yaml` at `/home/theworks/.hermes/config.yaml`, `/home/theworks/gdrive_local/AI_Workstation_Backup/host_configs/hermes_config.yaml`, and `/home/theworks/gdrive_local/AI_Workstation_Backup/hermes_swarm_data/.hermes-shared/config.yaml`.
   * Updated `opencode.json` at `/home/theworks/.config/opencode/opencode.json` and `/home/theworks/gdrive_local/AI_Workstation_Backup/host_configs/opencode.json`.
4. **Virtual Context Recalculation:**
   * Solved the logarithmic retrieval precision decay formula for $P = 110,000$ tokens:
     $$110,000 = 24,000 + \frac{9,900}{0.85 - 0.06 \log_{10}(V)}$$
     $$V_{\text{max}} = 10^{12.248067} \approx \mathbf{1,770,390,929,483 \text{ tokens (1.77 Trillion tokens)}}$$
   * Configured the virtual context limit to **`1,770,390,929,483`** across all active and backup config files.

---

## 2. RAG Pipeline Context Limit Toggle

We have implemented a dynamic toggle in the virtual context manager that allows you to switch between a high-speed parallel mode and a maximum-capacity codebase mode:

1. **UI Toggle Control ([widget.py](file:///home/theworks/teamwork_projects/floating_context_widget/widget.py)):**
   * Added a styled toggle button inside the header of the desktop overlay widget.
   * Mapped to the Catppuccin Mocha theme, changing dynamically from **Green (`#a6e3a1`) for Fast (75k)** mode to **Mauve (`#cba6f7`) for Huge (110k)** mode.
2. **Configuration Sync Engine:**
   * When clicked, the toggle dynamically updates `physical_context_length` and `context_length` in the active and backup configurations (three YAML configs and two JSON configs) and instantly redraws the Tkinter UI.
3. **Dynamic RAG Proxy Resolution ([proxy.py](file:///home/theworks/gdrive_local/AI_Workstation_Backup/vllm_sglang/proxy.py)):**
   * Refactored the proxy to read the context limit from the active `config.yaml` (`/opt/data/config.yaml`) dynamically on every completion request.
   * Mounted `/home/theworks/.hermes` as a read-only volume in the proxy container.

---

## 3. Performance & Verification Tests

### Concurrency Performance Sweep (4 Agents)
We tested 4 concurrent agents at 5k token intervals:
* **Fast Mode (50k–75k):** Parallel decoding was fully active. At 50k context, aggregate throughput reached **306.79 TPS** (89.25 TPS per agent) with a **0.42s TTFT** (prefix cache hit).
* **Huge Mode (80k–110k):** The scheduler switched to serial queueing to prevent VRAM OOMs, running 1 agent at a time. Throughput scaled linearly down to **32.71 TPS** (aggregate) at 110k tokens.

### Automated Toggle Verification ([verify_toggle.py](file:///home/theworks/teamwork_projects/rag_context_toggle/verify_toggle.py))
An automated test script was created to verify the toggle:
* Updates configs programmatically.
* Runs `docker exec` in the running proxy container to verify the dynamic resolution works instantly.
* Queries the completions HTTP endpoint directly to ensure correct proxy forwarding.
* **Result:** `🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉`

---

## 4. Multi-Repository Synchronization

* **`AI_Workstation_Backup`:** Committed and pushed proxy changes and compose updates ([commit 6779485](https://github.com/Cadododoom/AI_Workstation_Backup/commit/6779485)).
* **`mcp-rag-outlook-v2`:** Synchronized analysis reports, implementation records, and walkthroughs ([commit 1df2fad](https://github.com/Cadododoom/mcp-rag-outlook-v2/commit/1df2fad)).
