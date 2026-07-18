import os
import sys
import json
import time
import requests
import random

# Direct vLLM server endpoint (bypassing proxy to allow pure hardware context sweep up to 120k)
VLLM_URL = "http://localhost:29999/v1/chat/completions"
MODEL_NAME = "Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4"

# Dummy paragraphs to fill the haystack (approx 150 tokens each)
FILLER_TEXTS = [
    "The thermal subsystem on the workstation PC is configured with a closed-loop liquid cooler and active PWM fan curves. Under peak compute cycles, the coolant flow rate is maintained at 2.5 liters per minute. Exhaust vents must remain unobstructed to prevent local hot spots and heat pocket accumulation inside the chassis.",
    "A PCIe Gen 5 expansion slot is allocated for host-to-device direct memory access (DMA) transfers. The high-speed interconnect supports up to 32 gigatransfers per second per lane, facilitating low-latency page swaps between host system memory and GPU VRAM.",
    "The firmware controller implements an automated power throttling protocol that dynamically monitors VRM temperatures. If the temperature exceeds 85 degrees Celsius, the clock frequency is automatically scaled down in 50MHz increments until thermal equilibrium is restored.",
    "The Vulkan API compute queue handles asynchronous dispatch operations. Shader modules are compiled to SPIR-V binaries and optimized for parallel pipeline execution. Memory buffers are bound using storage buffers with host-visible and device-local memory properties.",
    "The system monitoring daemon logs workstation diagnostics, including CPU core temperatures, fan RPM speeds, rail voltages, and storage drive read-write latency metrics. These telemetry data streams are buffered in ring memory structures and serialized periodically."
]

def estimate_tokens(text: str) -> int:
    return len(text) // 4

def generate_haystack(target_tokens: int, needle: str, depth_percent: float) -> str:
    # Estimate tokens in needle
    needle_tokens = estimate_tokens(needle)
    
    # Generate filler paragraphs to hit target length
    filler_pool = []
    current_tokens = 0
    while current_tokens < target_tokens - needle_tokens:
        p = random.choice(FILLER_TEXTS)
        filler_pool.append(p)
        current_tokens += estimate_tokens(p)
        
    # Find insertion index based on depth percentage
    num_paragraphs = len(filler_pool)
    insertion_idx = int(num_paragraphs * (depth_percent / 100.0))
    insertion_idx = max(0, min(insertion_idx, num_paragraphs))
    
    # Insert needle
    filler_pool.insert(insertion_idx, needle)
    
    # Reassemble
    haystack = "\n\n".join(filler_pool)
    return haystack

def evaluate_needle_recall(context_size: int, depth_percent: float) -> dict:
    needle = "The secret code for the antigravity containment field is: 'containment-auth-key-8899-alpha'."
    question = "What is the secret code for the antigravity containment field?"
    
    # Build prompt
    haystack = generate_haystack(context_size, needle, depth_percent)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Answer the user question based solely on the context provided. Do not invent any facts."},
        {"role": "user", "content": f"Context:\n{haystack}\n\nQuestion: {question}"}
    ]
    
    actual_tokens = sum(estimate_tokens(m["content"]) for m in messages)
    print(f"  Testing context size: {context_size:,} tokens (actual estimated: {actual_tokens:,} tokens) | Insertion depth: {depth_percent}%...")
    
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 128
    }
    
    t0 = time.time()
    try:
        res = requests.post(VLLM_URL, json=payload, timeout=240)
        res.raise_for_status()
        resp = res.json()
        latency = time.time() - t0
        
        answer = resp["choices"][0]["message"]["content"]
        prompt_tokens_reported = resp.get("usage", {}).get("prompt_tokens", 0)
        
        # Check if the secret key is in the answer
        success = "containment-auth-key-8899-alpha" in answer
        
        print(f"    Completed in {latency:.2f}s | Reported Prompt Tokens: {prompt_tokens_reported} | Recall Success: {success}")
        return {
            "status": "success",
            "success": success,
            "latency": latency,
            "prompt_tokens_reported": prompt_tokens_reported,
            "answer": answer
        }
    except Exception as e:
        latency = time.time() - t0
        print(f"    Error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "latency": latency
        }

def main():
    print("==========================================================")
    print("      NEEDLE-IN-A-HAYSTACK (NIAH) SWEEP ENGINE           ")
    print("==========================================================")
    
    # Sweeping from 10k to 120k at 10k increments
    context_sizes = [10000 * i for i in range(1, 13)]
    # Insertion depths
    depths = [10.0, 50.0, 90.0]
    
    results = {}
    
    # Run sweep
    for size in context_sizes:
        results[size] = {}
        for depth in depths:
            res = evaluate_needle_recall(size, depth)
            results[size][depth] = res
            time.sleep(1) # Let server breathe
            
    # Generate Markdown report
    print("\n==========================================================")
    print("                    NIAH SWEEP RESULTS                    ")
    print("==========================================================")
    
    report_lines = [
        "# Needle-in-a-Haystack (NIAH) Hardware Context Sweep Report\n",
        "## Setup & Configuration",
        f"- **Model Under Test:** `{MODEL_NAME}`",
        "- **Target Context Range:** 10,000 to 120,000 tokens (10k increments)",
        "- **Insertion Depths:** 10% (Beginning), 50% (Middle), 90% (End)",
        "- **Evaluation Needle:** `containment-auth-key-8899-alpha`\n",
        "## Recall Accuracy Matrix\n",
        "| Context Size (Tokens) | Depth: 10% (Beginning) | Depth: 50% (Middle) | Depth: 90% (End) |",
        "| :--- | :--- | :--- | :--- |"
    ]
    
    anomalies = []
    
    for size in context_sizes:
        row_cells = [f"{size:,}"]
        for depth in depths:
            res = results[size][depth]
            if res["status"] == "success":
                icon = "🟢 Pass" if res["success"] else "🔴 Fail"
                row_cells.append(f"{icon} ({res['latency']:.1f}s)")
                if not res["success"]:
                    anomalies.append(f"- Context Size {size:,} at {depth}% depth failed to retrieve the needle. Model response: *{res['answer'].strip()}*")
            else:
                row_cells.append("💥 Error")
                anomalies.append(f"- Context Size {size:,} at {depth}% depth threw an error: {res.get('error')}")
        report_lines.append("| " + " | ".join(row_cells) + " |")
        
    report_lines.append("\n## Precision Degradation & Safety Margin Analysis\n")
    if not anomalies:
        report_lines.append("No recall degradation or precision drops were identified! The model demonstrated 100% retrieval accuracy across the entire hardware range of 10,000 to 120,000 tokens.")
        report_lines.append("\n**Safety Margin Recommendation:** The physical context ceiling of 120K tokens is highly stable. We can confidently use a safety margin of up to 110K tokens for raw prompt size if needed.")
    else:
        report_lines.append("### Identified Degradation Points & Anomalies\n")
        report_lines.extend(anomalies)
        report_lines.append("\n### Safety Margin & RAG Payload Recommendation\n")
        # Identify first failure point
        failure_point = None
        for size in context_sizes:
            for depth in depths:
                if results[size][depth]["status"] != "success" or not results[size][depth]["success"]:
                    failure_point = size
                    break
            if failure_point:
                break
                
        if failure_point:
            report_lines.append(f"Precision degradation starts at **{failure_point:,}** tokens context size.")
            report_lines.append(f"Based on these findings, we recommend setting a safety margin of **{failure_point - 10000:,}** tokens for the active context window, and utilizing the RAG pipeline to keep context payloads below this size.")
        else:
            report_lines.append("Anomalies were observed. Safety margins should be adjusted to limit prompt context to 80K tokens.")
            
    report = "\n".join(report_lines)
    print(report)
    
    # Save the report
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "niah_sweep_report.md"))
    with open(report_path, "w") as f:
        f.write(report)
        f.write("\n")
        
    print(f"\nNIAH Report saved to {report_path}")

if __name__ == "__main__":
    main()
