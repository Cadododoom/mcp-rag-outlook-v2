import requests
import json
import random
import time

VLLM_URL = "http://localhost:8000/v1/chat/completions"
EMBEDDING_URL = "http://localhost:8080/v1/embeddings"
MILVUS_URL = "http://localhost:18080"
CONV_ID = "rag-integration-test-conv"

# Helper to get embeddings from llama.cpp container
def get_embedding(text):
    res = requests.post(EMBEDDING_URL, json={"input": text})
    res.raise_for_status()
    return res.json()["data"][0]["embedding"]

# Helper to insert memory into Milvus
def insert_memory(summary, details):
    vector = get_embedding(summary)
    payload = {
        "collectionName": "agent_memories",
        "data": [
            {
                "id": random.randint(1000000000, 9999999999),
                "vector": vector,
                "conversationId": CONV_ID,
                "summary": summary,
                "details": details,
                "timestamp": int(time.time() * 1000)
            }
        ]
    }
    res = requests.post(f"{MILVUS_URL}/v2/vectordb/entities/insert", json=payload)
    res.raise_for_status()
    print(f"[Memory DB] Successfully stored: '{summary}'")

# Helper to search memories in Milvus
def search_memory(query, limit=3):
    vector = get_embedding(query)
    payload = {
        "collectionName": "agent_memories",
        "data": [vector],
        "filter": f'conversationId == "{CONV_ID}"',
        "limit": limit,
        "outputFields": ["summary", "details", "timestamp"]
    }
    res = requests.post(f"{MILVUS_URL}/v2/vectordb/entities/search", json=payload)
    res.raise_for_status()
    hits = res.json().get("data", [])
    
    if not hits:
        return "No matching memories found."
    
    formatted = []
    for i, h in enumerate(hits):
        formatted.append(f"[Past Memory {i+1}] Summary: {h['summary']}\nDetails: {h['details']}")
    return "\n---\n".join(formatted)

def run_test():
    print("==========================================================")
    # 1. Populate RAG database with test facts
    print("[Step 1] Populating Milvus database with project milestones...")
    try:
        insert_memory(
            summary="Postgres connection credentials configured",
            details="Database URL: postgresql://postgres:auth-key-9988@localhost:5432/production_db"
        )
        insert_memory(
            summary="Auth API Secret configuration details",
            details="JWT Token signing key: jwt-secret-string-alpha-beta-12345"
        )
        insert_memory(
            summary="Framework choice and setup decisions",
            details="Project is written in Node.js using Fastify and TypeORM for postgres connection."
        )
    except Exception as e:
        print(f"Failed to populate database: {e}")
        return

    # 2. Formulate tool schemas for vLLM
    tools = [
        {
            "type": "function",
            "function": {
                "name": "retrieve_chat_memory",
                "description": "Query the agent's long-term memory vector database for past facts, setup configurations, or milestones.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Semantic query describing what memory fact to retrieve."
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
                "You have access to a tool `retrieve_chat_memory` to fetch past configurations and decisions "
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
        "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.1
    }
    
    try:
        res = requests.post(VLLM_URL, json=payload)
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

    # 6. Execute RAG search in Milvus
    print("\n[Step 4] Querying vector database semantically...")
    retrieved_context = search_memory(query)
    print(f"[RAG Retrieved Context]:\n{retrieved_context}")

    # 7. Feed tool result back to vLLM
    print("\n[Step 5] Feeding tool results back to vLLM for final generation...")
    # Add assistant message and tool response message
    messages.append(message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_calls[0]["id"],
        "name": "retrieve_chat_memory",
        "content": retrieved_context
    })

    payload["messages"] = messages
    # Remove tools/tool_choice to force generation output
    del payload["tools"]
    del payload["tool_choice"]

    try:
        res = requests.post(VLLM_URL, json=payload)
        res.raise_for_status()
        final_response = res.json()["choices"][0]["message"]["content"]
        print("\n================ [FINAL LLM ROUTE HANDLER CODE] ================")
        print(final_response)
        print("================================================================\n")
    except Exception as e:
        print(f"Failed final generation: {e}")

if __name__ == "__main__":
    run_test()
