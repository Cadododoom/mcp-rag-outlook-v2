---
name: sglang-speculative-orchestrator
description: Routes high-throughput, low-latency text generation tasks to the local SGLang speculative serving backend. Use when managing parallel subagent execution loops.
version: 1.0.0
tools:
  - name: generate_language_response
    description: Generates low-latency text completions using SGLang with DFlash block-diffusion and local draft isolation.
    parameters:
      type: object
      properties:
        prompt:
          type: string
          description: The input text prompt to compile.
        max_tokens:
          type: integer
          default: 2048
          description: Maximum tokens to generate.
        temperature:
          type: float
          default: 0.0
          description: Recommend 0.0 to maximize speculative acceptance rates.
      required:
        - prompt
---

# SGLang Speculative Orchestrator Skill

This skill registers the dual NVIDIA RTX 5060 Ti language backend running the 4.75-bit PrismaQuant model. The tool routes requests to port 30000, enforcing a speculation window of 6 draft tokens to maximize throughput.
