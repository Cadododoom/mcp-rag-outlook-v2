# Walkthrough — Option A Calibration, vLLM Benchmark & RAG Verification

We have successfully re-calibrated the workstation PC to **Option A** parameters (4-agent concurrency, 112k max model length in vLLM, 110k proxy limit), validated performance through sustained benchmarking, verified the end-to-end RAG pipeline, and synchronized all changes to the remote repositories.

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

## 2. vLLM Performance Benchmark (4 Agents, 110k Context)

We executed a 60-second sustained concurrency test with 4 agents feeding 110,000-token contexts into the restarted container:

* **Sustained Load:** 4 parallel requests of 110k context blocks (approx. 440k characters per agent).
* **Cache Behavior:** Subsequent requests hit prefix caching successfully, reducing TTFT from **26.61s** (initial prefill) to **0.5s - 2.1s**.
* **Aggregate Performance Results:**
  * **Concurrent Agents:** 4
  * **Total Requests Completed:** 86
  * **Average TTFT (Prefill):** 2.02 seconds
  * **Average Agent TPS:** **`19.47 tokens/second`**
  * **System Aggregate TPS:** **`21.41 tokens/second`**
  * **Stability:** 100% stable with **zero OOM errors** or thread stalls under peak 110k sequence limits.

---

## 3. RAG Pipeline Verification

We wrote and executed a RAG validation test script [verify_rag.py](file:///home/theworks/.gemini/antigravity/brain/f2710fb0-8a15-4a45-b606-66e0aefc75b8/scratch/verify_rag.py):
* **Embedding Registration:** Handled the custom `nomic-vulkan` embedding registry configuration in Python dynamically to map the embedding requests to the local `llama-server` running on port `8080`.
* **Search Execution:** Successfully connected to the LanceDB database at `/home/theworks/.gemini/antigravity/scratch/mcp-rag-outlook/data/lancedb_store` and retrieved candidate code blocks from the table `raptor_collapsed_index`.
* **Reranking & Compression:** Ran the BGE reranker and the CPU-optimized INT8 ONNX cross-encoder to re-score matches, followed by LLMLingua-2 context compression at **`0.33`** retention rate.
* **Results:**
  ```text
  [+] Loading RAG engine...
  [+] Running execute_tool for query: 'How is connection retrying configured and handled in HTTPAdapter?'
  === RAG Execution Results ===
  [+] Success!
  Compressed Payload Length: 15123 characters
  Snippet:
  search_document: File: requests/adapters.py (Lines 161-190)
  ```

---

## 4. Multi-Repository Synchronization

All updated files were committed and pushed to remote origins:
* **`AI_Workstation_Backup`:** Pushed configuration changes and docker compose overrides to main branch ([commit b6ee255](https://github.com/Cadododoom/AI_Workstation_Backup/commit/b6ee255)).
* **`mcp-rag-outlook-v2`:** Synchronized analysis reports and walkthroughs to main branch ([commit bc75f6b](https://github.com/Cadododoom/mcp-rag-outlook-v2/commit/bc75f6b)).
