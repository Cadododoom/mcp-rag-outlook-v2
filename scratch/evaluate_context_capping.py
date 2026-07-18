import os
import sys
import json
import time
import requests

# Add skills path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../.agents/skills/lancedb-raptor-rag-engine")))
from query_edge_rag import execute_tool

VLLM_URL = "http://localhost:30000/v1/chat/completions"
MODEL_NAME = "Cadododoom/Qwen3.6-35B-A3B-DSV4Pro-FP4"
MAX_ACTIVE_TOKENS = 10000

# Dummy paragraph of approx 200 tokens
DUMMY_PARAGRAPH = (
    "In software engineering, structured system logging is vital for maintaining observability. "
    "Telemetric logs must capture the precise execution runtime, transaction boundaries, "
    "host resource statistics, database latency parameters, and trace identifiers. "
    "By formatting these entries as structured JSON objects, developers can easily ingest them "
    "into visualization dashboards or log analytics platforms. "
    "We must ensure that high throughput event streams are buffered in memory and flushed periodically "
    "using background write loops to prevent disk input-output contention on critical database tables. "
    "Furthermore, thread affinity pin mapping controls scheduler thread distribution, "
    "ensuring that high-concurrency tasks are executed with minimum context-switching latency. "
    "Lock-free circular queues are utilized to buffer telemetry events before they are serialized."
)

# Helper to estimate token counts
def estimate_tokens(text: str) -> int:
    return len(text) // 4

# Truncate messages down to max_tokens (simulate the proxy behavior)
def truncate_messages(messages: list, max_tokens: int) -> list:
    system_messages = [m for m in messages if m.get("role") == "system"]
    
    first_user_message = None
    for m in messages:
        if m.get("role") == "user":
            first_user_message = m
            break
            
    essential_messages = list(system_messages)
    if first_user_message and first_user_message not in essential_messages:
        essential_messages.append(first_user_message)
        
    essential_tokens = sum(estimate_tokens(str(m.get("content", ""))) for m in essential_messages)
    allowed_tokens = max_tokens - essential_tokens
    
    if allowed_tokens <= 0:
        return essential_messages
        
    remaining_messages = []
    current_tokens = 0
    
    # Pull from the end backwards
    for m in reversed(messages):
        if m.get("role") == "system":
            continue
        if m is first_user_message:
            continue
            
        m_tokens = estimate_tokens(str(m.get("content", "")))
        if current_tokens + m_tokens <= allowed_tokens:
            remaining_messages.insert(0, m)
            current_tokens += m_tokens
        else:
            break
            
    result = []
    result.extend(system_messages)
    if first_user_message:
        result.append(first_user_message)
    result.extend(remaining_messages)
    
    return result

def run_evaluation_step(target_tokens: int, mode: str) -> dict:
    print(f"--- Running Test: {target_tokens} tokens context, Mode: {mode.upper()} ---")
    
    # Define tool schema
    tools = [
        {
            "type": "function",
            "function": {
                "name": "retrieve_chat_memory",
                "description": "Query the agent's long-term memory vector database for past facts, setup configurations, or secrets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Semantic query describing what memory fact to retrieve."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    
    system_prompt = (
        "You are an AI coding assistant. Your working context length is limited. "
        "You have access to a tool `retrieve_chat_memory` to fetch past configurations and decisions "
        "from your database. Use this tool if you need database URLs, JWT keys, or framework decisions."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Injected fact (placed at the beginning, will be truncated when target_tokens exceeds MAX_ACTIVE_TOKENS)
    injected_fact = (
        "Project Setup: The AlphaCoreEngine thrust controller uses frequency modulation on 433.5MHz "
        "with secret auth token: 'alpha-thrust-secure-key-9988'."
    )
    messages.append({"role": "assistant", "content": f"I have initialized the configuration: {injected_fact}"})
    
    # Fill remaining history with dummy messages to hit the target token count
    current_estimated = estimate_tokens(system_prompt + injected_fact)
    dummy_index = 0
    while current_estimated < target_tokens:
        role = "user" if dummy_index % 2 == 0 else "assistant"
        content = f"Regarding discussion topic #{dummy_index}: {DUMMY_PARAGRAPH}"
        messages.append({"role": role, "content": content})
        current_estimated += estimate_tokens(content)
        dummy_index += 1
        
    # Last user query about the truncated fact
    query = "What is the secret auth token for AlphaCoreEngine?"
    messages.append({"role": "user", "content": query})
    
    original_length = len(messages)
    
    # 1. Truncate context down to max active limit (like the proxy does)
    truncated_messages = truncate_messages(messages, MAX_ACTIVE_TOKENS)
    truncated_length = len(truncated_messages)
    was_truncated = truncated_length < original_length
    
    # 2. If in Truncation-Aware mode and truncation occurred, inject warning
    if mode == "truncation-aware" and was_truncated:
        warning_msg = (
            "[SYSTEM WARNING]: The older conversation history (exceeding 10,000 tokens) has been "
            "truncated from your active memory to maintain performance. If you require details "
            "regarding previous code milestones, authentication tokens, database connection credentials, "
            "or architectural design decisions that are not visible in the recent messages above, "
            "you MUST call the 'retrieve_chat_memory' tool to search the database. Do not attempt to guess "
            "or invent these details."
        )
        # Append warning inside the last user message
        truncated_messages[-1]["content"] = warning_msg + "\n\n" + truncated_messages[-1]["content"]
        
    # 3. Query vLLM
    print(f"Sending prompt to vLLM (original count: {original_length} msgs, sent: {len(truncated_messages)} msgs)...")
    payload = {
        "model": MODEL_NAME,
        "messages": truncated_messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.1,
        "max_tokens": 1024
    }
    
    try:
        t0 = time.time()
        res = requests.post(VLLM_URL, json=payload, timeout=180)
        res.raise_for_status()
        resp = res.json()
        latency_1 = time.time() - t0
    except Exception as e:
        print(f"Error calling vLLM: {e}")
        return {"status": "error", "message": str(e)}
        
    choice = resp["choices"][0]
    message = choice["message"]
    tool_calls = message.get("tool_calls", [])
    
    # 4. Process tool calls
    if tool_calls:
        tool_call = tool_calls[0]
        tool_name = tool_call["function"]["name"]
        tool_args = json.loads(tool_call["function"]["arguments"])
        tool_query = tool_args["query"]
        
        print(f"Model requested tool call: {tool_name} with query '{tool_query}'")
        
        # Execute local LanceDB search and prompt compression
        rag_res_str = execute_tool(tool_query, compression_rate=0.33)
        rag_res = json.loads(rag_res_str)
        retrieved_context = rag_res.get("compressed_payload", "No matching documents found.")
        
        print(f"RAG Retrieved Context (compressed): {retrieved_context}")
        
        # Feed back to vLLM
        truncated_messages.append(message)
        truncated_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": retrieved_context
        })
        
        # Remove tools to force generation
        payload["messages"] = truncated_messages
        del payload["tools"]
        del payload["tool_choice"]
        
        try:
            t1 = time.time()
            res2 = requests.post(VLLM_URL, json=payload, timeout=180)
            res2.raise_for_status()
            final_content = res2.json()["choices"][0]["message"]["content"]
            total_latency = latency_1 + (time.time() - t1)
        except Exception as e:
            return {"status": "error", "message": f"Final generation failed: {e}"}
            
        # Verify if correct secret is in final response
        is_correct = "alpha-thrust-secure-key-9988" in final_content
        hallucinated = False
        
        print(f"Final Response:\n{final_content}\n")
        
        return {
            "status": "success",
            "was_truncated": was_truncated,
            "tool_called": True,
            "is_correct": is_correct,
            "hallucinated": hallucinated,
            "total_latency": total_latency,
            "response": final_content
        }
    else:
        # No tool called
        content = message.get("content", "")
        print(f"No tool called. Final Response:\n{content}\n")
        
        # Check for hallucinations
        # If the model gives a wrong key instead of saying it doesn't know
        hallucinated = False
        is_correct = "alpha-thrust-secure-key-9988" in content
        
        # If it was truncated and model guessed any key other than correct one
        if was_truncated and not is_correct:
            # Check if any fabricated key-like pattern is in content
            if "key-" in content or "token" in content or "secure" in content:
                hallucinated = True
                
        return {
            "status": "success",
            "was_truncated": was_truncated,
            "tool_called": False,
            "is_correct": is_correct,
            "hallucinated": hallucinated,
            "total_latency": latency_1,
            "response": content
        }

def main():
    print("==========================================================")
    print("    STARTING HIGH CONTEXT & CAPPING EVALUATION HARNESS    ")
    print("==========================================================")
    
    # Test cases: context lengths up to 10 million tokens (simulated)
    # We will test 10k (no truncation), 50k, 250k, 1M, 5M, and 10M tokens
    test_sizes = [10000, 50000, 250000, 1000000, 5000000, 10000000]
    modes = ["naive", "truncation-aware"]
    
    results = []
    
    for size in test_sizes:
        for mode in modes:
            res = run_evaluation_step(size, mode)
            res["size"] = size
            res["mode"] = mode
            results.append(res)
            # Sleep brief moment to let server breathe
            time.sleep(1)
            
    # Compile results into a markdown table
    print("\n==========================================================")
    print("                    EVALUATION METRIC REPORT              ")
    print("==========================================================")
    
    table_lines = [
        "| Context Size (Tokens) | Evaluation Mode | Was Truncated? | Tool Called? | Correct Answer? | Hallucinated? | Latency (sec) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for r in results:
        if r["status"] == "success":
            trunc = "Yes" if r["was_truncated"] else "No"
            tool = "Yes" if r["tool_called"] else "No"
            correct = "Yes" if r["is_correct"] else "No"
            halluc = "Yes" if r["hallucinated"] else "No"
            lat = f"{r['total_latency']:.2f}"
            table_lines.append(f"| {r['size']:,} | {r['mode']} | {trunc} | {tool} | {correct} | {halluc} | {lat} |")
        else:
            table_lines.append(f"| {r['size']:,} | {r['mode']} | Error | Error | Error | Error | Error |")
            
    report = "\n".join(table_lines)
    print(report)
    print("==========================================================\n")
    
    # Save the report to an artifact
    report_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "context_capping_report.md"))
    with open(report_file_path, "w") as f:
        f.write("# Context Capping and Hallucination Metric Report\n\n")
        f.write(report)
        f.write("\n")
        
    print(f"Report saved to {report_file_path}")

if __name__ == "__main__":
    main()
