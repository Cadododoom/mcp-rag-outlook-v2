# Context Capping and Hallucination Metric Report

| Context Size (Tokens) | Evaluation Mode | Was Truncated? | Tool Called? | Correct Answer? | Hallucinated? | Latency (sec) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 10,000 | naive | Yes | Yes | Yes | No | 4.94 |
| 10,000 | truncation-aware | Yes | Yes | Yes | No | 4.78 |
| 50,000 | naive | Yes | Yes | Yes | No | 4.72 |
| 50,000 | truncation-aware | Yes | Yes | Yes | No | 5.28 |
| 250,000 | naive | Yes | Yes | Yes | No | 4.64 |
| 250,000 | truncation-aware | Yes | Yes | Yes | No | 4.96 |
| 1,000,000 | naive | Yes | Yes | Yes | No | 5.64 |
| 1,000,000 | truncation-aware | Yes | Yes | Yes | No | 4.68 |
