# LLMLingua-2 CPU Core Scaling Benchmark Report

## Thread Configuration vs. Latency and CPU Overhead

The following table summarizes the performance-to-overhead tradeoff for prompt compression on CPU:

| CPU Threads | Avg Latency (ms) | Min Latency (ms) | Avg System CPU (%) | Max System CPU (%) | Relative Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 82544.0 | 82005.7 | 5.1% | 100.0% | 1.00x |
| 2 | 43643.1 | 43559.8 | 6.7% | 21.4% | 1.89x |
| 4 | 30320.6 | 30187.2 | 8.9% | 24.4% | 2.72x |
| 6 | 17657.6 | 17467.6 | 13.3% | 100.0% | 4.67x |
| 8 | 14714.2 | 14684.2 | 13.9% | 28.0% | 5.61x |
| 12 | 11422.3 | 11212.5 | 20.0% | 40.6% | 7.23x |
| 16 | 11155.6 | 10190.7 | 26.8% | 52.7% | 7.40x |
| 24 | 10834.1 | 10528.5 | 33.9% | 58.7% | 7.62x |
| 32 | 9869.3 | 9584.5 | 42.7% | 69.3% | 8.36x |

## Architectural Recommendation

Based on the core-time cost metric (Threads * Latency), the mathematically optimal allocation is **1 threads**.
This configuration achieves an ideal balance between low latency and low CPU utilization, preventing CPU starvation for concurrent agent runtimes.
