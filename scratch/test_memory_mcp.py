import json
import subprocess
import sys

def main():
    print("Testing memory manager MCP server JSON-RPC loop...")
    
    # Spawn the memory manager script
    # Inside the container, it's run as 'python3 mcp_server/launch-memory-mcp.py'
    proc = subprocess.Popen(
        ["python3", "mcp_server/launch-memory-mcp.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 1. Send initialize
    init_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_request) + "\n")
    proc.stdin.flush()
    
    init_response = json.loads(proc.stdout.readline())
    print("Initialize Response:", init_response)
    assert init_response["id"] == 1
    assert "capabilities" in init_response["result"]
    
    # 2. Send tools/list
    list_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    proc.stdin.write(json.dumps(list_request) + "\n")
    proc.stdin.flush()
    
    list_response = json.loads(proc.stdout.readline())
    print("Tools List Response:", list_response)
    assert list_response["id"] == 2
    tools = list_response["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "store_chat_memory" in tool_names
    assert "retrieve_chat_memory" in tool_names
    
    # 3. Call store_chat_memory
    store_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "store_chat_memory",
            "arguments": {
                "conversationId": "test-conv-123",
                "summary": "The test token is 'secure-token-abc-123'",
                "details": "This token is used for authentication in the HyperionGateway."
            }
        }
    }
    proc.stdin.write(json.dumps(store_request) + "\n")
    proc.stdin.flush()
    
    store_response = json.loads(proc.stdout.readline())
    print("Store Memory Response:", store_response)
    assert store_response["id"] == 3
    assert not store_response["result"]["isError"]
    
    # 4. Call retrieve_chat_memory
    retrieve_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "retrieve_chat_memory",
            "arguments": {
                "conversationId": "test-conv-123",
                "query": "HyperionGateway secure test token"
            }
        }
    }
    proc.stdin.write(json.dumps(retrieve_request) + "\n")
    proc.stdin.flush()
    
    retrieve_response = json.loads(proc.stdout.readline())
    print("Retrieve Memory Response:", retrieve_response)
    assert retrieve_response["id"] == 4
    content = retrieve_response["result"]["content"][0]["text"]
    print("Retrieved Text:\n", content)
    assert "secure-token-abc-123" in content
    
    # Cleanup
    proc.terminate()
    proc.wait()
    print("=== All JSON-RPC tests PASSED! ===")

if __name__ == "__main__":
    main()
