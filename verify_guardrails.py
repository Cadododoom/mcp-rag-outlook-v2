import os
import json
import unittest.mock as mock

from prompt_builder import PromptBuilder
from delegate_tool import delegate_task
from file_tool import write_and_verify_file

def test_context_cliff():
    builder = PromptBuilder(100)
    context = "a" * 90
    result = builder.build_prompt(context)
    assert "/compress" in result, "Warning not injected for large context"
    
    result2 = builder.build_prompt("short")
    assert "/compress" not in result2, "Warning injected when not needed"
    print("Context cliff test passed.")

def test_max_depth():
    registry_path = "active_swarm.json"
    swarm = {
        "agent4": {"parent_id": "agent3"},
        "agent3": {"parent_id": "agent2"},
        "agent2": {"parent_id": "agent1"},
        "agent1": {"parent_id": None}
    }
    with open(registry_path, "w") as f:
        json.dump(swarm, f)
        
    try:
        delegate_task("agent4", "do work", registry_path)
        assert False, "Expected nesting limit error"
    except ValueError as e:
        assert "Nesting limit error" in str(e), f"Unexpected error: {e}"
        
    try:
        delegate_task("agent2", "do work", registry_path)
    except Exception as e:
        assert False, f"Agent2 should be able to delegate, but got: {e}"
        
    print("Max depth test passed.")

def test_file_verification():
    # 1. Success case
    test_file = "dummy.txt"
    write_and_verify_file(test_file, "hello")
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # 2. Mocking a failed write
    import builtins
    original_open = builtins.open
    
    def mocked_open(*args, **kwargs):
        if args[0] == "test_fail.txt" and 'r' in args[1]:
            mock_file = mock.MagicMock()
            mock_file.__enter__.return_value.read.return_value = "wrong content"
            return mock_file
        return original_open(*args, **kwargs)
        
    with mock.patch("builtins.open", mocked_open):
        try:
            write_and_verify_file("test_fail.txt", "expected content")
            assert False, "Expected validation error"
        except ValueError as e:
            assert "Filesystem validation error" in str(e)
            
    if os.path.exists("test_fail.txt"):
        os.remove("test_fail.txt")
        
    print("File verification test passed.")

if __name__ == "__main__":
    test_context_cliff()
    test_max_depth()
    test_file_verification()
    print("All tests passed successfully.")
