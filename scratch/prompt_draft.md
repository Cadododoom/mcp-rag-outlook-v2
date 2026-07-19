# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Verify the integration of the 71k/70k context configuration, test end-to-end functionality across the gateway, desktop app, and floating widget, and synchronize all updated configuration files and information to the remote `AI_Workstation_Backup` and `mcp-rag-outlook` repositories.

Working directory: /home/theworks/teamwork_projects/context_validation_suite

## Requirements

### R1. System-Wide Calibration Validation
* Validate that the active vLLM container is running with `--max-model-len 71000` and `--max-num-seqs 6`.
* Verify that the proxy gateway uses a physical context limit of `70000` and is responsive.
* Confirm that Hermes Agent and OpenCode/OpenChamber are configured with the `37992307469` virtual context ceiling.
* Test model options submenu to verify both Thinking and Fast switches are present on a single row, and toggling Thinking OFF correctly swaps to the `-Fast` model.

### R2. Dual-Repository Synchronization
* Verify all modified compose configs, YAML configurations, and JSON registries are staged, committed, and pushed to the `AI_Workstation_Backup` repository.
* Copy the latest RAG performance, embedding comparison, and context scaling markdown reports to `mcp-rag-outlook/scratch/` and push all changes to the remote `mcp-rag-outlook` repository.

### R3. Automated Integration Test Script
* Write a Python script (`validate_system.py`) that checks the `/v1/models` and `/v1/chat/completions` endpoints on the gateway, asserts the model list contains folded variants, and verifies that the config.set endpoint is functional.

## Acceptance Criteria

### Verification & Sync Status
- [ ] vLLM, proxy, and UI clients are confirmed running under the 71k/70k/38B limits.
- [ ] Thinking and Fast switches function correctly without OOM or parameter errors.
- [ ] Both `AI_Workstation_Backup` and `mcp-rag-outlook` git repositories are in a clean, fully-pushed state with no unstaged changes.
- [ ] `validate_system.py` runs and passes all endpoint connectivity and parameter checks.
