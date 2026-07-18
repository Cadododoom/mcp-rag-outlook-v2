# Context Capping and Hallucination Metric Report

| Context Size (Tokens) | Evaluation Mode | Was Truncated? | Tool Called? | Correct Answer? | Hallucinated? | Latency (sec) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 10,000 | naive | Yes | Yes | Yes | No | 2.14 |
| 10,000 | truncation-aware | Yes | Yes | Yes | No | 2.29 |
| 50,000 | naive | Yes | Yes | Yes | No | 2.11 |
| 50,000 | truncation-aware | Yes | Yes | Yes | No | 2.15 |
| 250,000 | naive | Yes | Yes | Yes | No | 3.83 |
| 250,000 | truncation-aware | Yes | Yes | Yes | No | 1.98 |
| 1,000,000 | naive | Yes | Yes | Yes | No | 3.84 |
| 1,000,000 | truncation-aware | Yes | Yes | Yes | No | 1.94 |
| 5,000,000 | naive | Yes | Yes | Yes | No | 3.95 |
| 5,000,000 | truncation-aware | Yes | Yes | Yes | No | 2.17 |
| 10,000,000 | naive | Yes | Yes | Yes | No | 3.94 |
| 10,000,000 | truncation-aware | Yes | Yes | Yes | No | 1.92 |
