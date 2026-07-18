import os
import sys
import json
import time
import requests
import psutil
import threading

# Add skills path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../.agents/skills/lancedb-raptor-rag-engine")))
from query_edge_rag import execute_tool

VLLM_URL = "http://localhost:30000/v1/chat/completions"
MODEL_NAME = "Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4"

# Thread to measure CPU utilization in the background during execution
class CPUProfiler:
    def __init__(self, interval=0.1):
        self.interval = interval
        self.cpu_percentages = []
        self._running = False
        self._thread = None

    def start(self):
        self.cpu_percentages = []
        self._running = True
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()

    def _run(self):
        # Establish base reference
        psutil.cpu_percent(interval=None)
        while self._running:
            self.cpu_percentages.append(psutil.cpu_percent(interval=None))
            time.sleep(self.interval)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        if not self.cpu_percentages:
            return 0.0, 0.0
        avg_cpu = sum(self.cpu_percentages) / len(self.cpu_percentages)
        max_cpu = max(self.cpu_percentages)
        return avg_cpu, max_cpu

def run_rag_and_generate(query: str):
    print(f"\n==========================================================")
    print(f"QUERY: '{query}'")
    print(f"==========================================================")
    
    profiler = CPUProfiler(interval=0.1)
    
    # 1. Execute RAG Reranking & Prompt Compression
    print("Running RAG Retrieval & Prompt Compression...")
    profiler.start()
    t0 = time.time()
    
    rag_res_str = execute_tool(query, compression_rate=0.33)
    
    rag_latency = time.time() - t0
    avg_cpu_rag, max_cpu_rag = profiler.stop()
    
    try:
        rag_res = json.loads(rag_res_str)
        retrieved_context = rag_res.get("compressed_payload", "")
        meta = rag_res.get("metadata", {})
        original_tokens = meta.get("original_tokens", 0)
        compressed_tokens = meta.get("compressed_tokens", 0)
        saving_ratio = meta.get("saving_ratio", "N/A")
    except Exception as e:
        print(f"Error parsing RAG result: {e}")
        retrieved_context = ""
        original_tokens, compressed_tokens, saving_ratio = 0, 0, "Error"
        
    print(f"RAG Latency: {rag_latency:.3f} seconds")
    print(f"RAG CPU Usage -> Avg: {avg_cpu_rag:.1f}%, Max: {max_cpu_rag:.1f}%")
    print(f"Tokens -> Original: {original_tokens}, Compressed: {compressed_tokens} ({saving_ratio})")
    
    # 2. Query vLLM
    print("\nSending prompt to local vLLM model...")
    system_prompt = (
        "You are an expert Python developer with access to the requests codebase RAG context. "
        "Use the retrieved code chunks below to answer the user's question accurately."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"RAG Context:\n{retrieved_context}\n\nQuestion: {query}"}
    ]
    
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 3000
    }
    
    profiler.start()
    t1 = time.time()
    
    try:
        res = requests.post(VLLM_URL, json=payload, timeout=300)
        res.raise_for_status()
        resp = res.json()
        generation_latency = time.time() - t1
        avg_cpu_gen, max_cpu_gen = profiler.stop()
        
        answer = resp["choices"][0]["message"]["content"]
        prompt_tokens = resp.get("usage", {}).get("prompt_tokens", 0)
        completion_tokens = resp.get("usage", {}).get("completion_tokens", 0)
    except Exception as e:
        generation_latency = time.time() - t1
        avg_cpu_gen, max_cpu_gen = profiler.stop()
        answer = f"Error calling vLLM: {e}"
        prompt_tokens, completion_tokens = 0, 0
        
    print(f"Generation Latency: {generation_latency:.3f} seconds")
    print(f"Generation CPU Usage -> Avg: {avg_cpu_gen:.1f}%, Max: {max_cpu_gen:.1f}%")
    print(f"Token usage -> Prompt: {prompt_tokens}, Completion: {completion_tokens}")
    print(f"\nModel Answer:\n{answer}\n")
    
    return {
        "query": query,
        "rag_latency": rag_latency,
        "rag_avg_cpu": avg_cpu_rag,
        "rag_max_cpu": max_cpu_rag,
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "saving_ratio": saving_ratio,
        "generation_latency": generation_latency,
        "gen_avg_cpu": avg_cpu_gen,
        "gen_max_cpu": max_cpu_gen,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "answer": answer
    }

def main():
    print("==========================================================")
    # Check physical hardware details
    num_cpus = os.cpu_count() or 1
    total_mem_gb = psutil.virtual_memory().total / (1024 ** 3)
    print(f"System Configuration: {num_cpus} CPU Cores | {total_mem_gb:.2f} GB RAM")
    print("==========================================================")
    
    queries = [
        "How is connection retrying configured and handled in HTTPAdapter?",
        "What is the structure of Session.request and how does it merge cookies?",
        "Where is the PreparedRequest class defined, and what does its prepare_auth method do?"
    ]
    
    results = []
    for q in queries:
        res = run_rag_and_generate(q)
        results.append(res)
        # Sleep to let CPU settle
        time.sleep(2)
        
    # Write a summary report
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "real_world_perf_report.md"))
    with open(report_path, "w") as f:
        f.write("# Real-World Performance & Resource Evaluation Report\n\n")
        f.write(f"**System Specs:** {num_cpus} Cores, {total_mem_gb:.2f} GB RAM\n\n")
        f.write("## Resource Consumption & Latency Metrics\n\n")
        f.write("| Query | RAG Latency (s) | RAG Avg CPU (%) | RAG Max CPU (%) | Original Context (tokens) | Compressed Context (tokens) | Compression Ratio | Gen Latency (s) | Gen Avg CPU (%) | Prompt Tokens | Completion Tokens |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            f.write(
                f"| {r['query']} | {r['rag_latency']:.2f} | {r['rag_avg_cpu']:.1f}% | {r['rag_max_cpu']:.1f}% | "
                f"{r['original_tokens']} | {r['compressed_tokens']} | {r['saving_ratio']} | "
                f"{r['generation_latency']:.2f} | {r['gen_avg_cpu']:.1f}% | {r['prompt_tokens']} | {r['completion_tokens']} |\n"
            )
        f.write("\n## Qualitative Output Assessment\n\n")
        for r in results:
            f.write(f"### Query: *{r['query']}*\n\n")
            f.write(f"**Answer:**\n\n{r['answer']}\n\n")
            f.write("---\n\n")
            
    print(f"\nEvaluation complete. Report saved to {report_path}")

if __name__ == "__main__":
    main()
