#!/usr/bin/env python3
import sys
import os
import unittest
import json
import shutil
from unittest.mock import MagicMock, patch

# Dynamically resolve and add import paths depending on execution directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

SKILL_DIR = None
# Check if executing in requests_repo subfolder or main folder
if os.path.exists(os.path.join(current_dir, ".agents/skills/lancedb-raptor-rag-engine")):
    SKILL_DIR = os.path.join(current_dir, ".agents/skills/lancedb-raptor-rag-engine")
    WORKSPACE_DIR = current_dir
elif os.path.exists(os.path.join(parent_dir, ".agents/skills/lancedb-raptor-rag-engine")):
    SKILL_DIR = os.path.join(parent_dir, ".agents/skills/lancedb-raptor-rag-engine")
    WORKSPACE_DIR = parent_dir
else:
    # Try hardcoded default path
    SKILL_DIR = "/home/theworks/teamwork_projects/rag_outlook_v1_1/.agents/skills/lancedb-raptor-rag-engine"
    WORKSPACE_DIR = "/home/theworks/teamwork_projects/rag_outlook_v1_1"

sys.path.insert(0, SKILL_DIR)
sys.path.insert(0, WORKSPACE_DIR)

import ast_compactor
import query_edge_rag
import safety_audit
import lsp_diagnostics
import git_sandbox
import visual_verification
import vllm_failover
import agent_orchestrator


class TestTreeSitterAndBracketBalancer(unittest.TestCase):
    def test_python_compaction(self):
        py_code = """def add_values(x, y):
    print("Log statement")
    return x + y
"""
        compacted = ast_compactor.compress_code(py_code, "test.py")
        self.assertIn("def add_values(x, y):", compacted)
        self.assertIn("pass", compacted)
        self.assertNotIn("Log statement", compacted)

    def test_js_compaction(self):
        js_code = """function calculate(a, b) {
    const result = a * b;
    return result;
}"""
        compacted = ast_compactor.compress_code(js_code, "test.js")
        self.assertIn("function calculate(a, b)", compacted)
        self.assertIn("{ /* bypassed */ }", compacted)
        self.assertNotIn("result =", compacted)

    def test_bracket_balancer(self):
        unbalanced = "function bad(a, b { /* bypassed */ }"
        balanced = query_edge_rag.balance_brackets(unbalanced)
        self.assertEqual(balanced, "function bad(a, b { /* bypassed */ })")

        unbalanced_mixed = "[(hello {world}"
        balanced_mixed = query_edge_rag.balance_brackets(unbalanced_mixed)
        self.assertEqual(balanced_mixed, "[(hello {world})]")


class TestParentChildRAG(unittest.TestCase):
    def test_parent_child_retrieval_expansion(self):
        # Verify query_edge_rag fetches parent_text correctly
        query_edge_rag.reset_session()
        # Mock connection and table searches to test metadata extraction
        with patch('query_edge_rag._table') as mock_table:
            mock_arrow = MagicMock()
            mock_search = MagicMock()
            mock_search.limit.return_value = mock_search
            mock_search.to_arrow.return_value = mock_arrow
            mock_table.search.return_value = mock_search
            
            mock_arrow.to_pydict.return_value = {
                "text": ["search_document: child text 1", "search_document: child text 2"],
                "parent_text": ["FULL parent content of node 1", "FULL parent content of node 2"],
                "file_path": ["src/module.py", "src/module.py"]
            }
            
            # Disable tokenizer and session to bypass BGE reranking
            mock_tokenizer = MagicMock()
            mock_tokenizer.return_value = {
                "input_ids": MagicMock(astype=lambda x: MagicMock()),
                "attention_mask": MagicMock(astype=lambda x: MagicMock())
            }
            mock_session = MagicMock()
            mock_session.run.return_value = [MagicMock(squeeze=lambda x: [5.0, 4.0])]
            
            with patch('query_edge_rag._tokenizer', mock_tokenizer), \
                 patch('query_edge_rag._session', mock_session):
                res_json = query_edge_rag.execute_tool("test query", compression_rate=1.0)
                res = json.loads(res_json)
                
                payload = res["compressed_payload"]
                self.assertIn("FULL parent content of node 1", payload)
                self.assertIn("src/module.py", payload)


class TestMultiTurnRAGAndLoopDetection(unittest.TestCase):
    def test_loop_detection_warning(self):
        query_edge_rag.reset_session()
        
        # Call 1
        query_edge_rag.execute_tool("identical query")
        
        # Call 2 (identical query)
        res_json = query_edge_rag.execute_tool("identical query")
        res = json.loads(res_json)
        self.assertIn("System Note: You are repeating the same RAG search query", res["compressed_payload"])


class TestSafetyAuditAndGitSandbox(unittest.TestCase):
    def test_dangerous_command_blocked(self):
        with self.assertRaises(ValueError):
            safety_audit.SafetyAuditor.audit_command("rm -rf /")
            
        with self.assertRaises(ValueError):
            safety_audit.SafetyAuditor.audit_command("reboot")

        # Normal command should pass
        self.assertTrue(safety_audit.SafetyAuditor.audit_command("ls -la"))

    def test_dangerous_file_write_blocked(self):
        with self.assertRaises(ValueError):
            safety_audit.SafetyAuditor.audit_file_write("/etc/passwd", "malicious content")
            
        with self.assertRaises(ValueError):
            safety_audit.SafetyAuditor.audit_file_write("test.py", "import os; os.system('rm -rf /')")

    @patch('subprocess.run')
    def test_git_sandbox_flow(self, mock_run):
        # Mock successful git commands
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")
        
        sandbox = git_sandbox.GitSandbox(WORKSPACE_DIR)
        sandbox.enter()
        self.assertEqual(sandbox.original_branch, "main")
        
        sandbox.commit_and_merge()
        # Verify calls included checkout and merge
        called_cmds = [call[0][0] for call in mock_run.call_args_list]
        self.assertTrue(any("checkout" in cmd for cmd in called_cmds))


class TestLSPDiagnostics(unittest.TestCase):
    def test_python_syntax_diagnostics(self):
        # Create a temp file with invalid python syntax
        temp_file = os.path.join(WORKSPACE_DIR, "temp_syntax_error.py")
        with open(temp_file, "w") as f:
            f.write("def bad_func(\n    print('missing paren')\n")
            
        diagnostics = lsp_diagnostics.get_diagnostics(temp_file)
        self.assertTrue(len(diagnostics) > 0)
        self.assertEqual(diagnostics[0]["severity"], "error")
        
        # Clean up
        if os.path.exists(temp_file):
            os.remove(temp_file)


class TestVisualVerification(unittest.TestCase):
    def test_visual_verifier(self):
        # Create a basic HTML file to test Playwright local serving and capture
        temp_html_dir = os.path.join(WORKSPACE_DIR, "temp_html_verify")
        os.makedirs(temp_html_dir, exist_ok=True)
        
        html_file = os.path.join(temp_html_dir, "index.html")
        with open(html_file, "w") as f:
            f.write("<html><head><title>Visual Verification Title</title></head><body><nav><a href='#'>Menu Link</a></nav></body></html>")
            
        verifier = visual_verification.VisualVerifier(port=10185)
        verifier.start_server(temp_html_dir)
        
        screenshot_path = os.path.join(WORKSPACE_DIR, "temp_screenshot.png")
        
        try:
            report = verifier.verify_page("index.html", screenshot_path)
            self.assertTrue(report["vision_approved"])
            self.assertEqual(report["title"], "Visual Verification Title")
            self.assertTrue(os.path.exists(screenshot_path))
        finally:
            verifier.stop_server()
            # Clean up
            shutil.rmtree(temp_html_dir, ignore_errors=True)
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)


class TestVLLMCalibrationAndFailover(unittest.TestCase):
    def test_cost_limit_guardrail(self):
        client = vllm_failover.ReliableLLMClient(cost_limit=0.01)
        client.cumulative_cost = 0.02
        
        with self.assertRaises(ValueError):
            client.generate([{"role": "user", "content": "hello"}])

    @patch('requests.post')
    def test_failover_to_fallback(self, mock_post):
        # Mock local server connection refusal / failure (status 503)
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_post.return_value = mock_response
        
        client = vllm_failover.ReliableLLMClient()
        # Verify fallback response is returned
        res = client.generate([{"role": "user", "content": "test"}])
        self.assertIn("Simulated Fallback Output", res)


class TestLangGraphOrchestrator(unittest.TestCase):
    @patch('git_sandbox.GitSandbox')
    def test_self_correction_loop_threshold(self, mock_sandbox_class):
        mock_sandbox = MagicMock()
        mock_sandbox_class.return_value = mock_sandbox
        
        # Test that agent loops abort and rollback if self correction exceeds 4 iterations
        query = "fix buggy layout"
        target_file = os.path.join(WORKSPACE_DIR, "temp_orchestrator_test.py")
        
        with patch('agent_orchestrator.lsp_diagnostic_node') as mock_lsp:
            # Always return a diagnostic to trigger self correction
            mock_lsp.return_value = {
                "diagnostics": [{"file": target_file, "line": 1, "column": 1, "message": "Loop error"}],
                "logs": ["Diagnostics mock forced correction"]
            }
            
            result = agent_orchestrator.run_agent_loop(query, target_file, WORKSPACE_DIR)
            self.assertTrue(result["aborted"])
            self.assertFalse(result["success"])
            self.assertTrue(result["loop_count"] > 4)
            mock_sandbox.rollback.assert_called()
            
        if os.path.exists(target_file):
            os.remove(target_file)


if __name__ == "__main__":
    unittest.main()
