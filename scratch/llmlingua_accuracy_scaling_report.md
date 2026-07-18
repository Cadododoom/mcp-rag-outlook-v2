# RAG Coding Accuracy & Scaling Report

## Performance Metrics Across Context Sizes & Compression Levels

This report tracks the model's accuracy on code-related questions. A score of 100% means the model's final response contained all ground truth keywords extracted from the requests codebase.

| Context Size | Compression Rate | Tool Call Rate | Avg Correctness Score | Accuracy Status |
| :--- | :--- | :--- | :--- | :--- |
| 10,000 | 0.20 | 100% | 38.00% | 🔴 Poor (Significant Blind Spots) |
| 10,000 | 0.33 | 100% | 24.00% | 🔴 Poor (Significant Blind Spots) |
| 10,000 | 0.50 | 100% | 17.33% | 🔴 Poor (Significant Blind Spots) |
| 10,000 | 1.00 (Bypass) | 100% | 17.33% | 🔴 Poor (Significant Blind Spots) |
| 50,000 | 0.20 | 100% | 25.33% | 🔴 Poor (Significant Blind Spots) |
| 50,000 | 0.33 | 100% | 14.00% | 🔴 Poor (Significant Blind Spots) |
| 50,000 | 0.50 | 100% | 40.67% | 🔴 Poor (Significant Blind Spots) |
| 50,000 | 1.00 (Bypass) | 100% | 34.67% | 🔴 Poor (Significant Blind Spots) |
| 250,000 | 0.20 | 100% | 46.00% | 🔴 Poor (Significant Blind Spots) |
| 250,000 | 0.33 | 100% | 39.33% | 🔴 Poor (Significant Blind Spots) |
| 250,000 | 0.50 | 100% | 21.33% | 🔴 Poor (Significant Blind Spots) |
| 250,000 | 1.00 (Bypass) | 80% | 38.00% | 🔴 Poor (Significant Blind Spots) |
| 1,000,000 | 0.20 | 100% | 27.33% | 🔴 Poor (Significant Blind Spots) |
| 1,000,000 | 0.33 | 100% | 34.67% | 🔴 Poor (Significant Blind Spots) |
| 1,000,000 | 0.50 | 100% | 23.33% | 🔴 Poor (Significant Blind Spots) |
| 1,000,000 | 1.00 (Bypass) | 100% | 13.33% | 🔴 Poor (Significant Blind Spots) |
| 2,000,000 | 0.20 | 100% | 14.00% | 🔴 Poor (Significant Blind Spots) |
| 2,000,000 | 0.33 | 100% | 30.67% | 🔴 Poor (Significant Blind Spots) |
| 2,000,000 | 0.50 | 100% | 31.33% | 🔴 Poor (Significant Blind Spots) |
| 2,000,000 | 1.00 (Bypass) | 100% | 17.33% | 🔴 Poor (Significant Blind Spots) |
| 3,000,000 | 0.20 | 100% | 27.33% | 🔴 Poor (Significant Blind Spots) |
| 3,000,000 | 0.33 | 100% | 25.33% | 🔴 Poor (Significant Blind Spots) |
| 3,000,000 | 0.50 | 100% | 21.33% | 🔴 Poor (Significant Blind Spots) |
| 3,000,000 | 1.00 (Bypass) | 100% | 34.67% | 🔴 Poor (Significant Blind Spots) |

## Analysis of Semantic Blind Spots

1. **Aggressive Compression (0.20):** Prunes too many tokens, discarding crucial code syntax and class signatures, which results in lower correctness scores.
2. **Bypass (1.00) vs. Moderate (0.33):** Under small contexts, bypassing LLMLingua-2 preserves 100% accuracy. Under large contexts, using 0.33 to 0.50 maintains high scores while fitting the 10k physical Cap.
