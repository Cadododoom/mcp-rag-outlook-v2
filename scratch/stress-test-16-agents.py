import asyncio
import aiohttp
import json
import random
import time
import requests

VLLM_URL = "http://localhost:8000/v1/chat/completions"
EMBEDDING_URL = "http://127.0.0.1:8080/v1/embeddings"
MILVUS_URL = "http://localhost:18080"
CONV_ID = "rag-stress-test-conv"

# 4 target secrets that were injected during ingestion
TARGETS = [
    {"name": "AlphaCoreEngine", "query": "AlphaCoreEngine thrust authentication credentials token"},
    {"name": "QuantumVault", "query": "QuantumVault AES secure key Registry memory decryption"},
    {"name": "HyperionGateway", "query": "HyperionGateway port route certificate SSL private"},
    {"name": "NexusQueue", "query": "NexusQueue RabbitMQ connection credentials port host"}
]

async def get_embedding(session, text):
    async with session.post(EMBEDDING_URL, json={"input": text}) as response:
        response.raise_for_status()
        data = await response.json()
        return data["data"][0]["embedding"]

async def search_memory(session, query, limit=30):
    # Get embedding for query
    vector = await get_embedding(session, query)
    
    payload = {
        "collectionName": "agent_memories",
        "data": [vector],
        "filter": f'conversationId == "{CONV_ID}"',
        "limit": limit,
        "outputFields": ["summary", "details"]
    }
    
    async with session.post(f"{MILVUS_URL}/v2/vectordb/entities/search", json=payload) as response:
        response.raise_for_status()
        data = await response.json()
        hits = data.get("data", [])
        
        formatted = []
        for i, h in enumerate(hits):
            formatted.append(f"File Reference #{i+1}: {h['summary']}\nSource Code/Details: {h['details']}")
        return "\n---\n".join(formatted)

async def simulate_agent(agent_id, session):
    target = TARGETS[agent_id % len(TARGETS)]
    print(f"[Agent {agent_id:02d}] Starting task: Authenticating with {target['name']}...")
    
    # Step 1: Query database for context (RAG)
    t0 = time.time()
    context = await search_memory(session, target["query"], limit=300) # Retrieve 300 chunks to simulate ~20k tokens context
    rag_latency = time.time() - t0
    
    # Calculate approx tokens (4 characters per token average)
    context_char_len = len(context)
    approx_tokens = context_char_len // 4
    print(f"[Agent {agent_id:02d}] RAG retrieved {approx_tokens} tokens of code context in {rag_latency:.3f}s.")
    
    # Step 2: Formulate prompt
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert software engineer. You are provided with a large codebase context retrieved from the repository database. "
                "Analyze the context and write a complete, production-ready Python class to interface with the requested service. "
                "Use the exact credentials, keys, host, and port configurations found in the codebase context. Do not make up any parameters."
            )
        },
        {
            "role": "user",
            "content": f"Codebase Context:\n{context}\n\nTask: Implement the integration interface class for {target['name']}."
        }
    ]
    
    payload = {
        "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 128,  # Keep output short to focus on prefill load
        "stream": True      # Stream to measure Time to First Token (TTFT)
    }
    
    # Step 3: Query vLLM
    print(f"[Agent {agent_id:02d}] Sending prompt (~{approx_tokens + 100} tokens total) to vLLM...")
    
    t_send = time.time()
    ttft = None
    generated_tokens = 0
    
    async with session.post(VLLM_URL, json=payload) as response:
        response.raise_for_status()
        
        # Read stream
        async for line in response.content:
            line = line.decode('utf-8').strip()
            if not line.startswith("data:"):
                continue
            
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
                
            try:
                chunk = json.loads(data_str)
                delta = chunk["choices"][0]["delta"]
                
                # Capture TTFT on first token
                if ttft is None and ("content" in delta) and delta["content"]:
                    ttft = time.time() - t_send
                    
                if "content" in delta:
                    generated_tokens += 1
            except:
                pass
                
    duration = time.time() - t_send
    decode_speed = generated_tokens / (duration - ttft) if (duration - ttft) > 0 else 0
    print(f"[Agent {agent_id:02d}] Completed! TTFT: {ttft:.3f}s | Decode: {decode_speed:.1f} tok/s | Total Time: {duration:.2f}s | Tokens generated: {generated_tokens}")
    
    return {
        "agent_id": agent_id,
        "rag_latency": rag_latency,
        "approx_context_tokens": approx_tokens,
        "ttft": ttft,
        "decode_speed": decode_speed,
        "duration": duration,
        "tokens_generated": generated_tokens
    }

async def run_stress_test(concurrency=16):
    print("==========================================================")
    print(f"    RUNNING 16-AGENT CONCURRENT RAG CONCURRENCY TEST    ")
    print("==========================================================")
    
    # Check if Milvus collection has entries
    try:
        res = requests.post(f"{MILVUS_URL}/v2/vectordb/collections/describe", json={"collectionName": "agent_memories"})
        res.raise_for_status()
        desc = res.json()
        print(f"[Milvus] Collection verified active. Vector Dimension: {desc.get('data', {}).get('vectorFields', [{}])[0].get('dimension')}")
    except Exception as e:
        print(f"[Error] Failed to connect to Milvus or verify collection: {e}")
        return

    # Create client session with custom timeout and limits
    connector = aiohttp.TCPConnector(limit=100)
    timeout = aiohttp.ClientTimeout(total=300)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        t_start = time.time()
        
        # Spawn all agents concurrently
        tasks = [simulate_agent(i, session) for i in range(concurrency)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - t_start
        print("\n==========================================================")
        print("                 STRESS TEST RESULTS SUMMARY              ")
        print("==========================================================")
        
        successful_runs = []
        for r in results:
            if isinstance(r, Exception):
                print(f"Worker failed with error: {r}")
            else:
                successful_runs.append(r)
                
        if not successful_runs:
            print("All agents failed.")
            return
            
        avg_rag = sum(r["rag_latency"] for r in successful_runs) / len(successful_runs)
        avg_context = sum(r["approx_context_tokens"] for r in successful_runs) / len(successful_runs)
        avg_ttft = sum(r["ttft"] for r in successful_runs) / len(successful_runs)
        avg_decode = sum(r["decode_speed"] for r in successful_runs) / len(successful_runs)
        total_tokens_gen = sum(r["tokens_generated"] for r in successful_runs)
        system_throughput = total_tokens_gen / total_time
        
        print(f"Successful Agents: {len(successful_runs)}/{concurrency}")
        print(f"Average Milvus Search Latency: {avg_rag:.3f} seconds")
        print(f"Average Active Context per Agent: {avg_context:.0f} tokens")
        print(f"Total Concurrently Handled Context: {avg_context * len(successful_runs) / 1000:.1f}k tokens")
        print(f"Average Time to First Token (TTFT): {avg_ttft:.3f} seconds")
        print(f"Average Decode Speed (per agent): {avg_decode:.1f} tokens/sec")
        print(f"Total System Decode Throughput: {system_throughput:.1f} tokens/sec")
        print(f"Total Test Wall-Clock Duration: {total_time:.2f} seconds")
        print("==========================================================\n")

if __name__ == "__main__":
    asyncio.run(run_stress_test(16))
