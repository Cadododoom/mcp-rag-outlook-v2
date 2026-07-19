# RAG Pipeline Context Limit Toggle Implementation

We have successfully built and integrated the RAG pipeline context limit toggle. The implementation spans the desktop context widget overlay, the global and workstation backup configurations sync engine, the authorization proxy container mounts, and the dynamic resolution mechanism.

---

## 🛠️ Implementation Summary

### 1. UI Toggle in Floating Context Widget
* **File Updated**: [widget.py](file:///home/theworks/teamwork_projects/floating_context_widget/widget.py)
* **Design & Aesthetics**: Added a modern, rounded pill toggle button mapped to the Catppuccin Mocha theme (using `#a6e3a1` for Fast mode, `#cba6f7` for Huge mode, and a soft lavender `#b4befe` on hover).
* **Minimized & Active Layouts**:
  * In the **minimized state**, the header is slightly expanded to `40px` and the toggle button is placed centered-right (`x: 170` to `295`), perfectly aligning with the idle indicators and close button.
  * In the **active stacked panels state**, the header is sized to `35px` and the toggle button occupies the header section next to the close button.
* **Instant Activation**: Clicking the toggle instantly updates the configuration files, refreshes local widget state, and triggers a widget redrawing task.

### 2. Configuration Sync Engine
* Built file-level updaters directly into `widget.py`:
  * **YAML Updater**: Scans for the top-level `model:` block and replaces `physical_context_length` and `context_length` strictly inside that block, preserving all other configuration keys and structural comments.
  * **JSON Updater**: Parses JSON and rewrites the `context_length` parameter for all model configurations under `provider -> vllm -> models` block.
* Updates all 5 active and backup configs synchronously on click:
  1. Active Hermes: `/home/theworks/.hermes/config.yaml`
  2. Backup Hermes 1: `/home/theworks/gdrive_local/AI_Workstation_Backup/host_configs/hermes_config.yaml`
  3. Backup Hermes 2: `/home/theworks/gdrive_local/AI_Workstation_Backup/hermes_swarm_data/.hermes-shared/config.yaml`
  4. Active OpenCode: `/home/theworks/.config/opencode/opencode.json`
  5. Backup OpenCode: `/home/theworks/gdrive_local/AI_Workstation_Backup/host_configs/opencode.json`

### 3. Dynamic RAG Proxy Limit Resolution
* **File Updated**: [proxy.py](file:///home/theworks/gdrive_local/AI_Workstation_Backup/vllm_sglang/proxy.py)
* Refactored static `MAX_CONTEXT_TOKENS` into `get_dynamic_context_limit()` which reads `/opt/data/config.yaml` on every incoming API completions request. Falls back to environment `MAX_CONTEXT_TOKENS` or `75000` on any errors.
* **Docker Compose Mount**: Added read-only mount of `/home/theworks/.hermes` configuration directory under `/opt/data:ro` for `vllm-auth-proxy` service in [docker-compose.yml](file:///home/theworks/gdrive_local/AI_Workstation_Backup/docker-compose.yml).
* The container was restarted, uvicorn dependencies were re-installed, and the service is fully operational.

---

## 🧪 Verification & Testing

An automated verification test script [verify_toggle.py](file:///home/theworks/teamwork_projects/rag_context_toggle/verify_toggle.py) has been provided in the project workspace. It:
1. Simulates toggling between `Fast (75k)` and `Huge (110k)` modes.
2. Checks that all 5 YAML and JSON configuration files (active and backup) are correctly rewritten with target parameters.
3. Invokes a shell command `docker exec` in the running proxy container to execute the parsing logic internally and confirm that the change takes effect immediately without restarts.
4. Makes a test completions request to the HTTP proxy endpoint to verify operational status.

### Test Output Results
```bash
$ python3 verify_toggle.py
[Info] Original settings detected: Physical=110000, Virtual=1770390929483

==================================================
Simulating Toggle to Fast Mode (75000 physical, 37992307469 virtual)...
==================================================
[Verify] Checking configuration files for Physical=75000, Virtual=37992307469...
  [+] active_yaml is CORRECT.
  [+] backup_yaml_1 is CORRECT.
  [+] backup_yaml_2 is CORRECT.
  [+] active_json is CORRECT.
  [+] backup_json is CORRECT.
  [+] Proxy container resolved limit: 75000
  [+] Proxy Dynamic Resolution SUCCESS.

==================================================
Simulating Toggle to Huge Mode (110000 physical, 1770390929483 virtual)...
==================================================
[Verify] Checking configuration files for Physical=110000, Virtual=1770390929483...
  [+] active_yaml is CORRECT.
  [+] backup_yaml_1 is CORRECT.
  [+] backup_yaml_2 is CORRECT.
  [+] active_json is CORRECT.
  [+] backup_json is CORRECT.
  [+] Proxy container resolved limit: 110000
  [+] Proxy Dynamic Resolution SUCCESS.

[Verify] Querying proxy Completions endpoint directly...
  [+] Proxy responded with status code: 200
  [+] Proxy request logic successfully executed without internal server errors.

[Info] Restoring original settings (Physical=110000, Virtual=1770390929483)...
🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉
```
