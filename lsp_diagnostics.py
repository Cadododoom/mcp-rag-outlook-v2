import os
import sys
import subprocess
import threading
import json
import time

class LSPDaemon:
    def __init__(self):
        self._lock = threading.Lock()
        self._cache = {}
        self._running = True
        self._thread = threading.Thread(target=self._run_daemon, daemon=True)
        self._thread.start()

    def _run_daemon(self):
        # Simulate LSP background activity (keep connection active)
        while self._running:
            time.sleep(1)

    def stop(self):
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def check_file(self, file_path: str):
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return []
            
        ext = os.path.splitext(abs_path)[1].lower()
        
        if ext == '.py':
            return self._check_python(abs_path)
        elif ext in ('.js', '.jsx', '.ts', '.tsx'):
            return self._check_js_ts(abs_path)
        return []

    def _check_python(self, file_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            compile(code, file_path, 'exec')
            return []
        except SyntaxError as e:
            return [{
                "file": file_path,
                "line": e.lineno or 1,
                "column": e.offset or 1,
                "message": f"SyntaxError: {e.msg}",
                "severity": "error",
                "source": "LSP-Python"
            }]
        except Exception as e:
            return [{
                "file": file_path,
                "line": 1,
                "column": 1,
                "message": f"LSP Compiler Error: {str(e)}",
                "severity": "error",
                "source": "LSP-Python"
            }]

    def _check_js_ts(self, file_path: str):
        esbuild_path = "/home/theworks/.local/bin/esbuild"
        if not os.path.exists(esbuild_path):
            esbuild_path = "esbuild" # fallback to path search
            
        try:
            # Run esbuild in check mode (compile but write nothing)
            cmd = [esbuild_path, file_path, "--bundle", "--dryrun"]
            # To avoid bundler issues with imports, we can just compile without bundling:
            cmd = [esbuild_path, file_path, "--log-level=silent"]
            
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return []
                
            # If compile fails, re-run with verbose logging to parse stdout/stderr
            cmd = [esbuild_path, file_path, "--log-level=warning"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse esbuild error output
            diagnostics = []
            errors = res.stderr.strip()
            
            # Match pattern: path/to/file.ts:line:column: error: message
            # e.g., "scratch/test.ts:3:4: error: Expected ';'"
            pattern = r'^(.*?):(\d+):(\d+):\s*(error|warning):\s*(.*)$'
            for line in errors.splitlines():
                m = re.match(pattern, line.strip())
                if m:
                    diagnostics.append({
                        "file": m.group(1),
                        "line": int(m.group(2)),
                        "column": int(m.group(3)),
                        "message": f"esbuild error: {m.group(5)}",
                        "severity": m.group(4),
                        "source": "LSP-JS-TS"
                    })
                    
            if not diagnostics and errors:
                # Fallback if parsing fails but we have stderr
                diagnostics.append({
                    "file": file_path,
                    "line": 1,
                    "column": 1,
                    "message": errors.splitlines()[0] if errors.splitlines() else "Unknown syntax error",
                    "severity": "error",
                    "source": "LSP-JS-TS"
                })
            return diagnostics
        except Exception as e:
            # Fallback using node syntax check for JS
            if file_path.endswith('.js'):
                try:
                    res = subprocess.run(["node", "--check", file_path], capture_output=True, text=True)
                    if res.returncode != 0:
                        return [{
                            "file": file_path,
                            "line": 1,
                            "column": 1,
                            "message": res.stderr.strip(),
                            "severity": "error",
                            "source": "LSP-Node"
                        }]
                except Exception:
                    pass
            return []

# Singleton instance
_lsp_daemon = None

def get_diagnostics(file_path: str):
    global _lsp_daemon
    if _lsp_daemon is None:
        _lsp_daemon = LSPDaemon()
    return _lsp_daemon.check_file(file_path)
