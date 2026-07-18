import sys
import os
import json
import random
import time
import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

import torch

# Set model names
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Initialize LanceDB
db_path = os.getenv("LANCE_DB_PATH")
if not db_path:
    db_path = "/app/data/lancedb_store"
    if not os.path.exists("/app") or not os.access(os.path.dirname(db_path), os.W_OK):
        db_path = "./data/lancedb_store"

os.makedirs(os.path.dirname(db_path), exist_ok=True)
db = lancedb.connect(db_path)

from lancedb.embeddings.openai import OpenAIEmbeddings

class NomicVulkanEmbeddings(OpenAIEmbeddings):
    @property
    def _ndims(self):
        return 768

# Register custom Vulkan embeddings class
try:
    get_registry().register("nomic-vulkan")(NomicVulkanEmbeddings)
except KeyError:
    pass

# Initialize embedding registry with Vulkan llama-server on port 8080
os.environ["OPENAI_API_KEY"] = "sk-dummy"
base_url = "http://host.docker.internal:8080/v1" if os.path.exists("/.dockerenv") else "http://localhost:8080/v1"
embedding_func = get_registry().get("nomic-vulkan").create(
    name="nomic-embed-text-v1.5", 
    base_url=base_url
)

class AgentMemory(LanceModel):
    id: int
    text: str = embedding_func.SourceField()
    vector: Vector(embedding_func.ndims()) = embedding_func.VectorField()
    conversationId: str
    details: str
    timestamp: float

# Open or create table
table_name = "agent_memories"

def get_table():
    db_conn = lancedb.connect(db_path)
    try:
        return db_conn.open_table(table_name)
    except Exception:
        return db_conn.create_table(table_name, schema=AgentMemory, mode="overwrite")


def store_chat_memory(conversation_id, summary, details):
    table = get_table()
    data = [{
        "id": random.randint(1000000000, 9999999999),
        "text": summary,
        "conversationId": conversation_id,
        "details": details or "",
        "timestamp": time.time() * 1000
    }]
    table.add(data)
    return f"Successfully stored memory in database for conversation {conversation_id}."

def retrieve_chat_memory(conversation_id, query, limit=5):
    # Prefix query for Nomic retrieval model
    nomic_query = f"search_query: {query}"
    
    # We query the table
    table = get_table()
    results = table.search(nomic_query).where(f'conversationId == "{conversation_id}"').limit(limit).to_arrow()
    pydict = results.to_pydict()
    
    texts = pydict.get("text", [])
    details = pydict.get("details", [])
    timestamps = pydict.get("timestamp", [])
    
    if not texts:
        return f"No matching memories found for conversation {conversation_id}."
        
    formatted = []
    for i in range(len(texts)):
        t_val = timestamps[i]
        time_str = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t_val / 1000))
        formatted.append(f"[Memory {i + 1}] ({time_str})\nSummary: {texts[i]}\nDetails: {details[i]}\n")
        
    return "\n---\n\n".join(formatted)


def send_response(req_id, result):
    sys.stdout.write(json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result
    }) + "\n")
    sys.stdout.flush()

def send_error(req_id, code, message):
    sys.stdout.write(json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message}
    }) + "\n")
    sys.stdout.flush()

def send_tool_result(req_id, text):
    send_response(req_id, {
        "content": [{"type": "text", "text": text}],
        "isError": False
    })

def send_tool_error(req_id, message):
    send_response(req_id, {
        "content": [{"type": "text", "text": f"Error: {message}"}],
        "isError": True
    })

def main():
    sys.stderr.write("[Memory MCP] Memory Manager MCP Server starting (LanceDB backend)...\n")
    sys.stderr.flush()
    
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
            
        try:
            request = json.loads(line)
            method = request.get("method")
            req_id = request.get("id")
            
            if not method:
                continue
                
            if method == "initialize":
                send_response(req_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "memory-manager-mcp", "version": "1.0.0"}
                })
            elif method == "notifications/initialized":
                pass
            elif method == "ping":
                send_response(req_id, {})
            elif method == "tools/list":
                send_response(req_id, {
                    "tools": [
                        {
                            "name": "store_chat_memory",
                            "description": "Store a conversation summary or key milestone fact in the long-term memory database. Use this to persist context when conversation history is long or running details need to be saved.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "conversationId": {"type": "string", "description": "Unique identifier for the active agent conversation"},
                                    "summary": {"type": "string", "description": "Concise summary of the memory/decision to store"},
                                    "details": {"type": "string", "description": "Extended details, code changes, or context associated with this memory"}
                                },
                                "required": ["conversationId", "summary"]
                            }
                        },
                        {
                            "name": "retrieve_chat_memory",
                            "description": "Retrieve relevant past conversation summaries and milestones semantically using a natural language query.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "conversationId": {"type": "string", "description": "Unique identifier for the active agent conversation"},
                                    "query": {"type": "string", "description": "Semantic search query to retrieve matches for"},
                                    "limit": {"type": "number", "description": "Max results to return (default 5)"}
                                },
                                "required": ["conversationId", "query"]
                            }
                        }
                    ]
                })
            elif method == "tools/call":
                params = request.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})
                
                if name == "store_chat_memory":
                    conv_id = args.get("conversationId")
                    summary = args.get("summary")
                    details = args.get("details", "")
                    if not conv_id or not summary:
                        send_tool_error(req_id, "Missing required arguments: conversationId and summary")
                    else:
                        res = store_chat_memory(conv_id, summary, details)
                        send_tool_result(req_id, res)
                elif name == "retrieve_chat_memory":
                    conv_id = args.get("conversationId")
                    query = args.get("query")
                    limit = int(args.get("limit", 5))
                    if not conv_id or not query:
                        send_tool_error(req_id, "Missing required arguments: conversationId and query")
                    else:
                        res = retrieve_chat_memory(conv_id, query, limit)
                        send_tool_result(req_id, res)
                else:
                    send_error(req_id, -32601, f"Tool not found: {name}")
            else:
                send_error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            sys.stderr.write(f"[Memory MCP] Error processing request: {str(e)}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
