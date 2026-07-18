#!/usr/bin/env python3
import os
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"
os.environ["VECLIB_MAXIMUM_THREADS"] = "4"
os.environ["NUMEXPR_NUM_THREADS"] = "4"

import sys
import time
import json
import subprocess
import threading
import requests
import psutil
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

# Config
REPO_DIR = "/home/theworks/.gemini/antigravity/scratch/mcp-rag-outlook/scratch/requests_repo/src/requests"
BGE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
NOMIC_API_URL = "http://localhost:8080/v1/embeddings"
NOMIC_TOKENIZE_URL = "http://localhost:8080/tokenize"
NUM_CHUNKS_TO_TEST = 256

class ResourceMonitor:
    def __init__(self, interval=1.0):
        self.interval = interval
        self.samples = []
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.samples = []
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._monitor)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()

    def _monitor(self):
        # We trigger an initial cpu_percent call to establish a baseline
        psutil.cpu_percent(interval=None)
        while not self.stop_event.is_set():
            cpu_usage = psutil.cpu_percent(interval=None)
            gpu_stats = self._get_gpu_stats()
            self.samples.append({
                "cpu": cpu_usage,
                "gpu": gpu_stats
            })
            time.sleep(self.interval)

    def _get_gpu_stats(self):
        stats = {}
        try:
            output = subprocess.check_output(["rocm-smi"], stderr=subprocess.DEVNULL).decode("utf-8")
            lines = output.strip().split("\n")
            for line in lines:
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0].isdigit():
                    dev_id = int(parts[0])
                    gpu_util = float(parts[-1].replace("%", "")) if "%" in parts[-1] else 0.0
                    vram_util = float(parts[-2].replace("%", "")) if "%" in parts[-2] else 0.0
                    stats[dev_id] = {
                        "gpu_util": gpu_util,
                        "vram_util": vram_util
                    }
        except Exception:
            pass
        return stats

    def get_summary(self):
        if not self.samples:
            return {
                "cpu_avg": 0.0, "cpu_peak": 0.0,
                "gpu0_avg": 0.0, "gpu0_peak": 0.0, "vram0_avg": 0.0, "vram0_peak": 0.0,
                "gpu1_avg": 0.0, "gpu1_peak": 0.0, "vram1_avg": 0.0, "vram1_peak": 0.0,
            }
        
        cpus = [s["cpu"] for s in self.samples]
        summary = {
            "cpu_avg": sum(cpus) / len(cpus),
            "cpu_peak": max(cpus),
        }
        
        gpu0_utils = []
        gpu0_vrams = []
        gpu1_utils = []
        gpu1_vrams = []
        
        for s in self.samples:
            gstats = s["gpu"]
            if 0 in gstats:
                gpu0_utils.append(gstats[0]["gpu_util"])
                gpu0_vrams.append(gstats[0]["vram_util"])
            if 1 in gstats:
                gpu1_utils.append(gstats[1]["gpu_util"])
                gpu1_vrams.append(gstats[1]["vram_util"])
                
        summary["gpu0_avg"] = sum(gpu0_utils) / len(gpu0_utils) if gpu0_utils else 0.0
        summary["gpu0_peak"] = max(gpu0_utils) if gpu0_utils else 0.0
        summary["vram0_avg"] = sum(gpu0_vrams) / len(gpu0_vrams) if gpu0_vrams else 0.0
        summary["vram0_peak"] = max(gpu0_vrams) if gpu0_vrams else 0.0
        
        summary["gpu1_avg"] = sum(gpu1_utils) / len(gpu1_utils) if gpu1_utils else 0.0
        summary["gpu1_peak"] = max(gpu1_utils) if gpu1_utils else 0.0
        summary["vram1_avg"] = sum(gpu1_vrams) / len(gpu1_vrams) if gpu1_vrams else 0.0
        summary["vram1_peak"] = max(gpu1_vrams) if gpu1_vrams else 0.0
        
        return summary


def get_py_files(directory):
    py_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    return py_files


def chunk_file(file_path, base_dir, chunk_size=30, overlap=10):
    rel_path = os.path.relpath(file_path, base_dir)
    chunks = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    total_lines = len(lines)
    start = 0
    while start < total_lines:
        end = min(start + chunk_size, total_lines)
        chunk_lines = lines[start:end]
        code_content = "".join(chunk_lines)
        
        chunk_text = f"File: {rel_path} (Lines {start+1}-{end})\n\n```python\n{code_content}```"
        chunks.append(chunk_text)
        
        start += (chunk_size - overlap)
        if start >= total_lines or end == total_lines:
            break
            
    return chunks


def load_chunks():
    print(f"Scanning codebase files at: {REPO_DIR}...")
    py_files = get_py_files(REPO_DIR)
    all_chunks = []
    for f in py_files:
        all_chunks.extend(chunk_file(f, os.path.dirname(REPO_DIR)))
    
    # We slice to exactly NUM_CHUNKS_TO_TEST
    if len(all_chunks) < NUM_CHUNKS_TO_TEST:
        raise ValueError(f"Found only {len(all_chunks)} chunks, but we need at least {NUM_CHUNKS_TO_TEST}.")
    
    selected_chunks = all_chunks[:NUM_CHUNKS_TO_TEST]
    print(f"Successfully loaded and sliced to {len(selected_chunks)} codebase chunks.")
    return selected_chunks


def main():
    print("=== Embedding Engines Performance Benchmark ===")
    
    # 1. Load the codebase chunks
    try:
        chunks = load_chunks()
    except Exception as e:
        print(f"Error loading chunks: {e}")
        sys.exit(1)
        
    # Initialize monitor
    monitor = ResourceMonitor(interval=0.1)
    
    # Results data structure
    results = {}
    
    # Load BGE local components
    print("Loading BGE model...")
    bge_model = SentenceTransformer(BGE_MODEL_NAME, device="cpu")
    bge_tokenizer = AutoTokenizer.from_pretrained(BGE_MODEL_NAME)
    
    # Truncate chunks to a max of 512 tokens to prevent index errors
    truncated_chunks = []
    for c in chunks:
        tokens = bge_tokenizer.encode(c, max_length=512, truncation=True)
        truncated_chunks.append(bge_tokenizer.decode(tokens, skip_special_tokens=True))
    chunks = truncated_chunks
    
    # Calculate tokens for BGE
    print("Calculating BGE token counts...")
    bge_tokens = [len(bge_tokenizer.encode(c)) for c in chunks]
    total_bge_tokens = sum(bge_tokens)
    print(f"Total BGE tokens: {total_bge_tokens} (Avg: {total_bge_tokens/NUM_CHUNKS_TO_TEST:.1f} per chunk)")
    
    # Set up HTTP session for Nomic Vulkan API
    http_session = requests.Session()
    
    # Warmup Nomic Vulkan Tokenizer and API
    print("Warming up Nomic Vulkan server and calculating tokens...")
    nomic_tokens = []
    for chunk in chunks:
        # We can query tokenize API to get precise nomic tokens
        try:
            r = http_session.post(NOMIC_TOKENIZE_URL, json={"content": chunk})
            r.raise_for_status()
            nomic_tokens.append(len(r.json().get("tokens", [])))
        except Exception as e:
            # Fallback to word-based count estimate in case of API failure
            nomic_tokens.append(len(chunk.split()))
            
    total_nomic_tokens = sum(nomic_tokens)
    print(f"Total Nomic tokens: {total_nomic_tokens} (Avg: {total_nomic_tokens/NUM_CHUNKS_TO_TEST:.1f} per chunk)")
    
    # Warmup runs
    print("Running warmups...")
    bge_model.encode(["Warmup text 1", "Warmup text 2"])
    try:
        http_session.post(NOMIC_API_URL, json={"model": "nomic-embed-text-v1.5", "input": ["Warmup text 1", "Warmup text 2"]})
    except Exception as e:
        print(f"Error warming up Nomic server: {e}")
        
    # --- BENCHMARKING BGE ON CPU ---
    print("\n--- Benchmarking BGE on CPU ---")
    
    # Sequential (Batch size 1)
    print("BGE Sequential...")
    monitor.start()
    start_time = time.time()
    bge_model.encode(chunks, batch_size=1)
    total_time = time.time() - start_time
    monitor.stop()
    res_summary = monitor.get_summary()
    
    avg_lat = (total_time / NUM_CHUNKS_TO_TEST) * 1000.0
    results["BGE_seq"] = {
        "avg_req_latency": avg_lat,
        "p95_req_latency": avg_lat,
        "avg_chunk_latency": avg_lat,
        "throughput_tokens": total_bge_tokens / total_time,
        "throughput_chunks": NUM_CHUNKS_TO_TEST / total_time,
        "total_time": total_time,
        **res_summary
    }
    
    # Batch scales
    for b_size in [8, 32, 128]:
        print(f"BGE Batch size {b_size}...")
        monitor.start()
        start_time = time.time()
        bge_model.encode(chunks, batch_size=b_size)
        total_time = time.time() - start_time
        monitor.stop()
        res_summary = monitor.get_summary()
        
        num_batches = NUM_CHUNKS_TO_TEST / b_size
        avg_req_lat = (total_time / num_batches) * 1000.0
        
        results[f"BGE_batch_{b_size}"] = {
            "avg_req_latency": avg_req_lat,
            "p95_req_latency": avg_req_lat,
            "avg_chunk_latency": (total_time / NUM_CHUNKS_TO_TEST) * 1000.0,
            "throughput_tokens": total_bge_tokens / total_time,
            "throughput_chunks": NUM_CHUNKS_TO_TEST / total_time,
            "total_time": total_time,
            **res_summary
        }
        
    # --- BENCHMARKING NOMIC ON VULKAN ---
    print("\n--- Benchmarking Nomic on Vulkan ---")
    
    # Sequential (Batch size 1)
    print("Nomic Sequential...")
    nomic_seq_latencies = []
    monitor.start()
    start_time = time.time()
    for chunk in chunks:
        req_start = time.time()
        response = http_session.post(NOMIC_API_URL, json={
            "model": "nomic-embed-text-v1.5",
            "input": chunk
        })
        response.raise_for_status()
        nomic_seq_latencies.append((time.time() - req_start) * 1000.0)
    total_time = time.time() - start_time
    monitor.stop()
    res_summary = monitor.get_summary()
    
    results["Nomic_seq"] = {
        "avg_req_latency": np.mean(nomic_seq_latencies),
        "p95_req_latency": np.percentile(nomic_seq_latencies, 95),
        "avg_chunk_latency": np.mean(nomic_seq_latencies),
        "throughput_tokens": total_nomic_tokens / total_time,
        "throughput_chunks": NUM_CHUNKS_TO_TEST / total_time,
        "total_time": total_time,
        **res_summary
    }
    
    # Batch scales
    for b_size in [8, 32, 128]:
        print(f"Nomic Batch size {b_size}...")
        nomic_batch_latencies = []
        monitor.start()
        start_time = time.time()
        for i in range(0, NUM_CHUNKS_TO_TEST, b_size):
            batch = chunks[i:i+b_size]
            req_start = time.time()
            response = http_session.post(NOMIC_API_URL, json={
                "model": "nomic-embed-text-v1.5",
                "input": batch
            })
            response.raise_for_status()
            nomic_batch_latencies.append((time.time() - req_start) * 1000.0)
        total_time = time.time() - start_time
        monitor.stop()
        res_summary = monitor.get_summary()
        
        results[f"Nomic_batch_{b_size}"] = {
            "avg_req_latency": np.mean(nomic_batch_latencies),
            "p95_req_latency": np.percentile(nomic_batch_latencies, 95),
            "avg_chunk_latency": (total_time / NUM_CHUNKS_TO_TEST) * 1000.0,
            "throughput_tokens": total_nomic_tokens / total_time,
            "throughput_chunks": NUM_CHUNKS_TO_TEST / total_time,
            "total_time": total_time,
            **res_summary
        }
        
    # Save raw results
    results_file = "/home/theworks/.gemini/antigravity/scratch/mcp-rag-outlook/scratch/benchmark_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved raw results to: {results_file}")
    
    # Print formatted output table
    print("\nBenchmark Summary Table:")
    print(f"{'Engine & Scenario':<22} | {'Avg Req Lat (ms)':<16} | {'p95 Req Lat (ms)':<16} | {'Avg Chunk Lat (ms)':<18} | {'Throughput (tok/s)':<19} | {'CPU Avg/Peak':<13} | {'GPU0/1 Avg Util':<15}")
    print("-" * 135)
    for name, data in results.items():
        engine_scenario = name
        avg_req = f"{data['avg_req_latency']:.2f}"
        p95_req = f"{data['p95_req_latency']:.2f}"
        avg_chunk = f"{data['avg_chunk_latency']:.2f}"
        tok_sec = f"{data['throughput_tokens']:.2f}"
        cpu_str = f"{data['cpu_avg']:.1f}%/{data['cpu_peak']:.1f}%"
        gpu_str = f"{data['gpu0_avg']:.1f}% / {data['gpu1_avg']:.1f}%"
        print(f"{engine_scenario:<22} | {avg_req:<16} | {p95_req:<16} | {avg_chunk:<18} | {tok_sec:<19} | {cpu_str:<13} | {gpu_str:<15}")


if __name__ == "__main__":
    main()
