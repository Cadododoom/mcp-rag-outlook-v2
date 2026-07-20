import sys
import os
import sqlite3

# Add the correct active hermes-swarm path to sys.path
sys.path.insert(0, '/home/theworks/.gemini/antigravity/scratch/hermes-swarm')

from run_agent import AIAgent
from agent.conversation_compression import compress_context
from hermes_cli.config import load_config
from hermes_state import SessionDB

# Set home environment
os.environ['HERMES_HOME'] = '/home/theworks/.hermes'

def compress_session(session_id):
    db = SessionDB()
    
    cfg = load_config()
    model_conf = cfg.get("model", {})
    
    # Initialize AIAgent
    agent = AIAgent(
        model=model_conf.get("default"),
        provider=model_conf.get("provider"),
        base_url=model_conf.get("base_url"),
        api_key=model_conf.get("api_key"),
        session_db=db,
        quiet_mode=True
    )
    agent.session_id = session_id
    
    # Load messages
    messages = db.get_messages(session_id)
    if not messages or len(messages) < 2:
        print("Not enough messages to compress.")
        return
        
    print(f"Loaded {len(messages)} messages. Starting context compression...")
    
    # Rebuild system prompt
    from agent.system_prompt import build_system_prompt
    system_prompt = build_system_prompt(agent)
    
    # Run compress_context
    new_messages, new_sys = compress_context(
        agent=agent,
        messages=messages,
        system_message=system_prompt,
        force=True
    )
    print("Compression complete. Fresh continuation session created:", agent.session_id)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 compress_session.py <session_id>")
        sys.exit(1)
    compress_session(sys.argv[1])
