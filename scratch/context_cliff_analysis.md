# Workstation PC Context Performance Cliff Analysis

We executed a high-resolution performance sweep testing 4 concurrent agents at 5,000 token intervals from **50,000 to 110,000 tokens**. The results expose a distinct performance cliff at the **75,000–80,000 token boundary**.

---

## 📊 Sweep Results Summary Table

| Context Size (Tokens) | Avg Agent TPS | System Aggregate TPS | Avg TTFT (seconds) | Parallelism Factor | Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **50k** | 89.25 | **306.79** | 0.42s | **3.44x** (Parallel) | OK |
| **55k** | 87.31 | **296.50** | 0.45s | **3.40x** (Parallel) | OK |
| **60k** | 84.59 | **282.82** | 0.48s | **3.34x** (Parallel) | OK |
| **65k** | 84.05 | **275.56** | 0.53s | **3.28x** (Parallel) | OK |
| **70k** | 85.33 | **254.08** | 0.95s | **2.98x** (Parallel) | OK |
| **75k** | 83.74 | **246.54** | 0.98s | **2.94x** (Parallel) | OK |
| **80k (CLIFF)** | 59.62 | **50.06** | 0.80s | **0.84x** (Serialized) | OK |
| **85k** | 58.57 | **47.20** | 0.85s | **0.81x** (Serialized) | OK |
| **90k** | 56.37 | **46.64** | 0.97s | **0.83x** (Serialized) | OK |
| **95k** | 55.15 | **40.75** | 0.96s | **0.74x** (Serialized) | OK |
| **100k** | 53.40 | **36.81** | 1.04s | **0.69x** (Serialized) | OK |
| **105k** | 52.28 | **34.74** | 1.08s | **0.66x** (Serialized) | OK |
| **110k** | 49.95 | **32.71** | 1.21s | **0.65x** (Serialized) | OK |

*Note: Parallelism Factor = System TPS / Avg Agent TPS. A factor close to 4.0 indicates full parallel decoding. A factor ≤ 1.0 indicates serial execution.*

---

## 🔍 Key Insights & Technical Characteristics

### 1. The 75k–80k Parallelism Cliff
* **The Symptom:** Between **75k** and **80k** tokens, the individual agent decoding speed drops from 83.74 TPS to 59.62 TPS (a moderate **29% drop**). However, the aggregate System TPS drops from 246.54 to 50.06 (a massive **80% drop**).
* **The Cause (vLLM Serialized Scheduling):** 
  * At 75k tokens, the total KV cache memory required for 4 sequences is $4 \times 75,000 = 300,000$ tokens, which fits comfortably within the **490,933** tokens VRAM KV cache limit.
  * When the context increases to 80k tokens, the vLLM scheduler anticipates that running all 4 sequences concurrently up to their generation limit might exceed the remaining block allocator capacity.
  * To prevent an out-of-memory error, the vLLM engine dynamically **deprioritizes and preempts requests**, swapping to a **serialized scheduling queue** (processing 1 sequence at a time in wall-clock time).
  * Consequently, the System Aggregate TPS collapses to match the throughput of a single sequence (~50 TPS).

### 2. Linear Memory Bandwidth Scaling (Post-Cliff)
* Once the scheduler switches to serial processing at 80k tokens, performance degrades slowly and linearly:
  * 80k: 59.62 TPS
  * 90k: 56.37 TPS
  * 100k: 53.40 TPS
  * 110k: 49.95 TPS
* This linear decay is the direct result of the GPU's memory bandwidth constraint when fetching larger KV cache matrices from VRAM for the single active sequence.

---

## 💡 Recommendations for Workspace Usage

* **Optimal Concurrency Limit:** If running multi-agent tasks where fast responses are critical, capping the RAG proxy limit to **70k tokens** (Option B/C range) allows all 4 agents to decode in parallel, finishing the tasks up to **5x faster** in wall-clock time.
* **Peak Capacity vs. Speed Tradeoff:** Option A (110k tokens proxy limit) remains highly stable and should be used when the codebase size requires a very wide context window. However, users should expect that if all 4 agents hit their context limits concurrently, the system will serialize requests to protect VRAM.
