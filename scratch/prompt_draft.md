# Teamwork Project Prompt — Draft

> Status: Step 1 — Eliciting project idea
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Re-calibrate the local workstation and vLLM configuration to Option A (4-agent concurrency, 112k vLLM max model length, 110k RAG proxy limit) and verify the performance of both the vLLM container and RAG pipeline.

Working directory: /home/theworks/teamwork_projects/workstation_calibration_option_a

## Requirements

### R1. Configuration Re-calibration to Option A
* Update all active and backup configurations (including `docker-compose.yml`, `config.yaml`, `opencode.json` in the active locations and remote backup repositories `AI_Workstation_Backup` and `mcp-rag-outlook-v2`) to reflect:
  - 4 concurrent agents
  - vLLM `--max-model-len` = `112000`
  - vLLM `--max-num-seqs` = `4`
  - RAG auth-proxy limit = `110000`
  - Recalculated virtual context ceiling for 4 agents at 110k tokens.

### R2. vLLM Container Re-launch and Benchmark
* Restart the docker-compose services with the new configurations.
* Run a sustained 60-second concurrency benchmark with 4 agents to measure prefill and decode tokens per second (TPS).

### R3. RAG Pipeline Verification
* Execute a RAG query to ensure that the search, context retrieval, compression (at 0.33), and model completion function end-to-end without errors.

## Acceptance Criteria

### Workstation Re-calibration
- [ ] Active and backup configuration files contain the exact calibration limits (4 agents, 112k/110k).
- [ ] vLLM container is running with `--max-model-len 112000` and `--max-num-seqs 4`.

### Performance & Operation
- [ ] 4-agent sustained concurrency benchmark completes successfully, verifying high decode TPS (approx 50+ TPS per agent) and low TTFT.
- [ ] RAG pipeline query runs successfully without error, displaying the retrieved and compressed context payload.
