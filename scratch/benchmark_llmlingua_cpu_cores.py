import os
import sys
import time
import json
import psutil
import threading
from llmlingua import PromptCompressor

# Sample retrieved codebase chunks to compress
DUMMY_CONTEXT = [
    "class HTTPAdapter(BaseAdapter):\n    def __init__(self, pool_connections=10, pool_maxsize=10, max_retries=3):\n        self.max_retries = max_retries\n        self.poolmanager = PoolManager(num_pools=pool_connections, maxsize=pool_maxsize)",
    "def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):\n        conn = self.get_connection(request.url, proxies)\n        self.cert_verify(conn, request.url, verify, cert)\n        resp = conn.urlopen(method=request.method, url=request.url, body=request.body, headers=request.headers, retries=self.max_retries, timeout=timeout)",
    "class Session(SessionRedirectMixin):\n    def __init__(self):\n        self.headers = case_insensitive_dict()\n        self.auth = None\n        self.proxies = {}\n        self.hooks = default_hooks()\n        self.params = {}\n        self.stream = False\n        self.verify = True\n        self.cert = None\n        self.max_redirects = 30\n        self.cookies = cookiejar_from_dict({})",
    "def merge_cookies(cookiejar, cookies):\n    if not isinstance(cookiejar, cookielib.CookieJar):\n        raise ValueError('You can only merge into a CookieJar')\n    if cookies is not None:\n        if isinstance(cookies, dict):\n            cookies = cookiejar_from_dict(cookies)\n        for cookie in cookies:\n            cookiejar.set_cookie(cookie)\n    return cookiejar"
] * 10 # Expand to create a realistic larger context (~3000 tokens)

class CPUProfiler:
    def __init__(self, interval=0.05):
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
        return sum(self.cpu_percentages) / len(self.cpu_percentages), max(self.cpu_percentages)

def main():
    print("==========================================================")
    print("   LLMLINGUA-2 CPU CORE SCALING & THREAD BENCHMARK        ")
    print("==========================================================")
    
    num_cpus = os.cpu_count() or 1
    print(f"Detected {num_cpus} physical/logical CPU Cores.")
    
    # Range of threads to evaluate
    thread_configurations = [1, 2, 4, 6, 8, 12, 16, 24, 32]
    
    results = []
    
    # Initialize LLMLingua-2
    print("Initializing LLMLingua-2 compressor on CPU...")
    compressor = PromptCompressor(
        model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
        device_map="cpu",
        use_llmlingua2=True
    )
    
    # Import torch to control threads programmatically
    import torch
    
    # Warm up run
    print("Running warm-up compression...")
    compressor.compress_prompt(
        context=DUMMY_CONTEXT,
        instruction="Analyze connection retries",
        question="How does HTTPAdapter handle max_retries?",
        rate=0.33
    )
    
    profiler = CPUProfiler(interval=0.05)
    
    for num_threads in thread_configurations:
        if num_threads > num_cpus:
            continue
            
        print(f"\nEvaluating configuration: {num_threads} thread(s)...")
        
        # Apply thread count
        torch.set_num_threads(num_threads)
        
        # Measure CPU and Latency over 5 iterations
        latencies = []
        profiler.start()
        
        t0 = time.time()
        for _ in range(5):
            t_iter = time.time()
            compressor.compress_prompt(
                context=DUMMY_CONTEXT,
                instruction="Analyze connection retries",
                question="How does HTTPAdapter handle max_retries?",
                rate=0.33
            )
            latencies.append((time.time() - t_iter) * 1000) # ms
            
        total_time = (time.time() - t0) * 1000
        avg_cpu, max_cpu = profiler.stop()
        
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        
        print(f"  Avg Latency: {avg_latency:.1f} ms (Min: {min_latency:.1f} ms)")
        print(f"  CPU Usage  : Avg {avg_cpu:.1f}% | Max {max_cpu:.1f}%")
        
        results.append({
            "threads": num_threads,
            "avg_latency_ms": avg_latency,
            "min_latency_ms": min_latency,
            "avg_cpu_percent": avg_cpu,
            "max_cpu_percent": max_cpu
        })
        time.sleep(1) # cool down
        
    # Compile results into a markdown report
    report_lines = [
        "# LLMLingua-2 CPU Core Scaling Benchmark Report\n",
        "## Thread Configuration vs. Latency and CPU Overhead\n",
        "The following table summarizes the performance-to-overhead tradeoff for prompt compression on CPU:\n",
        "| CPU Threads | Avg Latency (ms) | Min Latency (ms) | Avg System CPU (%) | Max System CPU (%) | Relative Throughput |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    baseline_latency = results[0]["avg_latency_ms"]
    for r in results:
        speedup = baseline_latency / r["avg_latency_ms"]
        report_lines.append(
            f"| {r['threads']} | {r['avg_latency_ms']:.1f} | {r['min_latency_ms']:.1f} | "
            f"{r['avg_cpu_percent']:.1f}% | {r['max_cpu_percent']:.1f}% | {speedup:.2f}x |"
        )
        
    report_lines.append("\n## Architectural Recommendation")
    
    # Find the elbow point
    # We want a configuration that minimizes the product of core count and latency (or where scaling yields diminishing returns)
    optimal_threads = 4
    min_cost = float('inf')
    for r in results:
        # Core-time cost metric
        cost = r["threads"] * r["avg_latency_ms"]
        if cost < min_cost:
            min_cost = cost
            optimal_threads = r["threads"]
            
    report_lines.append(f"\nBased on the core-time cost metric (Threads * Latency), the mathematically optimal allocation is **{optimal_threads} threads**.")
    report_lines.append(f"This configuration achieves an ideal balance between low latency and low CPU utilization, preventing CPU starvation for concurrent agent runtimes.")
    
    report = "\n".join(report_lines)
    print("\n" + report + "\n")
    
    # Save the report
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "llmlingua_cpu_scaling_report.md"))
    with open(report_path, "w") as f:
        f.write(report)
        f.write("\n")
        
    print(f"Report saved to {report_path}")

if __name__ == "__main__":
    main()
