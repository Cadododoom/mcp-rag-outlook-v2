from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
import os
import sys

# Add paths to imports
sys.path.insert(0, os.path.dirname(__file__))

import query_edge_rag
import lsp_diagnostics
import git_sandbox
import safety_audit
import vllm_failover

class AgentState(TypedDict):
    query: str
    context: str
    diagnostics: List[Dict[str, Any]]
    test_status: str
    loop_count: int
    logs: List[str]
    success: bool
    aborted: bool
    target_file: str
    sandbox: Any

# Node 1: RetrieveContext
def retrieve_context_node(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    logs.append("Entering RetrieveContext Node")
    
    # Expose multi-turn RAG retrieval
    query = state["query"]
    print(f"Orchestrator: Performing multi-turn RAG for: '{query}'")
    
    # Turn 1: Primary search
    res1_json = query_edge_rag.execute_tool(query)
    res1 = json.loads(res1_json)
    payload1 = res1.get("compressed_payload", "")
    
    # Turn 2: Follow-up search based on extracted concepts
    follow_up_query = ""
    if "thrust controller" in payload1.lower() or "thrust" in query.lower():
        follow_up_query = "thrust controller auth token"
    elif "session memory" in payload1.lower() or "vault" in query.lower():
        follow_up_query = "QuantumVault decrypt key"
        
    accumulated_context = payload1
    if follow_up_query:
        logs.append(f"Multi-Turn RAG: Performing follow-up turn query: '{follow_up_query}'")
        res2_json = query_edge_rag.execute_tool(follow_up_query)
        res2 = json.loads(res2_json)
        payload2 = res2.get("compressed_payload", "")
        accumulated_context = f"{payload1}\n\n=== TURN 2 RETRIEVAL: {follow_up_query} ===\n{payload2}"
        
    return {
        "context": accumulated_context,
        "logs": logs
    }

# Node 2: GenerateEdits
def generate_edits_node(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    logs.append(f"Entering GenerateEdits Node (Loop count: {state['loop_count']})")
    
    # Intercept shell and file write safety audit
    safety_audit.SafetyAuditor.audit_file_write(state["target_file"], "Verify write")
    
    # Apply sandboxed code modifications
    target_file = state["target_file"]
    
    # Create the target file directory if missing
    os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)
    
    # Modify code: add simulated implementation or dummy changes
    # In a real environment this would call the LLM to write the edit.
    # To demonstrate loop breaker, we can intentionally write a syntax error if loop_count is 0 or 1,
    # and correct it in a subsequent loop, or keep it to trigger loop abort.
    if state["loop_count"] == 0:
        # Syntax error!
        code = "def test_func():\n    print('test'\n" # missing closing parenthesis
        logs.append("GenerateEdits: Intentionally injected a syntax error (missing paren)")
    else:
        # Correct code
        code = "def test_func():\n    print('test')\n"
        logs.append("GenerateEdits: Wrote corrected code")
        
    with open(target_file, "w") as f:
        f.write(code)
        
    return {
        "logs": logs
    }

# Node 3: LSPDiagnostic
def lsp_diagnostic_node(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    logs.append("Entering LSPDiagnostic Node")
    
    # Run LSP check
    target_file = state["target_file"]
    diagnostics = lsp_diagnostics.get_diagnostics(target_file)
    
    if diagnostics:
        logs.append(f"LSPDiagnostic: Found {len(diagnostics)} diagnostics in {target_file}")
    else:
        logs.append("LSPDiagnostic: No syntax/lint issues found.")
        
    return {
        "diagnostics": diagnostics,
        "logs": logs
    }

# Node 4: RunTests
def run_tests_node(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    logs.append("Entering RunTests Node")
    
    # If there were LSP errors, tests fail immediately
    if state.get("diagnostics"):
        logs.append("RunTests: Diagnostics present, skipping tests and marking FAIL.")
        return {
            "test_status": "FAIL",
            "logs": logs
        }
        
    # Simulate test suite execution
    logs.append("RunTests: Running mock test suite...")
    test_status = "PASS"
    logs.append("RunTests: Mock test suite PASSED.")
    
    return {
        "test_status": test_status,
        "logs": logs
    }

# Node 5: SelfCorrect
def self_correct_node(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    logs.append("Entering SelfCorrect Node")
    
    new_loop_count = state["loop_count"] + 1
    aborted = False
    
    # Strict loop threshold: abort if repeating beyond 4 iterations
    if new_loop_count > 4:
        aborted = True
        logs.append(f"SelfCorrect: Aborting loop. Self-correction threshold (> 4 cycles) exceeded!")
    else:
        logs.append(f"SelfCorrect: Incrementing self-correction loop count to {new_loop_count}")
        
    return {
        "loop_count": new_loop_count,
        "aborted": aborted,
        "logs": logs
    }

# Routing logic after RunTests
def route_after_tests(state: AgentState) -> str:
    if not state.get("diagnostics") and state.get("test_status") == "PASS":
        return "success"
    return "correct"

# Routing logic after SelfCorrect
def route_after_self_correct(state: AgentState) -> str:
    if state.get("aborted"):
        return "abort"
    return "edit"

# Build LangGraph Workflow
import json

def build_workflow() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("RetrieveContext", retrieve_context_node)
    workflow.add_node("GenerateEdits", generate_edits_node)
    workflow.add_node("LSPDiagnostic", lsp_diagnostic_node)
    workflow.add_node("RunTests", run_tests_node)
    workflow.add_node("SelfCorrect", self_correct_node)
    
    # Set Entry Point
    workflow.set_entry_point("RetrieveContext")
    
    # Linear transitions
    workflow.add_edge("RetrieveContext", "GenerateEdits")
    workflow.add_edge("GenerateEdits", "LSPDiagnostic")
    workflow.add_edge("LSPDiagnostic", "RunTests")
    
    # Conditional edge after RunTests
    workflow.add_conditional_edges(
        "RunTests",
        route_after_tests,
        {
            "success": END,
            "correct": "SelfCorrect"
        }
    )
    
    # Conditional edge after SelfCorrect
    workflow.add_conditional_edges(
        "SelfCorrect",
        route_after_self_correct,
        {
            "abort": END,
            "edit": "GenerateEdits"
        }
    )
    
    return workflow.compile()

def run_agent_loop(query: str, target_file: str, repo_path: str) -> Dict[str, Any]:
    # Initialize Git Sandbox
    sandbox = git_sandbox.GitSandbox(repo_path)
    sandbox.enter()
    
    initial_state = {
        "query": query,
        "context": "",
        "diagnostics": [],
        "test_status": "",
        "loop_count": 0,
        "logs": [],
        "success": False,
        "aborted": False,
        "target_file": os.path.abspath(target_file),
        "sandbox": sandbox
    }
    
    app = build_workflow()
    
    try:
        final_state = app.invoke(initial_state)
        
        # Determine success and handle sandbox commit/rollback
        if final_state.get("aborted"):
            print("Orchestrator: Aborted execution. Rolling back sandbox...")
            sandbox.rollback()
            return {
                "success": False,
                "aborted": True,
                "logs": final_state["logs"],
                "loop_count": final_state["loop_count"]
            }
        else:
            print("Orchestrator: Verification succeeded. Committing and merging changes...")
            sandbox.commit_and_merge("Verification success: Auto commit via LangGraph")
            return {
                "success": True,
                "aborted": False,
                "logs": final_state["logs"],
                "loop_count": final_state["loop_count"]
            }
    except Exception as e:
        print(f"Orchestrator Exception: {e}. Rolling back sandbox...")
        sandbox.rollback()
        raise e
