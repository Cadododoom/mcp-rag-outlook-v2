import requests
import json
import random
import time

VLLM_URL = "http://localhost:8000/v1/chat/completions"
EMBEDDING_URL = "http://127.0.0.1:8080/v1/embeddings"
MILVUS_URL = "http://localhost:18080"
CONV_ID = "rag-volume-test-conv"

# Technical specification document chunks to simulate large amounts of data
TECH_SPECS = [
    {
        "summary": "Antigravity Project Overview",
        "details": "Project Antigravity is a distributed agentic workflow orchestrator. It coordinates up to 64 micro-agents concurrently across a virtualized network mesh. The system is designed to run locally on multi-GPU consumer workstations."
    },
    {
        "summary": "Antigravity Database Architecture and credentials",
        "details": "The orchestrator uses a primary TimescaleDB instance for telemetry logging. Connection string: postgresql://telemetry_master:SecureTelemetryPass2026!@telemetry-db.internal:5432/telemetry. Pool size is capped at 100 connections with a timeout of 15000ms."
    },
    {
        "summary": "Antigravity Gateway API port and routing",
        "details": "The main API Gateway listens on port 9090. All incoming external requests are routed through a Fastify reverse proxy. The proxy terminates TLS and forwards requests to internal node groups on port 9091."
    },
    {
        "summary": "Antigravity Authentication JWT configurations",
        "details": "Security is enforced via JWT. Tokens are signed using the RS256 algorithm. The public key is retrieved from http://auth-service.internal:8081/jwks.json. Token expiration is set to exactly 900 seconds (15 minutes) with no grace period."
    },
    {
        "summary": "Antigravity Cache Layer configurations",
        "details": "Redis is used for session token caching and rate limiting. The Redis cluster operates on port 6379 with password 'RedisSessionCachePass2026'. Max memory policy is volatile-lru, capped at 4GB."
    },
    {
        "summary": "Antigravity Telemetry logging format",
        "details": "All logs are formatted as structured JSON. Required fields for every log entry: timestamp (epoch ms), traceId (UUIDv4), spanId (UUIDv4), componentName, severity, and payload. Telemetry is flushed to TimescaleDB every 5 seconds."
    },
    {
        "summary": "Antigravity Heartbeat agent protocol",
        "details": "Micro-agents check in with the orchestrator every 30 seconds by sending a POST request to /agents/heartbeat. The payload must include the agentId, activeTaskId, and current VRAM usage in bytes. If an agent misses two consecutive check-ins, it is marked as offline."
    },
    {
        "summary": "Antigravity Agent deployment parameters",
        "details": "Agents are deployed as Docker containers using the image 'antigravity-agent:v2.5.0'. Each container is allocated 1 CPU core and 2GB of physical system RAM. GPU access is granted via nvidia-docker runtime with a VRAM limit of 2GB."
    },
    {
        "summary": "Antigravity Storage bucket specifications",
        "details": "Artifacts and agent logs are persisted in a local MinIO bucket named 'antigravity-artifacts'. Access key is 'AntigravityMinioAdmin', secret key is 'SuperSecretMinioPassword2026'. The endpoint is http://minio.internal:9000."
    },
    {
        "summary": "Antigravity Message queue configurations",
        "details": "RabbitMQ is used for inter-agent message passing. The queue runs on port 5672 with AMQP protocol. Standard queue name is 'agent-tasks-queue', configured as durable and non-auto-delete."
    }
]

# Add additional filler chunks to simulate "large amounts of data"
for i in range(40):
    TECH_SPECS.append({
        "summary": f"Antigravity System Policy Reference Doc #{i}",
        "details": f"Policy document reference code AG-POL-{1000 + i}. Section {i // 10}. Paragraph {i % 10}. This section covers general operating guidelines, workstation maintenance, air-conditioning requirements, and physical security procedures for local compute nodes. All workstations must maintain room temperature below 22 degrees Celsius and keep GPU fans clean."
    })

def get_embedding(text):
    res = requests.post(EMBEDDING_URL, json={"input": text})
    res.raise_for_status()
    return res.json()["data"][0]["embedding"]

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

def search_memory(query, limit=5):
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

def run_volume_test():
    print("==========================================================")
    print("       ANTIGRAVITY RAG VOLUME & COMPREHENSION TEST        ")
    print("==========================================================")
    
    # 1. Populate Milvus with the extensive specs
    print(f"\n[Step 1] Ingesting {len(TECH_SPECS)} specification chunks into Milvus...")
    start_time = time.time()
    inserted_count = 0
    for chunk in TECH_SPECS:
        try:
            insert_memory(chunk["summary"], chunk["details"])
            inserted_count += 1
            if inserted_count % 10 == 0:
                print(f"  Ingested {inserted_count}/{len(TECH_SPECS)} documents...")
        except Exception as e:
            print(f"  Failed to insert chunk '{chunk['summary']}': {e}")
            return
    
    ingest_time = time.time() - start_time
    print(f"  Completed ingestion of {inserted_count} docs in {ingest_time:.2f} seconds.")

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

    # 3. Prompt requiring multiple disjointed facts
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI coding assistant. Your working context length is limited. "
                "You have access to a tool `retrieve_chat_memory` to fetch past configurations and decisions "
                "from your database. Use this tool if you need database URLs, JWT keys, API ports, storage buckets, or queue details."
            )
        },
        {
            "role": "user",
            "content": (
                "Write a Docker Compose file and a Node.js Fastify server for deploying a new Antigravity node. "
                "The server needs to run on the correct API Gateway port, connect to the telemetry database with the correct credentials, "
                "validate JWT tokens using the configured algorithm/JWKS endpoint, and verify agent status via MinIO storage. "
                "Make sure you retrieve all these values from your long-term memory."
            )
        }
    ]

    # 4. First LLM Query
    print("\n[Step 2] Querying vLLM to analyze request...")
    payload = {
        "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.2
    }
    
    try:
        t0 = time.time()
        res = requests.post(VLLM_URL, json=payload)
        res.raise_for_status()
        ttft = time.time() - t0
        print(f"  Received response from vLLM (TTFT: {ttft:.2f}s)")
        
        response_json = res.json()
        message = response_json["choices"][0]["message"]
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
    retrieved_context = search_memory(query, limit=6)
    print(f"[RAG Retrieved Context (Top 6 hits)]:\n{retrieved_context}")

    # 7. Feed tool result back to vLLM
    print("\n[Step 5] Feeding retrieved context back to vLLM for final generation...")
    messages.append(message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_calls[0]["id"],
        "name": "retrieve_chat_memory",
        "content": retrieved_context
    })

    payload["messages"] = messages
    del payload["tools"]
    del payload["tool_choice"]

    try:
        t0 = time.time()
        res = requests.post(VLLM_URL, json=payload)
        res.raise_for_status()
        duration = time.time() - t0
        final_response = res.json()["choices"][0]["message"]["content"]
        print(f"  Received final response in {duration:.2f}s")
        print("\n================ [FINAL GENERATED CONFIGS & CODE] ================")
        print(final_response)
        print("================================================================\n")
        print("Volume and comprehension test completed successfully!")
    except Exception as e:
        print(f"Failed final generation: {e}")

if __name__ == "__main__":
    run_volume_test()
