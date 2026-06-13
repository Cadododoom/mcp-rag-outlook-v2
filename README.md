# Multi-Agent Vector Database RAG Outlook (mcp-rag-outlook)

This repository contains the standalone RAG stack and AST-aware Model Context Protocol (MCP) server designed to expand the codebase search and long-term context memory capabilities for multiple concurrent coding agents.

It works in tandem with the local dual-RTX 5060 Ti vLLM server to enable **16 concurrent agents** to work efficiently within a shared 380K context pool without experiencing Out-Of-Memory (OOM) failures or position embedding (RoPE) degradation.

---

## 3-Tier Context Memory Architecture

To allow any single agent to scale up to the model's native limit of **262K tokens** while running **16 agents concurrently**, the system implements a tiered memory design:

```
  ┌─────────────────────────────────────────────────────────────┐
  │                        AGENT CLIENT                         │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │ (Active Dialog)       │ (Inactive / Idle)     │ (Long-Term Search)
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Tier 1: VRAM    │    │  Tier 2: RAM/SSD │    │  Tier 3: RAG     │
│  PagedAttention  │◄──►│  vLLM KV Cache   │    │  Milvus VectorDB │
│  Prefix Caching  │    │  PCIe Swapping   │    │  AST Chunk Search│
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

1.  **Tier 1: GPU VRAM (Active Attention)**
    *   Uses **PagedAttention** for dynamic memory allocation, preventing fragmentation.
    *   Uses **Prefix Caching** to share common prompts (system rules, workspace directories) in a single VRAM location, drastically cutting prefill costs across concurrent runs.
2.  **Tier 2: Host RAM & SSD (vLLM Swapping)**
    *   When the 380K VRAM limit is hit, vLLM automatically swaps inactive KV caches over the PCIe bus to host CPU RAM (`--swap-space 16` and `--cpu-offload-gb 8`).
    *   Uses high-speed DMA (Direct Memory Access) page-locked memory to execute these transfers in the background during active computation.
3.  **Tier 3: Vector Database (Semantic Code Search)**
    *   Rather than dumping entire source files directly into the active prompt window, static codebase context is indexed semantically into **Milvus**.
    *   The agent calls the **AST-aware Code Indexer MCP** to query the database on demand, fetching only the top relevant code snippets (typically under 10K tokens) into its working context window.

---

## Component Setup & Deployment

### 1. Deploy the Stack (Milvus + Llama.cpp Embedding)
1. Copy your `nomic-embed-text-v1.5.Q8_0.gguf` file to the local `./models/` directory.
2. Ensure you have stopped any conflicting containers, then run:
   ```powershell
   docker compose up -d
   ```
This deploys the complete RAG and embedding infrastructure:
*   **llama-cpp-embedding** (Port `8080`): Isolated embedding server running `llama.cpp`.
*   **milvus-standalone** (Port `19530`): Standalone vector indexing and search database.
*   **milvus-etcd** (Internal Port `2379`): Metadata storage.
*   **milvus-minio** (Ports `9000` / `9001`): Object storage for vectors and indexes.

### 2. Configure the MCP Server Launcher
The folder `mcp_server` contains a pre-configured Node.js launcher wrapper.
1.  Verify the environment settings inside [mcp_server/.env](mcp_server/.env):
    ```env
    EMBEDDING_PROVIDER=OpenAI
    OPENAI_BASE_URL=http://localhost:8080/v1
    OPENAI_API_KEY=llama-cpp
    EMBEDDING_MODEL=nomic-embed-text-v1.5.Q8_0
    MILVUS_ADDRESS=localhost:19530
    ```
2.  Install launcher dependencies:
    ```powershell
    # Run in the mcp_server folder
    cmd.exe /c npm install
    ```
3.  Run or register the launcher (`launch-mcp.js`). The script performs a port check to verify that Milvus is online before starting the AST indexer.

---

## Integration with OpenCode / OpenChamber

We have provided two alternative configuration profiles in the `config/` directory:

1.  **Native 262k Profile** ([config/opencode_rag.json](config/opencode_rag.json)): Uses the full 262K native model context window. Recommended for single-agent deep analysis.
2.  **Virtual Context 22k Profile** ([config/opencode_virtual_ctx.json](config/opencode_virtual_ctx.json)): Caps the physical context window at 22K to support up to 16 concurrent agents in VRAM. Recommended for running high-concurrency workflows alongside our RAG memory loop.

To activate one of the configurations:
1.  Locate your active OpenCode configuration file at:
    `%USERPROFILE%\.config\opencode\opencode.json`
2.  Backup your existing configuration file.
3.  Copy the contents of either `config/opencode_rag.json` or `config/opencode_virtual_ctx.json` to replace it.
4.  Restart your OpenCode server or OpenChamber workspace in VS Code.
