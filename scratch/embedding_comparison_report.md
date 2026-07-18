# Embedding Engine Performance Comparison Report

This report presents the performance evaluation and comparative metrics between the CPU-bound **BGE-small-en-v1.5** model and the GPU-accelerated **Nomic-embed-text-v1.5** model running natively on the **Vulkan** compute backend of the **AMD Radeon RX 5700** (Device 1).

## Benchmark Configuration

- **Dataset:** 256 codebase chunks from the `requests` repository (truncated to max sequence length of 512 tokens).
- **CPU Backend:** BGE-small-en-v1.5 running locally on the AMD EPYC host (restricted to 4 active OpenMP threads to avoid core thrashing).
- **Vulkan GPU Backend:** Nomic-embed-text-v1.5 running on `llama-server` Vulkan instance with batch/ubatch configurations set to 2048 and prompt disk caching disabled.

---

## Performance Summary Table

| Engine & Scenario | Avg Req Latency (ms) | P95 Req Latency (ms) | Avg Chunk Latency (ms) | Throughput (tok/s) | CPU Avg/Peak | GPU1 (RX 5700) Avg Util |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BGE CPU (Sequential)** | 74.55 ms | 74.55 ms | 74.55 ms | 4,059.62 tok/s | 11.2% / 19.1% | 0.0% |
| **BGE CPU (Batch 8)** | 626.58 ms | 626.58 ms | 78.32 ms | 3,863.87 tok/s | 11.4% / 18.1% | 0.0% |
| **BGE CPU (Batch 32)** | 3,107.84 ms | 3,107.84 ms | 97.12 ms | 3,116.03 tok/s | 10.2% / 20.3% | 0.0% |
| **BGE CPU (Batch 128)** | 17,090.26 ms | 17,090.26 ms | 133.52 ms | 2,266.58 tok/s | 9.8% / 22.9% | 0.0% |
| **Nomic Vulkan (Sequential)** | **24.92 ms** | **33.10 ms** | **24.92 ms** | **12,060.74 tok/s** | 3.5% / 4.5% | 85.9% |
| **Nomic Vulkan (Batch 8)** | **160.98 ms** | **241.29 ms** | **20.12 ms** | **14,939.04 tok/s** | 4.1% / 7.1% | 91.1% |
| **Nomic Vulkan (Batch 32)** | **609.13 ms** | **656.46 ms** | **19.04 ms** | **15,793.03 tok/s** | 6.1% / 11.7% | 88.9% |
| **Nomic Vulkan (Batch 128)** | **2,395.01 ms** | **2,405.28 ms** | **18.71 ms** | **16,066.93 tok/s** | 3.5% / 4.9% | 84.1% |

---

## Key Performance Insights

### 1. Latency Reduction
- **Sequential Requests:** Nomic on Vulkan achieves a query response latency of **`24.92 ms`** per chunk compared to BGE CPU's **`74.55 ms`** — a **3x sequential speedup**.
- **Large Batch Latency:** At batch size 128, BGE CPU's request latency spikes to **`17,090 ms`** (17 seconds) due to CPU cache misses and memory synchronization overhead. Under the same load, Nomic Vulkan processes the batch in only **`2,395 ms`** (2.39 seconds) — a **7.1x latency reduction**.

### 2. Throughput & Scaling
- **CPU Scaling Bottleneck:** BGE CPU throughput drops by **44%** (from `4,059` down to `2,266 tok/s`) as the batch size scales from 1 to 128. This is a common bottleneck of matrix multiplications on shared CPU memory buses.
- **GPU Scaling Efficiency:** Nomic Vulkan throughput increases by **33%** (from `12,060` up to `16,066 tok/s`) as batch size increases, showing high compute density scaling on the RX 5700 shader cores.
- **Max Throughput Gain:** Under a batch load of 128, Nomic Vulkan achieves a throughput of **`16,066.93 tok/s`** compared to BGE CPU's **`2,266.58 tok/s`**, representing a **7.1x throughput speedup**.

### 3. Resource Utilization & CPU Offloading
- Running embeddings on CPU pins 4 threads to 100% (averaging 11.2% of the massive 56-core EPYC processor), which introduces thermal load and cache pollution for the host.
- Running embeddings on Vulkan uses only **3.5% CPU** (pure driver dispatch overhead) while offloading **84% - 91%** of the math to the RX 5700 GPU, leaving the EPYC CPU completely free for other agent workflows and tool operations.

---
> [!TIP]
> **Conclusion:** Migrating the memory and codebase embedding workflows to the **Vulkan Nomic** backend is highly recommended. It yields a **3x latency reduction for sequential memory queries**, a **7x throughput boost for batch codebase ingestions**, and completely frees the host CPU from heavy tensor workloads.
