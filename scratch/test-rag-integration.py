import os
import sys
import requests
import json
import time

VLLM_URL = "http://localhost:30000/v1/chat/completions"
VLLM_HEADERS = {"Authorization": "Bearer vllm-5060ti-token"}

# Add skills path to sys.path
skills_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.agents/skills/lancedb-raptor-rag-engine"))
sys.path.append(skills_path)
from query_edge_rag import execute_tool

def run_test():
    print("==========================================================")
    print("[Step 1] Verifying database population...")
    # LanceDB was populated using populate_lancedb.py
    print("LanceDB store should be populated via populate_lancedb.py.")

    # 2. Formulate tool schemas for vLLM
    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_edge_rag",
                "description": "Query the local high-efficiency RAG engine to retrieve context from LanceDB, rerank, and compress prompts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to retrieve relevant facts."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    # 3. Simulate a conversation where the active history is truncated (no database credentials present in prompt)
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI coding assistant. Your working context length is limited. "
                "You have access to a tool `query_edge_rag` to fetch past configurations and decisions "
                "from your database. Use this tool if you need database URLs, JWT keys, or framework decisions."
            )
        },
        {
            "role": "user",
            "content": "Please write a Fastify route handler to query users from our production database. I need to make sure we use the correct database credentials and configure the token validator."
        }
    ]

    # 4. Query vLLM
    print("\n[Step 2] Sending initial prompt to vLLM (TP=2, Qwen 35B)...")
    payload = {
        "model": "Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.1
    }
    
    try:
        res = requests.post(VLLM_URL, json=payload, headers=VLLM_HEADERS)
        res.raise_for_status()
        response_json = res.json()
        choice = response_json["choices"][0]
        message = choice["message"]
    except Exception as e:
        print(f"Failed to connect or query vLLM: {e}")
        return

    # 5. Check if Qwen requested tool calls
    tool_calls = message.get("tool_calls", [])
    if not tool_calls:
        print("[LLM Response] Model did not request tool calls. Output:")
        print(message.get("content"))
        return

    print(f"\n[Step 3] Model requested tool call: {tool_calls[0]['function']['name']}")
    tool_args = json.loads(tool_calls[0]["function"]["arguments"])
    query = tool_args["query"]
    print(f"  Query Parameter: '{query}'")

    # 6. Execute RAG search using query_edge_rag
    print("\n[Step 4] Querying vector database semantically and compressing prompt...")
    # Execute tool
    result_str = execute_tool(query, compression_rate=0.33)
    print(f"[RAG Retrieved/Compressed Result]:\n{result_str}")

    # Parse payload from the tool result
    try:
        result_json = json.loads(result_str)
        retrieved_context = result_json.get("compressed_payload", "")
    except Exception:
        retrieved_context = result_str

    # 7. Feed tool result back to vLLM
    print("\n[Step 5] Feeding tool results back to vLLM for final generation...")
    # Add assistant message and tool response message
    messages.append(message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_calls[0]["id"],
        "name": "query_edge_rag",
        "content": retrieved_context
    })

    payload["messages"] = messages
    # Remove tools/tool_choice to force generation output
    del payload["tools"]
    del payload["tool_choice"]

    try:
        res = requests.post(VLLM_URL, json=payload, headers=VLLM_HEADERS)
        res.raise_for_status()
        final_response = res.json()["choices"][0]["message"]["content"]
        print("\n================ [FINAL LLM ROUTE HANDLER CODE] ================")
        print(final_response)
        print("================================================================\n")
    except Exception as e:
        print(f"Failed final generation: {e}")

if __name__ == "__main__":
    run_test()
