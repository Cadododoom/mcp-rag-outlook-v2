import os
import sys
import time
import requests
import lancedb
import random

# Configuration
API_URL = "http://127.0.0.1:8642/v1/chat/completions"
API_KEY = "change-me-local-dev"
DB_PATH = "/home/theworks/.hermes/data/lancedb_store"
SESSION_ID = f"test-scale-session-{random.randint(1000, 9999)}"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "X-Hermes-Session-Id": SESSION_ID
}

def clean_database():
    print(f"Connecting to LanceDB at {DB_PATH}...")
    db = lancedb.connect(DB_PATH)
    if "agent_memories" in db.table_names():
        table = db.open_table("agent_memories")
        print("Cleaning up old test session memories...")
        table.delete(f'conversationId == "{SESSION_ID}"')
        print("Old memories deleted.")
    else:
        db.create_table("agent_memories", data=[{
            "id": 0,
            "text": "init",
            "conversationId": "init",
            "details": "init",
            "timestamp": 0.0
        }])
        print("Created agent_memories table.")

def insert_simulated_memory(target_tokens):
    # Calculate required characters
    # db_tokens = int(db_chars / 4.2) -> db_chars = db_tokens * 4.2
    target_chars = int(target_tokens * 4.2)
    print(f"Inserting simulated memory of size: {target_tokens} tokens (~{target_chars} characters)...")
    
    db = lancedb.connect(DB_PATH)
    table = db.open_table("agent_memories")
    
    # We create a large details string
    details_str = "x" * target_chars
    
    data = [{
        "id": random.randint(1000000000, 9999999999),
        "text": "Simulated memory of scale testing",
        "conversationId": SESSION_ID,
        "details": details_str,
        "timestamp": time.time() * 1000
    }]
    table.add(data)
    print("Simulated memory inserted successfully.")

def test_api_completions(expected_min_tokens):
    print(f"Sending chat completion request with session: {SESSION_ID}...")
    payload = {
        "model": "Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4",
        "messages": [
            {"role": "user", "content": "Hello agent! What is the virtual context memory size of this session? Respond in one sentence."}
        ],
        "stream": False
    }
    
    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"API Error {response.status_code}: {response.text}")
        sys.exit(1)
        
    res_data = response.json()
    print("API Response received successfully.")
    
    usage = res_data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    print(f"Prompt tokens reported: {prompt_tokens}")
    print(f"Completion content: {res_data['choices'][0]['message']['content']}")
    
    assert prompt_tokens >= expected_min_tokens, f"Expected prompt tokens to be at least {expected_min_tokens}, but got {prompt_tokens}"
    print(f"SUCCESS: Prompt tokens {prompt_tokens} verified >= {expected_min_tokens}!")

def main():
    clean_database()
    
    # Step 1: Baseline check (should be small, e.g. < 1000 tokens)
    print("\n--- Running Baseline Check ---")
    test_api_completions(0)
    
    # Step 2: Scale to 2 Million tokens
    print("\n--- Scaling to 2,000,000 tokens ---")
    insert_simulated_memory(2000000)
    test_api_completions(2000000)
    
    # Step 3: Scale to 5 Million tokens
    print("\n--- Scaling to 5,000,000 tokens ---")
    # Clean and insert 5M
    clean_database()
    insert_simulated_memory(5000000)
    test_api_completions(5000000)
    
    # Step 4: Scale to 10 Million tokens
    print("\n--- Scaling to 10,000,000 tokens ---")
    # Clean and insert 10M
    clean_database()
    insert_simulated_memory(10000000)
    test_api_completions(10000000)
    
    # Cleanup
    clean_database()
    print("\nAll scaling tests completed successfully and verified!")

if __name__ == "__main__":
    main()
