# Context Capping and Hallucination Metric Report

| Context Size (Tokens) | Evaluation Mode | Was Truncated? | Tool Called? | Correct Answer? | Hallucinated? | Latency (sec) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 10,000 | naive | Yes | Yes | Yes | No | 3.90 |
| 10,000 | truncation-aware | Yes | Yes | Yes | No | 1.66 |
| 50,000 | naive | Yes | Yes | Yes | No | 3.62 |
| 50,000 | truncation-aware | Yes | Yes | Yes | No | 1.44 |
| 250,000 | naive | Yes | Yes | Yes | No | 3.41 |
| 250,000 | truncation-aware | Yes | Yes | Yes | No | 1.48 |
| 1,000,000 | naive | Yes | Yes | Yes | No | 3.42 |
| 1,000,000 | truncation-aware | Yes | Yes | Yes | No | 1.69 |
| 5,000,000 | naive | Yes | Yes | Yes | No | 3.63 |
| 5,000,000 | truncation-aware | Yes | Yes | Yes | No | 1.50 |
| 10,000,000 | naive | Yes | Yes | Yes | No | 4.11 |
| 10,000,000 | truncation-aware | Yes | Yes | Yes | No | 1.53 |
