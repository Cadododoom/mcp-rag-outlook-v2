import os
import uuid
import random
import requests
import time
import concurrent.futures
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

BASE_DIR = r"C:\Users\jeffr\.gemini\antigravity\scratch\mcp-rag-outlook\scratch\synthetic_codebase"
EMBEDDING_URL = "http://localhost:8080/v1/embeddings"
MILVUS_URL = "http://localhost:18080"
CONV_ID = "rag-stress-test-conv"

# Configure connection pooling for requests
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
session.mount("http://", HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retries))

def generate_synthetic_codebase(num_files=1000):
    print(f"[Generator] Creating synthetic codebase of {num_files} files at {BASE_DIR}...")
    os.makedirs(BASE_DIR, exist_ok=True)
    
    # Pre-generate some unique features to search for
    target_secrets = [
        {"name": "AlphaCoreEngine", "detail": "The core thrust controller uses frequency modulation on 433.5MHz with secret auth token: 'alpha-thrust-secure-key-9988'."},
        {"name": "QuantumVault", "detail": "The secure session memory vaults use AES-256-GCM. The primary decrypt key is located in memory registry under name 'quantum-vault-key-alpha-delta'."},
        {"name": "HyperionGateway", "detail": "The internal routing gateway connects on port 10190 and requires SSL key certificate stored at '/etc/ssl/hyperion-private-cert.pem'."},
        {"name": "NexusQueue", "detail": "The task dispatcher uses RabbitMQ cluster running on nodes nexus-node-01 through 03 on port 5673. Authentication string: 'nexus-rabbit-secret-pass-2026'."}
    ]
    
    # Store these targets so we can check if they are correctly indexed
    targets_written = []
    
    for i in range(num_files):
        file_name = f"module_{i:04d}.py"
        file_path = os.path.join(BASE_DIR, file_name)
        
        # Inject one of the target secrets into random modules
        injected = None
        if i in [100, 300, 500, 700] and target_secrets:
            injected = target_secrets.pop(0)
            targets_written.append(injected)
            
        with open(file_path, "w") as f:
            f.write("# Synthetic Codebase Module\n")
            f.write("import os\nimport sys\nimport time\n\n")
            
            # Generate 15-20 dummy classes/functions per file
            for j in range(15):
                func_id = str(uuid.uuid4())[:8]
                f.write(f"def process_data_flow_{j}_{func_id}(data_payload):\n")
                f.write(f"    \"\"\"\n")
                
                if injected and j == 7:
                    # Inject target detail in the docstring
                    f.write(f"    Spec: {injected['name']} integration details.\n")
                    f.write(f"    Details: {injected['detail']}\n")
                else:
                    f.write(f"    Standard data processing block for utility function {func_id}.\n")
                    f.write(f"    Handles mathematical routing for module parameter block {random.random()}.\n")
                    
                f.write(f"    \"\"\"\n")
                f.write(f"    processed = [x * 2 for x in data_payload]\n")
                f.write(f"    return processed\n\n")
                
    print(f"[Generator] Synthetic codebase generated successfully. Injected targets: {[t['name'] for t in targets_written]}")
    return targets_written

def parse_and_chunk_codebase():
    print("[Ingester] Parsing codebase files and chunking by functions...")
    chunks = []
    for file_name in os.listdir(BASE_DIR):
        if not file_name.endswith(".py"):
            continue
        file_path = os.path.join(BASE_DIR, file_name)
        with open(file_path, "r") as f:
            content = f.read()
            
        # Quick parsing based on functions
        parts = content.split("def ")
        for part in parts[1:]:
            lines = part.split("\n")
            func_name = lines[0].split("(")[0].strip()
            
            # Extract docstring
            docstring_lines = []
            in_docstring = False
            for line in lines[1:]:
                if '"""' in line:
                    if not in_docstring:
                        in_docstring = True
                    else:
                        break
                elif in_docstring:
                    docstring_lines.append(line.strip())
                    
            summary = f"Function {func_name} in {file_name}"
            details = " ".join(docstring_lines)
            
            chunks.append({
                "summary": summary,
                "details": details
            })
            
    print(f"[Ingester] Total parsed code chunks: {len(chunks)}")
    return chunks

def get_embedding_rest(text):
    res = session.post(EMBEDDING_URL, json={"input": text}, timeout=10)
    res.raise_for_status()
    return res.json()["data"][0]["embedding"]

def ingest_all_chunks(chunks):
    print(f"[Ingester] Ingesting {len(chunks)} chunks into Milvus using 32 parallel threads...")
    
    # We will compute embeddings in parallel
    start_time = time.time()
    embeddings = [None] * len(chunks)
    
    def process_chunk(idx):
        try:
            summary = chunks[idx]["summary"]
            details = chunks[idx]["details"]
            # Embed the combination of summary and details
            text_to_embed = f"{summary} - {details}"
            vector = get_embedding_rest(text_to_embed)
            embeddings[idx] = vector
        except Exception as e:
            print(f"Error embedding chunk {idx}: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(process_chunk, i): i for i in range(len(chunks))}
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            if completed % 1000 == 0:
                rate = completed / (time.time() - start_time)
                print(f"  Embedded {completed}/{len(chunks)} chunks... ({rate:.1f} embeddings/sec)")
                
    embed_time = time.time() - start_time
    print(f"[Ingester] Computed {len(chunks)} embeddings in {embed_time:.2f} seconds.")

    # Filter out failures
    valid_data = []
    for i in range(len(chunks)):
        if embeddings[i] is not None:
            valid_data.append({
                "id": random.randint(1000000000, 9999999999),
                "vector": embeddings[i],
                "conversationId": CONV_ID,
                "summary": chunks[i]["summary"],
                "details": chunks[i]["details"],
                "timestamp": int(time.time() * 1000)
            })

    # Bulk insert into Milvus
    print(f"[Ingester] Bulk inserting {len(valid_data)} records into Milvus...")
    payload = {
        "collectionName": "agent_memories",
        "data": valid_data
    }
    
    t0 = time.time()
    res = requests.post(f"{MILVUS_URL}/v2/vectordb/entities/insert", json=payload)
    res.raise_for_status()
    print(f"[Ingester] Milvus insert completed in {time.time() - t0:.2f} seconds.")

if __name__ == "__main__":
    t_start = time.time()
    targets = generate_synthetic_codebase(1000)
    chunks = parse_and_chunk_codebase()
    
    # Truncate chunks to 15000 to keep within reasonable memory/embedding limits for test speed (approx 15,000 functions)
    chunks = chunks[:15000]
    
    ingest_all_chunks(chunks)
    print(f"[Ingester] Total Ingestion execution time: {time.time() - t_start:.2f} seconds.")
