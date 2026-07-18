import requests
import json
import random
import time
import psutil

VLLM_URL = "http://localhost:30000/v1/chat/completions"
EMBEDDING_URL = "http://127.0.0.1:8080/v1/embeddings"
MILVUS_URL = "http://localhost:18080"
CONV_ID = "proxy-routing-benchmark-conv"

# Helper to get embeddings
def get_embedding(text):
    res = requests.post(EMBEDDING_URL, json={"input": text})
    res.raise_for_status()
    return res.json()["data"][0]["embedding"]

# Helper to insert memory
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

# Helper to search memories
def search_memory(query, limit=3):
    vector = get_embedding(query)
    payload = {
        "collectionName": "agent_memories",
        "data": [vector],
        "filter": f'conversationId == "{CONV_ID}"',
        "limit": limit,
        "outputFields": ["summary", "details"]
    }
    res = requests.post(f"{MILVUS_URL}/v2/vectordb/entities/search", json=payload)
    res.raise_for_status()
    hits = res.json().get("data", [])
    if not hits:
        return "No matching memories found."
    formatted = []
    for i, h in enumerate(hits):
        formatted.append(f"[Memory {i+1}] Summary: {h['summary']}\nDetails: {h['details']}")
    return "\n---\n".join(formatted)

# Generate a large chunk of text to inflate context (approx 3,000 tokens)
def generate_large_history_message(index):
    topics = [
        "Distributed system synchronization protocols and consensus models (Paxos, Raft).",
        "Garbage collection algorithms in JVM and V8, memory footprint compaction, and heap layout.",
        "AST parsing, lexing, and tokenization optimizations in TypeScript/Rust transpilers.",
        "Linux kernel scheduling policies, CFS virtual runtime, and thread affinity mapping.",
        "TCP congestion control mechanisms, BBR window adjustments, and packet retransmission queues."
    ]
    topic = topics[index % len(topics)]
    paragraphs = []
    for i in range(15):
        paragraphs.append(
            f"Regarding {topic} - Paragraph {i+1}: It is essential to understand the implications of thread pooling, "
            f"memory barriers, cache-line bouncing (L1/L2 coherence), and memory layout alignment. "
            f"When scaling concurrent workers to 100,000+ coroutines, the scheduler overhead can exceed the actual task execution duration. "
            f"To mitigate scheduling latency, engineers employ thread-affinity pin mapping and lock-free ring buffer queues. "
            f"Additionally, memory allocation fragmentation can be addressed using customized block arena allocators (jemalloc or tcmalloc). "
            f"We must profile memory heap allocations using heaptrack or valgrind tools to identify leak patterns under long-running cycles."
        )
    return "\n\n".join(paragraphs)

def run_benchmark():
    print("==========================================================")
    print("    STARTING CONTEXT RE-ROUTING PROXY STRESS BENCHMARK    ")
    print("==========================================================")
    
    # 1. Clear database from prior runs by deleting and recreating entities or storing new distinct facts
    print("[1/5] Injecting target database facts into Milvus RAG...")
    db_url = "postgresql://postgres:benchmark-secure-pass-99@localhost:5432/bench_db"
    jwt_secret = "jwt-secret-string-benchmark-alpha-beta-gamma-998877"
    
    insert_memory(
        summary="Production Database Connection String Configured",
        details=f"Database URL: {db_url}"
    )
    insert_memory(
        summary="Authentication API JWT Validator Details Configured",
        details=f"JWT Token signing key: {jwt_secret}"
    )
    print("      Milvus facts populated successfully.")

    # 2. Build a massive conversation history (approx 30,000 tokens)
    # The original query is user message 0, but it will be kept by our proxy.
    # The intermediate messages will be very large and will get truncated.
    print("[2/5] Constructing massive simulated dialog history (30k tokens)...")
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI coding assistant. You have access to a tool `retrieve_chat_memory` to fetch past facts, "
                "setup configurations, or milestones. If you do not possess specific database credentials or secret keys "
                "in your active context, you MUST call this tool to retrieve them before answering."
            )
        },
        {
            "role": "user",
            "content": "Please write a Fastify route handler to query users from our production database. I need to make sure we use the correct database credentials and configure the token validator."
        }
    ]
    
    # Add 10 large intermediate turns to blow past the 22k token proxy limit (approx 3k tokens per turn)
    for i in range(10):
        # Alternate roles to make it a valid conversation history
        role = "assistant" if i % 2 == 0 else "user"
        messages.append({
            "role": role,
            "content": f"Here is some dense technical context regarding architectural optimization:\n{generate_large_history_message(i)}"
        })
        
    print(f"      Total messages in payload: {len(messages)}")
    approx_input_tokens = sum(len(m["content"]) // 4 for m in messages)
    print(f"      Approximate input payload size: {approx_input_tokens} tokens")

    # 3. Setup tool schema
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

    # 4. Measure CPU usage baseline
    cpu_start = psutil.cpu_percent(interval=1.0)
    print(f"[3/5] CPU Utilization (Baseline): {cpu_start}%")

    # 5. Send payload through proxy
    print("[4/5] Sending 30k token payload through proxy to vLLM (Streaming)...")
    payload = {
        "model": "Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.1
    }
    
    t0 = time.time()
    cpu_readings = []
    
    try:
        # We query the proxy on port 8000
        res = requests.post(VLLM_URL, json=payload)
        res.raise_for_status()
        duration = time.time() - t0
        
        # Collect CPU reading during query execution
        cpu_readings.append(psutil.cpu_percent())
        
        response_json = res.json()
        choice = response_json["choices"][0]
        message = choice["message"]
    except Exception as e:
        print(f"Failed to query vLLM: {e}")
        return

    # Check for tool call
    tool_calls = message.get("tool_calls", [])
    if not tool_calls:
        print("[LLM Response] Model did not request tool calls. Output:")
        print(message.get("content"))
        return

    print(f"      LLM response received in {duration:.2f}s.")
    print(f"      Model requested tool call: {tool_calls[0]['function']['name']}")
    tool_args = json.loads(tool_calls[0]["function"]["arguments"])
    query = tool_args["query"]
    print(f"      Query Parameter: '{query}'")

    # 6. Execute RAG Search
    print("[5/5] Executing vector RAG retrieval and feeding back to vLLM...")
    retrieved_context = search_memory(query)
    print(f"      Retrieved Context:\n{retrieved_context}")

    # Add tool response and call vLLM again for final code generation
    messages.append(message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_calls[0]["id"],
        "name": "retrieve_chat_memory",
        "content": retrieved_context
    })
    
    # We must truncate the payload again, which the proxy does automatically!
    payload["messages"] = messages
    del payload["tools"]
    del payload["tool_choice"]
    
    t_gen = time.time()
    try:
        res = requests.post(VLLM_URL, json=payload)
        res.raise_for_status()
        final_response = res.json()["choices"][0]["message"]["content"]
        gen_duration = time.time() - t_gen
        cpu_readings.append(psutil.cpu_percent())
        
        print("\n================ [BENCHMARK FINAL ROUTE CODE] ================")
        print(final_response)
        print("================================================================")
        
        # Verify the code contains our benchmark credentials
        success = (db_url in final_response) and (jwt_secret in final_response)
        
        print("\n================ BENCHMARK REPORT ================")
        print(f"Verification Success: {success}")
        print(f"Initial LLM Turn Duration: {duration:.2f}s")
        print(f"Final Generation Turn Duration: {gen_duration:.2f}s")
        print(f"Average CPU Usage during execution: {sum(cpu_readings)/len(cpu_readings):.1f}%")
        print(f"Maximum CPU Usage during execution: {max(cpu_readings):.1f}%")
        print("==================================================\n")
        
    except Exception as e:
        print(f"Failed final generation: {e}")

if __name__ == "__main__":
    run_benchmark()
