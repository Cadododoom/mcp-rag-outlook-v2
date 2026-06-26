import requests
import json
import time

PROXY_URL = "http://localhost:30000/v1/chat/completions"
HEADERS = {
    "Authorization": "Bearer vllm-5060ti-token",
    "Content-Type": "application/json"
}

def main():
    print("Testing proxy context truncation and warning injection...")
    
    # Create a system message (essential)
    system_msg = {"role": "system", "content": "You are a helpful assistant."}
    
    # Create a very old user message that we want to get truncated
    # 15,000 tokens is about 60,000 characters
    large_old_content = "X" * 60000 # ~15,000 tokens
    old_msg = {"role": "user", "content": f"Old context: {large_old_content}"}
    
    # Create a recent user query
    recent_msg = {"role": "user", "content": "What is 2+2?"}
    
    # Reassemble: system, large old context, recent query
    messages = [system_msg, old_msg, recent_msg]
    
    payload = {
        "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 10
    }
    
    print("Sending payload with large history (>25k tokens)...")
    t0 = time.time()
    r = requests.post(PROXY_URL, json=payload, headers=HEADERS)
    print(f"Status Code: {r.status_code}")
    print(f"Time Taken: {time.time() - t0:.2f} seconds")
    
    if r.status_code != 200:
        print(f"Error Response: {r.text}")
        return
        
    res = r.json()
    print("Response keys:", res.keys())
    
    # Verify usage metrics
    usage = res.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    print(f"Prompt tokens reported by vLLM: {prompt_tokens}")
    
    # The proxy limit is 10,000 tokens. The prompt_tokens must be <= 10,000 tokens plus a small delta,
    # and definitely less than the 15,000+ tokens we sent (which would have been ~15,000 + 10 = ~15,010 tokens).
    print(f"Is prompt truncated? {prompt_tokens < 11000}")
    assert prompt_tokens < 11000, f"Expected prompt to be truncated below 11,000 tokens, got {prompt_tokens}"
    
    print("=== Truncation Test PASSED! ===")

if __name__ == "__main__":
    main()
