#!/usr/bin/env python3
import sys
import json
import time
from pathlib import Path

# Add active agent library directories to sys.path
sys.path.insert(0, "/home/theworks/.hermes/hermes-agent")

# Stub build_system_prompt_parts before importing context_breakdown to avoid loading requirements
import agent.system_prompt
agent.system_prompt.build_system_prompt_parts = lambda agent: {
    "stable": "Mock system prompt with <available_skills>available skills</available_skills>",
    "context": "Mock rules",
    "volatile": "Mock volatile memory"
}

from agent.context_breakdown import compute_session_context_breakdown, update_swarm_session, _get_registry_path

class MockCompressor:
    def __init__(self, context_length=32000, last_prompt_tokens=5000):
        self.context_length = context_length
        self.last_prompt_tokens = last_prompt_tokens

    def get_virtual_tokens(self, estimated_total):
        return estimated_total

class MockAgent:
    def __init__(self, session_id="parent_session_id", model="gemini-pro", parent_session_id=None):
        self.session_id = session_id
        self.model = model
        self.parent_session_id = parent_session_id
        self.context_compressor = MockCompressor()
        self._memory_store = None
        self.tools = []
        self._workspace_mode = "inherit"

def test_registry_write():
    print("Running test_registry_write...")
    # Clear registry first
    path = _get_registry_path()
    if path.exists():
        path.unlink()
        
    update_swarm_session(
        session_id="child_1",
        role="leaf",
        workspace_mode="branch",
        active=True,
        parent_uuid="parent_1",
        goal="do research",
        model="gemini-flash",
        context_used=1000,
        context_max=32000
    )
    
    assert path.exists(), "Registry file was not created!"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert "child_1" in data, "child_1 missing from registry"
    child = data["child_1"]
    assert child["uuid"] == "child_1"
    assert child["role"] == "leaf"
    assert child["workspace_mode"] == "branch"
    assert child["active"] is True
    assert child["parent_uuid"] == "parent_1"
    assert child["goal"] == "do research"
    assert child["model"] == "gemini-flash"
    assert child["context_used"] == 1000
    assert child["context_max"] == 32000
    print("[+] test_registry_write passed successfully!")

def test_breakdown_calculations():
    print("Running test_breakdown_calculations...")
    # Re-setup registry
    path = _get_registry_path()
    if path.exists():
        path.unlink()
        
    # Write parent (active)
    update_swarm_session(
        session_id="parent_1",
        role="parent",
        workspace_mode="inherit",
        active=True,
        parent_uuid=None,
        goal=None,
        model="gemini-pro",
        context_used=5000,
        context_max=32000
    )
    
    # Write child_shared (active, workspace=inherit)
    update_swarm_session(
        session_id="child_shared",
        role="orchestrator",
        workspace_mode="inherit",
        active=True,
        parent_uuid="parent_1",
        goal="sub-task shared",
        model="gemini-flash",
        context_used=2000,
        context_max=32000
    )
    
    # Write child_isolated (inactive/decaying, workspace=branch)
    update_swarm_session(
        session_id="child_isolated",
        role="leaf",
        workspace_mode="branch",
        active=False,
        parent_uuid="parent_1",
        goal="sub-task isolated",
        model="gemini-flash",
        context_used=1500,
        context_max=32000
    )
    
    agent = MockAgent(session_id="parent_1", model="gemini-pro")
    
    breakdown = compute_session_context_breakdown(agent)
    
    assert "swarm" in breakdown, "swarm key missing in breakdown"
    swarm = breakdown["swarm"]
    
    assert swarm["cumulative_context"] == 8500, f"Expected cumulative context 8500, got {swarm['cumulative_context']}"
    
    nodes = {n["uuid"]: n for n in swarm["nodes"]}
    assert "parent_1" in nodes, "parent_1 node missing"
    assert "child_shared" in nodes, "child_shared node missing"
    assert "child_isolated" in nodes, "child_isolated node missing"
    
    # Check sharing states
    assert nodes["child_shared"]["sharing_state"] == "shared", "child_shared sharing state should be 'shared'"
    assert nodes["child_isolated"]["sharing_state"] == "isolated", "child_isolated sharing state should be 'isolated'"
    
    # Check decay countdowns
    assert nodes["child_shared"]["decay_countdown"] == 60.0, "active child_shared should have full decay countdown"
    assert nodes["child_isolated"]["decay_countdown"] > 0.0, "inactive child_isolated should have decaying countdown > 0"
    assert nodes["child_isolated"]["decay_countdown"] <= 60.0, "inactive child_isolated decay countdown should be <= 60"
    
    print("[+] test_breakdown_calculations passed successfully!")

def test_decay_expiration():
    print("Running test_decay_expiration...")
    path = _get_registry_path()
    if path.exists():
        path.unlink()
        
    # Write active parent
    update_swarm_session(
        session_id="parent_1",
        role="parent",
        workspace_mode="inherit",
        active=True,
        parent_uuid=None,
        goal=None,
        model="gemini-pro",
        context_used=5000,
        context_max=32000
    )
    
    # Write fully decayed child (last activity 70 seconds ago)
    path.parent.mkdir(parents=True, exist_ok=True)
    registry = {
        "parent_1": {
            "uuid": "parent_1",
            "parent_uuid": None,
            "role": "parent",
            "workspace_mode": "inherit",
            "active": True,
            "last_activity": time.time(),
            "goal": None,
            "model": "gemini-pro",
            "context_used": 5000,
            "context_max": 32000
        },
        "expired_child": {
            "uuid": "expired_child",
            "parent_uuid": "parent_1",
            "role": "leaf",
            "workspace_mode": "branch",
            "active": False,
            "last_activity": time.time() - 70.0,
            "goal": "expired",
            "model": "gemini-flash",
            "context_used": 1000,
            "context_max": 32000
        }
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        
    agent = MockAgent(session_id="parent_1", model="gemini-pro")
    breakdown = compute_session_context_breakdown(agent)
    
    swarm = breakdown["swarm"]
    nodes = {n["uuid"]: n for n in swarm["nodes"]}
    
    assert "expired_child" not in nodes, "expired_child should have been purged/decayed"
    assert "parent_1" in nodes, "parent_1 should remain"
    
    # Check that expired_child was actually removed from the file
    with open(path, "r", encoding="utf-8") as f:
        registry_after = json.load(f)
    assert "expired_child" not in registry_after, "expired_child should be deleted from active_swarm.json"
    
    print("[+] test_decay_expiration passed successfully!")

if __name__ == "__main__":
    try:
        test_registry_write()
        test_breakdown_calculations()
        test_decay_expiration()
        print("\n=== ALL VERIFICATION TESTS PASSED SUCCESSFULLY! ===")
        sys.exit(0)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
