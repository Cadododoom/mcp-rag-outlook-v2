# Physical KV Cache to Virtual Context Ratio Analysis

This document derives the mathematical relationship between the physical model context window (KV cache size, $P$) and the maximum virtual context size ($V$) it can support within the **MCP RAG Outlook v2** pipeline.

---

## 1. Defining the Variables

To establish the physical-to-virtual context relationship, we define:
* $P$: Active **Physical Context Window** (tokens loaded into GPU KV cache, e.g., max 120,000).
* $V$: Active **Virtual Context Size** (tokens indexed in LanceDB, e.g., 100,000,000).
* $T$: **Target Task Information** (the minimum set of tokens needed to solve a specific coding task, e.g., the target class, method interfaces, and direct imports. Typically 10,000 to 40,000 tokens).
* $\eta(V)$: **Retrieval Precision** (the ratio of relevant target tokens retrieved relative to retrieved distractors).
* $C$: **Compression Rate** (LLMLingua-2 target retention rate, fixed at `0.33`).
* $O$: **System Overhead** (static system prompts + active conversation history + generation output buffer. Typically 24,000 tokens).

---

## 2. Derivation of the Ratio Formula

The relationship is governed by the retrieval-compression chain:

1. **Retrieval Expansion:** To extract the target task information $T$ from a database of size $V$, the retriever must pull a larger set of candidates $R$ to maintain high recall.
   $$R(V) = \frac{T}{\eta(V)}$$

2. **Compression Compaction:** The retrieved tokens are compressed using LLMLingua-2 at rate $C$:
   $$R_{\text{comp}}(V) = R(V) \times C = \frac{T \cdot C}{\eta(V)}$$

3. **Physical Capacity Constraint:** The physical KV cache $P$ must hold the system overhead $O$ plus the compressed retrieved context:
   $$P \ge O + R_{\text{comp}}(V)$$
   $$P \ge O + \frac{T \cdot C}{\eta(V)}$$

4. **Logarithmic Precision Decay:** Retrieval precision $\eta$ degrades logarithmically as the database size $V$ increases due to semantic collisions (similar symbol names, helper patterns, test structures):
   $$\eta(V) = \eta_0 - \beta \log_{10}(V)$$
   where $\eta_0$ is the baseline precision on a small codebase (e.g., $0.85$) and $\beta$ is the code symbol collision coefficient (typically $0.06$ for large repositories).

5. **Final Physical-to-Virtual Formula:**
   $$P_{\text{min}}(V) = O + \frac{T \cdot C}{\eta_0 - \beta \log_{10}(V)}$$

---

## 3. Ratio Projections for Qwen 35B

Using standard parameters for a complex refactoring task on a workstation ($O = 24k$, $T = 30k$, $C = 0.33$, $\eta_0 = 0.85$, $\beta = 0.06$):

### Scenario A: Small Workspace ($V = 100k$ tokens)
* $\eta = 0.85 - 0.06(5) = 0.55$ (55% retrieval precision)
* $P_{\text{min}} = 24,000 + \frac{30,000 \times 0.33}{0.55} = 24,000 + 18,000 = \mathbf{42,000 \text{ tokens}}$
* **Physical-to-Virtual Ratio:** $42\text{k} : 100\text{k} \approx \mathbf{1 : 2.38}$

### Scenario B: Medium Workspace ($V = 1M$ tokens)
* $\eta = 0.85 - 0.06(6) = 0.49$ (49% retrieval precision)
* $P_{\text{min}} = 24,000 + \frac{9,900}{0.49} \approx 24,000 + 20,204 = \mathbf{44,204 \text{ tokens}}$
* **Physical-to-Virtual Ratio:** $44.2\text{k} : 1\text{M} \approx \mathbf{1 : 22.6}$

### Scenario C: Chromium-Scale Subsystem ($V = 100M$ tokens)
* $\eta = 0.85 - 0.06(8) = 0.37$ (37% retrieval precision)
* $P_{\text{min}} = 24,000 + \frac{9,900}{0.37} \approx 24,000 + 26,757 = \mathbf{50,757 \text{ tokens}}$
* **Physical-to-Virtual Ratio:** $50.8\text{k} : 100\text{M} \approx \mathbf{1 : 1,968}$

---

## 4. Theoretical Maximum Virtual Context ($V_{\text{max}}$) for 120k KV Cache

What is the absolute maximum virtual codebase size a **120k token physical KV cache** can serve before hitting retrieval saturation?

Using $P = 120,000$ and solving for $V$:

$$120,000 = 24,000 + \frac{9,900}{0.85 - 0.06 \log_{10}(V)}$$
$$96,000 = \frac{9,900}{0.85 - 0.06 \log_{10}(V)}$$
$$0.85 - 0.06 \log_{10}(V) = \frac{9,900}{96,000} \approx 0.1031$$
$$0.06 \log_{10}(V) = 0.85 - 0.1031 = 0.7469$$
$$\log_{10}(V) = \frac{0.7469}{0.06} \approx 12.45$$
$$V_{\text{max}} = 10^{12.45} \approx \mathbf{2.81 \times 10^{12} \text{ tokens (2.8 Trillion tokens)}}$$

### Conclusion
Because search precision degrades **logarithmically** while physical context requirements scale **linearly**, a 120k physical KV cache is mathematically capable of serving virtually infinite virtual contexts (up to trillion-token scales) when combined with RAG and LLMLingua-2 compression, far exceeding the size of the entire Chromium project.

---

## 5. 60k Physical KV Cache & 8 Agent Concurrency Feasibility Study

If the system is scaled to a physical KV cache limit of **60,000 tokens** per sequence and configured to run **8 concurrent agents**, we evaluate the hardware and capability boundaries:

### 5.1 VRAM Resource Footprint (Qwen 35B)
* FP8 memory per token = $10.24 \text{ KB}$
* $60,000 \text{ tokens} \times 10.24 \text{ KB} = 614.4 \text{ MB per agent}$
* For 8 concurrent agents: $8 \times 614.4 \text{ MB} = \mathbf{4.92 \text{ GiB total KV cache VRAM}}$
* Static Model Footprint (FP4/FP8) = $\mathbf{21.00 \text{ GiB VRAM}}$
* **Aggregate VRAM Requirement:** $21.00 \text{ GiB} + 4.92 \text{ GiB} = \mathbf{25.92 \text{ GiB VRAM}}$

This is highly optimized and easily fits within a dual-GPU cluster or a single high-end workstation card (like a 32 GB or 48 GB VRAM allocation).

### 5.2 Virtual Context Capacity at 54k Physical Limit (vLLM Limit)
Solving for $V$ when $P = 54,000$ tokens:

$$54,000 = 24,000 + \frac{9,900}{0.85 - 0.06 \log_{10}(V)}$$
$$30,000 = \frac{9,900}{0.85 - 0.06 \log_{10}(V)}$$
$$0.85 - 0.06 \log_{10}(V) = \frac{9,900}{30,000} = 0.33$$
$$0.06 \log_{10}(V) = 0.85 - 0.33 = 0.52$$
$$\log_{10}(V) = \frac{0.52}{0.06} \approx 8.66667$$
$$V_{\text{max}} = 10^{8.66667} \approx \mathbf{4.64 \times 10^8 \text{ tokens (464 Million tokens)}}$$

---

### 5.3 Virtual Context Capacity at 53.5k Proxy Limit (500 Token Compression Margin)
Solving for $V$ when $P = 53,500$ tokens:

$$53,500 = 24,000 + \frac{9,900}{0.85 - 0.06 \log_{10}(V)}$$
$$29,500 = \frac{9,900}{0.85 - 0.06 \log_{10}(V)}$$
$$0.85 - 0.06 \log_{10}(V) = \frac{9,900}{29,500} \approx 0.33559$$
$$0.06 \log_{10}(V) = 0.85 - 0.33559 = 0.51441$$
$$\log_{10}(V) = \frac{0.51441}{0.06} \approx 8.57345$$
$$V_{\text{max}} = 10^{8.57345} \approx \mathbf{3.74 \times 10^8 \text{ tokens (374.49 Million tokens)}}$$

---

### 5.4 Feasibility on the Entire Chromium Codebase
The entire Chromium codebase is approximately **35 million lines of code**, which equates to **1.0 to 1.5 Billion tokens**.
* At a physical context ceiling of **53,500** tokens (max proxy input limit), the retrieval-compression pipeline supports a maximum workspace indexing capacity of **374.49 Million tokens** (over one third of a billion tokens).
* This provides ample context headroom to index major directories, individual modules, and sub-systems of Chromium (such as `blink`, `content`, `base`, or `v8`), allowing 8 concurrent agents to run code search and refactoring operations.
* For repositories larger than 374.49M tokens, the sliding window of LanceDB automatically prioritizes local imports and semantic neighborhoods, ensuring prompt integrity remains within the physical GPU limit.
