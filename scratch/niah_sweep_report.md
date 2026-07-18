# Needle-in-a-Haystack (NIAH) Hardware Context Sweep Report

## Setup & Configuration
- **Model Under Test:** `Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4`
- **Target Context Range:** 10,000 to 120,000 tokens (10k increments)
- **Insertion Depths:** 10% (Beginning), 50% (Middle), 90% (End)
- **Evaluation Needle:** `containment-auth-key-8899-alpha`

## Recall Accuracy Matrix

| Context Size (Tokens) | Depth: 10% (Beginning) | Depth: 50% (Middle) | Depth: 90% (End) |
| :--- | :--- | :--- | :--- |
| 10,000 | 🟢 Pass (1.9s) | 🟢 Pass (1.9s) | 🟢 Pass (1.9s) |
| 20,000 | 🟢 Pass (3.2s) | 🟢 Pass (3.2s) | 🟢 Pass (3.3s) |
| 30,000 | 🟢 Pass (5.0s) | 🟢 Pass (5.2s) | 🟢 Pass (4.9s) |
| 40,000 | 🟢 Pass (6.5s) | 🟢 Pass (6.6s) | 🟢 Pass (6.3s) |
| 50,000 | 🟢 Pass (7.9s) | 🟢 Pass (8.0s) | 🟢 Pass (8.1s) |
| 60,000 | 🟢 Pass (9.9s) | 🟢 Pass (10.0s) | 🟢 Pass (11.3s) |
| 70,000 | 🟢 Pass (15.8s) | 🟢 Pass (15.9s) | 🟢 Pass (13.6s) |
| 80,000 | 🟢 Pass (17.2s) | 🟢 Pass (15.8s) | 🟢 Pass (14.2s) |
| 90,000 | 🟢 Pass (16.1s) | 🟢 Pass (16.1s) | 🟢 Pass (16.1s) |
| 100,000 | 🟢 Pass (18.3s) | 🟢 Pass (19.8s) | 🟢 Pass (20.0s) |
| 110,000 | 🟢 Pass (21.6s) | 🟢 Pass (21.8s) | 🟢 Pass (22.0s) |
| 120,000 | 🟢 Pass (24.7s) | 🟢 Pass (25.6s) | 🟢 Pass (24.1s) |

## Precision Degradation & Safety Margin Analysis

No recall degradation or precision drops were identified! The model demonstrated 100% retrieval accuracy across the entire hardware range of 10,000 to 120,000 tokens.

**Safety Margin Recommendation:** The physical context ceiling of 120K tokens is highly stable. We can confidently use a safety margin of up to 110K tokens for raw prompt size if needed.
