# Version 1.0 System Architecture and Configuration Documentation
## AI Workstation Backup Repository

This document details the system architecture, component configurations, retrieval-augmented generation (RAG) pipeline, and performance characteristics of the Multi-Agent RAG system calibrated for the AI Workstation stack, as well as the backup layout and operational management.

---

## 1. System Topology & Data Flow Diagrams

The following diagrams illustrate the end-to-end data flows and network routing between the workstation clients, the desktop context manager widget, the authentication gateway proxy, and the backend model serving engine.

### Sequence Diagram: Client Request Interception & Prompt Compression

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client IDE / Agent<br/>(OpenCode / Hermes)
    participant Proxy as vLLM Auth Gateway Proxy<br/>(Port 30000)
    participant HostFS as Host Filesystem<br/>(config.yaml)
    participant vLLM as vLLM Model Server<br/>(Port 29999 / 30000)
    participant RAG as LanceDB & RAG Skill<br/>(query_edge_rag.py)

    Client->>Proxy: POST /v1/chat/completions (with payload)
    activate Proxy
    Proxy->>HostFS: Read config limit from /opt/data/config.yaml
    HostFS-->>Proxy: Return physical_context_length (75k or 110k)
    
    alt Payload size > physical_context_length
        Proxy->>Proxy: Truncate messages (preserve system & first user query)
        Proxy->>Proxy: Inject [SYSTEM WARNING] advising model to call RAG tools
    end

    Proxy->>vllm: Forward adjusted payload
    activate vLLM
    
    alt Model decides to query codebase or memory
        vLLM->>RAG: Call query_edge_rag / retrieve_chat_memory
        activate RAG
        RAG->>RAG: Query LanceDB (raptor_collapsed_index / agent_memories)
        RAG->>RAG: Rerank via CPU ONNX Cross-Encoder (bge-reranker-v2-m3)
        RAG->>RAG: Compress via CPU LLMLingua-2 (extractive BERT)
        RAG-->>vLLM: Return compressed retrieved context
        deactivate RAG
    end
    
    vLLM-->>Proxy: Return completion response / stream chunks
    deactivate vLLM
    Proxy-->>Client: Return final response with reconstructed <think> blocks
    deactivate Proxy
```

### Component Interaction: Desktop Context Manager Widget

```mermaid
flowchart TD
    subgraph UI [Desktop Layer]
        widget[Virtual Context Manager Widget<br/>Tkinter Desktop Overlay]
    end

    subgraph Configs [Active & Backup Configs]
        c1["/home/theworks/.hermes/config.yaml<br/>(Active Hermes)"]
        c2["/home/theworks/gdrive_local/AI_Workstation_Backup/host_configs/hermes_config.yaml<br/>(Backup Hermes)"]
        c3["/home/theworks/gdrive_local/AI_Workstation_Backup/hermes_swarm_data/.hermes-shared/config.yaml<br/>(Backup Swarm)"]
        c4["/home/theworks/.config/opencode/opencode.json<br/>(Active OpenCode)"]
        c5["/home/theworks/gdrive_local/AI_Workstation_Backup/host_configs/opencode.json<br/>(Backup OpenCode)"]
    end

    subgraph ProxyService [vLLM Serving Container Stack]
        proxy["vLLM Auth Gateway Proxy<br/>Container: SGlang_5060ti_Proxy"]
    end

    subgraph State [Application State Databases]
        db1["/home/theworks/.hermes/state.db<br/>(SQLite database)"]
        db2["/home/theworks/.local/share/opencode/opencode.db<br/>(SQLite database)"]
    end

    %% Interactions
    widget -->|1. Poll active sessions & token counts| db1 & db2
    widget -->|2. Toggle clicked: Update limits| c1 & c2 & c3 & c4 & c5
    c1 -->|3. Mounted Volume Mapping<br/>/home/theworks/.hermes -> /opt/data:ro| proxy
    proxy -->|4. Parse dynamically on request| proxy
```

---

## 2. Core Components and Parameters

### 2.1 vLLM Engine Configuration (Option A)
The model server is calibrated under **Option A** to maximize physical execution length while avoiding out-of-memory (OOM) states under GPU parallel workloads.

*   **Served Model:** `nvidia/Qwen3.6-35B-A3B-NVFP4` (hybrid MoE model post-training quantized to 4-bit).
*   **Tensor Parallel Size:** `--tensor-parallel-size 2` (sharded across dual RTX 5060 Ti GPUs).
*   **KV Cache Precision:** `--kv-cache-dtype fp8` (reduces memory consumption per token by 50%).
*   **Max Model Len:** `--max-model-len 112000` (physical ceiling of 112,000 tokens).
*   **Max Num Seqs:** `--max-num-seqs 4` (concurrency constraint limiting active decoding to 4 sequences).
*   **GPU Memory Utilization:** `--gpu-memory-utilization 0.97` (allows full allocation of VRAM).
*   **Attention Backend:** `--attention-backend flashinfer`.
*   **Prefix Caching:** `--enable-prefix-caching` (caches system instructions, tools, and preceding turns).
*   **Prefill Strategy:** `--enable-chunked-prefill` (chunked token processing preventing latency spikes).

### 2.2 vLLM Auth Gateway Proxy
The proxy acts as a reverse proxy on host port `30000`, intercepting completion requests to secure the endpoint and dynamically manage context lengths.

*   **Auth Token Security:** Validates requests using the `Authorization: Bearer <token>` header (bypass granted for local private IPs).
*   **Dynamic Limits:** Reads the `/opt/data/config.yaml` file dynamically on every request. This file parses `physical_context_length` from the active Hermes config.
*   **Context Slicing:** When the incoming payload exceeds the limit, the proxy truncates older messages but preserves critical system instructions, tools, and the very first user query.
*   **Truncation Alert Injection:** Injecting the following warning in the last user message to instruct the model to trigger RAG instead of hallucinating:
    > `[SYSTEM WARNING]: The older conversation history has been truncated from your active memory to maintain performance. If you require details regarding previous code milestones, authentication tokens, database connection credentials, or architectural design decisions that are not visible in the recent messages above, you MUST call the 'retrieve_chat_memory' tool to search the database. Do not attempt to guess or invent these details.`
*   **Reasoning Reassembly:** Re-constructs reasoning tokens in `<think>...</think>` tags for clients that do not support raw reasoning field streaming.
*   **Dynamic Model Parameter Calibration (Version 1.0):** Intercepts completions requests to enforce calibrated model parameters optimized per Unsloth's official specifications for thinking/reasoning and fast/non-thinking variants:
    | Parameter | Thinking Model (`Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4`) | Fast Model (`Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4-Fast`) | Calibration Rationale / Source |
    | :--- | :--- | :--- | :--- |
    | `temperature` | `0.6` | `0.7` | Optimal reasoning vs speed scaling (Unsloth specifications). Lower temperature focuses the search path for deep thinking. |
    | `top_p` | `0.95` | `0.8` | High top-p retains alternative thinking paths; lower top-p for fast mode improves execution speed and coherence. |
    | `top_k` | `20` | `20` | Constrains the search space to the top 20 tokens to eliminate long-tail hallucinations. |
    | `min_p` | `0.0` | `0.0` | Disabled in favor of strict top-p/top-k filtering. |
    | `presence_penalty` | `0.0` | `1.5` | 0.0 for natural thinking flow; 1.5 in fast mode to penalize repetition and force direct concise output. |
    | `repetition_penalty` | `1.0` | `1.0` | Neutral scaling to prevent synthetic degradation of reasoning patterns. |

### 2.3 Virtual Context Manager Widget
A frameless desktop overlay widget implemented in python (Tkinter) that provides real-time tracking and control over the workstation's context state.

*   **Session Polling:** Runs a background thread polling active session token counts from the SQLite databases of Hermes (`~/.hermes/state.db`) and OpenCode (`~/.local/share/opencode/opencode.db`).
*   **Visual Status:** Displays active panels representing current conversations, tracking physical context usage (with color-coded limits) and virtual RAG context size.
*   **Fast/Huge Toggle Button:** A styled button mapped to the Catppuccin Mocha theme (Green `#a6e3a1` for Fast, Mauve `#cba6f7` for Huge) that updates configurations on click.
*   **Configuration Sync:** On click, the widget programmatically writes limits to three YAML configurations (Hermes active, Hermes backup, Swarm shared backup) and two JSON configurations (OpenCode active, OpenCode backup).
*   **Decay & Active Session Persistence (Version 1.0):** Retains running/unfinished sessions (where `ended_at IS NULL` in the database) persistently active on the overlay panel regardless of age. Completed sessions (where `ended_at` is set) are subject to a 5-minute (300 seconds) decay window from the session's completion or last activity time, after which they are automatically filtered out to prevent clutter.

---

## 3. RAG Pipeline & Mathematical Limits

### 3.1 Pipeline Mechanics
Retrieval-Augmented Generation processes retrieved codebase and memory data via a tiered system:

1.  **LanceDB Vector Database:** In-process columnar database storing Arrow records. Flat L2 index search is utilized to prevent recall degradation on local code repos. BGE instruction prefixing is applied to queries.
2.  **CPU ONNX Cross-Encoder Reranker:** Reranks candidate chunks using `BAAI/bge-reranker-v2-m3` compiled to INT8 ONNX, capped to `ORT_SEQUENTIAL` with 2 execution threads to avoid CPU thrashing.
3.  **AST-Guided Code Compactor:** Parses Python code into AST trees, replacing function and class method bodies with `pass` statements, and C++/Java function bodies with `{ /* bypassed */ }` signatures. This extracts structural skeletons while reducing token footprints by up to 80%.
4.  **Extractive Prompt Compressor:** For remaining contexts, `LLMLingua-2` (BERT-based meetingbank compressor) compresses prompts down to the target budget (compression rate `0.33` to `0.50`), while bypassing compression for payloads under 2500 tokens.

### 3.2 Logarithmic Virtual Context Math
The relationship between the physical VRAM context ceiling ($P$) and the virtual codebase context limit ($V$) is defined by a logarithmic retrieval decay formula:

$$P = 24,000 + \frac{9,900}{0.85 - 0.06 \log_{10}(V)}$$

This formula calculates how much virtual database context ($V$) can be effectively indexed without causing recall degradation beyond prompt window capabilities. Solving for the two limits:

*   **Fast Mode ($P = 75,000$ tokens):**
    $$V_{\text{fast}} = 10^{10.58} \approx \mathbf{37,992,307,469 \text{ tokens (38 Billion)}} $$
*   **Huge Mode ($P = 110,000$ tokens):**
    $$V_{\text{huge}} = 10^{12.248} \approx \mathbf{1,770,390,929,483 \text{ tokens (1.77 Trillion)}} $$

---

## 4. Performance & Scheduling Cache Cliff Analysis

### The 75k Performance Cliff
During concurrency testing of 4 parallel agent workloads at different token limits, a severe performance cliff was observed at **75,000 tokens**:

```
Throughput (TPS)
  ▲
  │   ┌──────────────────┐  <- 306.79 TPS (Parallel prefill & decode active)
  │   │                  │
  │   │   Parallel Mode  │
  │   │    (50k - 75k)   │
  │   │                  │
  ├─ ─┴─ ─ ─ ─ ─ ─ ─ ─ ─ ┼ ─ ─ ─ ─ ─ ─ ─ ─ ┐   <- 75k Scheduling Cliff
  │                                        │
  │                                        │   Serial Queueing Mode (80k - 110k)
  │                                        │   (Only 1 agent served at a time)
  │                                        │
  │                                        └──────────► 32.71 TPS (At 110k)
  └──────────────────────────────────────────────────► Context size
```

*   **Under 75,000 Tokens:** The dual RTX 5060 Ti GPUs have sufficient physical KV Cache page allocations to support parallel decoding of 4 concurrent sequences. prefix caching hit rates are high, yielding **306.79 TPS** aggregate and **0.42s TTFT**.
*   **Over 75,000 Tokens (The Cliff):** The combined VRAM requirements of the KV Cache and model weights exceed physical VRAM under parallel execution. To prevent OOMs, the vLLM scheduler falls back to serial queueing (serving only 1 agent sequence at a time while preempting others). This drops aggregate throughput down to **32.71 TPS** (linear degradation due to serialization overhead).
*   **Recommendation:** Use **Fast Mode (75k)** for interactive multi-agent chat sessions, and switch to **Huge Mode (110k)** only for deep codebase analysis tasks.

---

## 5. Workstation Repository Layout & Backup Specifics

### 5.1 Repository Directory Layout
This repository serves as the central orchestration and backup repository for the AI Workstation. The structure is organized as follows:

*   **`host_configs/`**: Backup store containing core host configuration files like `hermes_config.yaml` and `opencode.json` to ensure fast disaster recovery restoration.
*   **`vllm_sglang/`**: Custom proxy server code (`proxy.py`), benchmark scripts (`benchmark.py`), and model implementation overrides (e.g., `qwen3_5.py`, `registry.py`) mounted directly into the vLLM container.
*   **`repositories/`**: Houses key git submodules and secondary codebases (e.g. `local-high-efficiency-rag` and `hermes-swarm`).
*   **`hermes_swarm_data/`**: Persistent data store for swarm agent operations.
*   **`archives/`**: Work directory containing compiled backup archives (`.tar.gz`) before being pushed to the cloud.

### 5.2 Backup Sync Mechanics
To ensure persistence of the local state without interfering with live database operations:

1.  **Non-Blocking SQLite Hot Backups:** The cron/scheduler invokes `backup.sh`. The script initiates hot backups using the SQLite `.backup` command:
    ```bash
    sqlite3 ~/.hermes/state.db ".backup '/tmp/databases/state.db'"
    sqlite3 ~/.hermes/agent-teams-data/monitoring.db ".backup '/tmp/databases/monitoring.db'"
    ```
    This eliminates file locking issues during active agent chats.
2.  **LanceDB & Folder Rsync:** In-process vector database stores are safely synced using `rsync -a --inplace` to a staging area.
3.  **Tarball Packaging:** Staged databases, configuration directories, and workspaces are packaged into compressed archives (`databases.tar.gz`, `configs.tar.gz`, `hermes_data.tar.gz`, `workspace.tar.gz`, `deployment.tar.gz`).
4.  **rclone Cloud Syncing:** Uploads the generated archives to Google Drive (`google_drive:AI_Workstation_Backup/archives/`) or a mounted local Google Drive folder.
5.  **Git Remote Synchronization:** Automated git commits and pushes are run regularly to keep the backup repositories synchronized with GitHub.

### 5.3 Service Management Instructions
The workstation services are managed using Docker Compose from the root of this repository.

*   **Start the full stack:**
    ```bash
    docker compose up -d
    ```
*   **Stop the full stack:**
    ```bash
    docker compose down
    ```
*   **Restart a specific service (e.g., the proxy after code updates):**
    ```bash
    docker compose restart vllm-auth-proxy
    ```
*   **Check container status:**
    ```bash
    docker compose ps
    ```
*   **View live system logs:**
    ```bash
    docker compose logs -f
    ```
