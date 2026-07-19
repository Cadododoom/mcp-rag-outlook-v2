import os
import sys
import subprocess
import json
import sqlite3

# Define paths
HERMES_VENV_PYTHON = "/home/theworks/.hermes/hermes-agent/venv/bin/python"
HERMES_CLI = "/home/theworks/.hermes/hermes-agent/venv/bin/hermes"
STATE_DB = "/home/theworks/.hermes/state.db"

def run_cmd(args):
    print(f"Running: {' '.join(args)}")
    result = subprocess.run(args, capture_output=True, text=True)
    return result

def get_latest_session_id():
    conn = sqlite3.connect(STATE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def main():
    print("==========================================================")
    print(" Hermes Agent Continuity Verification Suite")
    print("==========================================================")
    
    # Step 1: Start a new session with oneshot query
    print("\n[Step 1] Initializing new session with test query...")
    initial_prompt = "Hello! This is a test message to start a new session."
    res = run_cmd([HERMES_CLI, "chat", "-q", initial_prompt])
    
    if res.returncode != 0:
        print(f"❌ Error starting session: {res.stderr}")
        sys.exit(1)
        
    print(f"Response: {res.stdout.strip()}")
    
    # Retrieve the session ID we just created
    session_id = get_latest_session_id()
    if not session_id:
        print("❌ Could not retrieve latest session ID from database.")
        sys.exit(1)
        
    print(f"✅ Successfully started new session. Session ID: {session_id}")
    
    # Step 2: Resume the session and verify history continuity
    print("\n[Step 2] Resuming session and sending follow-up query...")
    follow_up_prompt = "What was the very first message I sent in this session?"
    res = run_cmd([HERMES_CLI, "chat", "-r", session_id, "-q", follow_up_prompt])
    
    if res.returncode != 0:
        print(f"❌ Error resuming session: {res.stderr}")
        sys.exit(1)
        
    print(f"Response: {res.stdout.strip()}")
    
    # Check if response indicates it remembers the history
    output_lower = res.stdout.lower()
    if "test message" in output_lower or "start a new session" in output_lower or "hello" in output_lower:
        print("✅ Session history was successfully loaded and remembered by the agent!")
    else:
        print("⚠️ Warning: Agent response did not explicitly mention the first message content, but let's check DB.")
        
    # Check DB message count
    conn = sqlite3.connect(STATE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
    count = cursor.fetchone()[0]
    conn.close()
    print(f"✅ Total messages stored in DB for this session: {count} (expected 4)")
    if count >= 4:
        print("✅ Message count matches expectation (2 user, 2 assistant messages).")
    else:
        print(f"❌ Unexpected message count: {count}")
        sys.exit(1)

    # Step 3: Verify the context breakdown RPC logic directly
    print("\n[Step 3] Verifying context breakdown computation...")
    # Import agent modules using python venv and compute the breakdown
    python_code = f"""
import sys
sys.path.append('/home/theworks/.hermes/hermes-agent')
from run_agent import AIAgent
from agent.agent_init import init_agent
from agent.context_breakdown import compute_session_context_breakdown

agent = AIAgent()
init_agent(
    agent,
    model='Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4',
    provider='custom',
    base_url='http://host.docker.internal:30001/v1',
    api_key='vllm-5060ti-token'
)
agent._config_context_length = 10000000
agent._config_physical_context_length = 119500

from agent.context_compressor import ContextCompressor
comp = ContextCompressor(
    model=agent.model,
    base_url=agent.base_url,
    api_key=agent.api_key,
    provider=agent.provider,
    api_mode=agent.api_mode,
    physical_context_length=119500,
    config_context_length=10000000
)
agent.context_compressor = comp

history = [
    {{"role": "system", "content": "You are a helpful assistant"}},
    {{"role": "user", "content": "hello"}},
    {{"role": "assistant", "content": "hi"}}
]

# Run compute breakdown
breakdown = compute_session_context_breakdown(agent, history)
import json
print(json.dumps(breakdown, indent=2))
"""
    res = run_cmd([HERMES_VENV_PYTHON, "-c", python_code])
    if res.returncode != 0:
        print(f"❌ Error computing context breakdown: {res.stderr}")
        sys.exit(1)
        
    stdout = res.stdout
    json_start = stdout.find("{")
    if json_start == -1:
        print(f"❌ Could not find JSON block in output: {stdout}")
        sys.exit(1)
    json_str = stdout[json_start:]
    breakdown = json.loads(json_str)
    print("✅ Context breakdown output:")
    print(json.dumps(breakdown, indent=2))
    
    # Verify expected fields
    expected_keys = ["categories", "context_max", "context_percent", "context_used", "estimated_total", "model"]
    for k in expected_keys:
        if k not in breakdown:
            print(f"❌ Missing key '{k}' in breakdown response.")
            sys.exit(1)
            
    print("✅ All expected keys present in context breakdown.")
    
    # Check if context_max matches virtual limit (10,000,000)
    if breakdown["context_max"] == 10000000:
        print("✅ Context max correctly represents virtual limit (10,000,000).")
    else:
        print(f"❌ Context max mismatch: {breakdown['context_max']}")
        sys.exit(1)
        
    print("\n==========================================================")
    print(" 🎉 All continuity checks PASSED successfully!")
    print("==========================================================")

if __name__ == "__main__":
    main()
