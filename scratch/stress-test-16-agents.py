import asyncio
import aiohttp
import json
import random
import time
import requests
import os
import sys

# Add skills path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../.agents/skills/lancedb-raptor-rag-engine")))
from query_edge_rag import execute_tool

VLLM_URL = "http://localhost:30000/v1/chat/completions"
CONV_ID = "rag-stress-test-conv"

# 4 target secrets that were injected during ingestion
TARGETS = [
    {"name": "AlphaCoreEngine", "query": "AlphaCoreEngine thrust authentication credentials token"},
    {"name": "QuantumVault", "query": "QuantumVault AES secure key Registry memory decryption"},
    {"name": "HyperionGateway", "query": "HyperionGateway port route certificate SSL private"},
    {"name": "NexusQueue", "query": "NexusQueue RabbitMQ connection credentials port host"}
]

async def search_memory(query, compression_rate=0.33):
    # Execute RAG retrieval and context compression using LanceDB + LLMLingua-2
    # execute_tool is blocking, so we run it in a thread pool using asyncio.to_thread
    res_str = await asyncio.to_thread(execute_tool, query, compression_rate)
    res = json.loads(res_str)
    if "error" in res:
        raise Exception(res["error"])
    return res.get("compressed_payload", "")

async def simulate_agent(agent_id, session):
    target = TARGETS[agent_id % len(TARGETS)]
    print(f"[Agent {agent_id:02d}] Starting task: Authenticating with {target['name']}...")
    
    # Step 1: Query database for context (RAG)
    t0 = time.time()
    context = await search_memory(target["query"], compression_rate=0.33)
    rag_latency = time.time() - t0
    
    # Pad context to ~120,000 tokens (approx 480,000 characters) to simulate the 120k context load
    target_chars = 120000 * 4
    if len(context) < target_chars:
        padding_needed = target_chars - len(context)
        dummy_padding_block = " This is a dummy padding block to simulate a large 120k token context window. In software engineering, maintaining a large context allows the model to reason about multiple files and dependencies simultaneously, avoiding context fragmentation."
        repeats = (padding_needed // len(dummy_padding_block)) + 1
        context += (dummy_padding_block * repeats)[:padding_needed]
        
    # Calculate approx tokens (4 characters per token average)
    context_char_len = len(context)
    approx_tokens = context_char_len // 4
    print(f"[Agent {agent_id:02d}] RAG retrieved context padded to {approx_tokens} tokens of code context in {rag_latency:.3f}s.")
    
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
        "model": "Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4",
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

async def run_stress_test(concurrency=4):
    print("==========================================================")
    print(f"    RUNNING 4-AGENT CONCURRENT RAG CONCURRENCY TEST     ")
    print("==========================================================")
    
    # Check if LanceDB table exists
    try:
        db_path = "./data/lancedb_store"
        if not os.path.exists(db_path):
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.agents/skills/lancedb-raptor-rag-engine/../../../data/lancedb_store"))
        import lancedb
        db = lancedb.connect(db_path)
        if "raptor_collapsed_index" in db.table_names():
            print(f"[LanceDB] Table 'raptor_collapsed_index' verified active.")
        else:
            print(f"[Error] LanceDB table 'raptor_collapsed_index' not found.")
            return
    except Exception as e:
        print(f"[Error] Failed to connect to LanceDB: {e}")
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
        print(f"Average LanceDB Search & Compression Latency: {avg_rag:.3f} seconds")
        print(f"Average Active Context per Agent: {avg_context:.0f} tokens")
        print(f"Total Concurrently Handled Context: {avg_context * len(successful_runs) / 1000:.1f}k tokens")
        print(f"Average Time to First Token (TTFT): {avg_ttft:.3f} seconds")
        print(f"Average Decode Speed (per agent): {avg_decode:.1f} tokens/sec")
        print(f"Total System Decode Throughput: {system_throughput:.1f} tokens/sec")
        print(f"Total Test Wall-Clock Duration: {total_time:.2f} seconds")
        print("==========================================================\n")

if __name__ == "__main__":
    asyncio.run(run_stress_test(4))
