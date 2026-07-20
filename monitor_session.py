import sqlite3
import time
import logging
import os
import argparse
import json

def setup_logger(log_file):
    logger = logging.getLogger('session_monitor')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)
    return logger

def analyze_logs(db_path, logger):
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        
        if 'messages' in tables:
            # Analyze using the real messages table
            cursor.execute("SELECT role, tool_name, tool_calls, content FROM messages ORDER BY id ASC")
            rows = cursor.fetchall()
            
            # Loop detection (consecutive duplicate tool calls)
            prev_tool_call = None
            consecutive_count = 0
            for row in rows:
                role, tool_name, tool_calls, content = row
                if role == "assistant" and tool_name:
                    call_sig = f"{tool_name}:{tool_calls}"
                    if call_sig == prev_tool_call:
                        consecutive_count += 1
                        if consecutive_count >= 3:
                            logger.warning(f"Tool loop detected! Repeated tool call: {tool_name} with args: {tool_calls}")
                    else:
                        consecutive_count = 1
                    prev_tool_call = call_sig

            # Error and Truncation detection
            for row in rows:
                role, tool_name, tool_calls, content = row
                if content:
                    msg = content.lower()
                    if 'error' in msg or 'exception' in msg or 'hang' in msg or 'exit' in msg:
                        logger.warning(f"Subprocess/Tool issue detected in content: {content[:150]}")
                    if 'warning' in msg or 'truncate' in msg or 'truncation' in msg or 'compact' in msg:
                        logger.warning(f"System context/truncation issue detected in content: {content[:150]}")
                        
        elif 'logs' in tables:
            # Legacy/Mock logs table fallback
            cursor.execute("PRAGMA table_info(logs)")
            cols = [col[1] for col in cursor.fetchall()]
            msg_col = 'message' if 'message' in cols else 'content' if 'content' in cols else None
            
            if msg_col:
                cursor.execute(f"SELECT {msg_col} FROM logs ORDER BY rowid ASC")
                rows = cursor.fetchall()
                
                prev_msg = None
                consecutive_count = 0
                for row in rows:
                    msg = str(row[0])
                    if msg == prev_msg and msg.strip():
                        consecutive_count += 1
                        if consecutive_count >= 3:
                            logger.warning(f"Tool loop detected! Repeated 3 times: {msg[:100]}")
                    else:
                        consecutive_count = 1
                    prev_msg = msg
                    
                for row in rows:
                    msg = str(row[0]).lower()
                    if 'error' in msg or 'exception' in msg or 'hang' in msg or 'exit' in msg:
                        logger.warning(f"Subprocess issue detected: {msg[:100]}")
                    if 'warning' in msg or 'truncate' in msg or 'truncation' in msg:
                        logger.warning(f"System context/truncation issue detected: {msg[:100]}")
        else:
            logger.warning(f"Neither 'messages' nor 'logs' table found. Available tables: {tables}")
            
        logger.info("Log analysis cycle complete.")
        conn.close()
    except Exception as e:
        logger.error(f"Error querying db: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=os.path.expanduser('~/.hermes/state.db'))
    parser.add_argument('--log', default='/home/theworks/teamwork_projects/neon_void_monitor/session_diagnostics.log')
    parser.add_argument('--duration', type=int, default=86400) # 24 hours
    parser.add_argument('--interval', type=int, default=120)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    logger = setup_logger(args.log)
    logger.info("Starting background monitor...")
    
    end_time = time.time() + args.duration
    while time.time() < end_time:
        analyze_logs(args.db, logger)
        time.sleep(args.interval)
