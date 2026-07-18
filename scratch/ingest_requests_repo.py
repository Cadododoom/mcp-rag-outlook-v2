import os
import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

def get_py_files(directory):
    py_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    return py_files

def chunk_file(file_path, base_dir, chunk_size=30, overlap=10):
    rel_path = os.path.relpath(file_path, base_dir)
    chunks = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    total_lines = len(lines)
    start = 0
    while start < total_lines:
        end = min(start + chunk_size, total_lines)
        chunk_lines = lines[start:end]
        code_content = "".join(chunk_lines)
        
        # Format chunk text with metadata header for context preservation
        chunk_text = f"File: {rel_path} (Lines {start+1}-{end})\n\n```python\n{code_content}```"
        chunks.append({"text": chunk_text})
        
        start += (chunk_size - overlap)
        if start >= total_lines or end == total_lines:
            break
            
    return chunks

def main():
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "requests_repo/src/requests"))
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/lancedb_store"))
    
    if not os.path.exists(repo_dir):
        print(f"Error: Repository directory not found at {repo_dir}")
        return

    print(f"Scanning python files in: {repo_dir}...")
    py_files = get_py_files(repo_dir)
    print(f"Found {len(py_files)} Python source files.")

    # Generate chunks
    all_chunks = []
    for file_path in py_files:
        file_chunks = chunk_file(file_path, os.path.dirname(repo_dir))
        all_chunks.extend(file_chunks)
    
    # Append test project facts so they are preserved
    test_docs = [
        {"text": "The AlphaCoreEngine thrust controller uses frequency modulation on 433.5MHz with secret auth token: 'alpha-thrust-secure-key-9988'."},
        {"text": "QuantumVault secure session memory vaults use AES-256-GCM. The primary decrypt key is located in memory registry under name 'quantum-vault-key-alpha-delta'."},
        {"text": "The HyperionGateway internal routing gateway connects on port 10190 and requires SSL key certificate stored at '/etc/ssl/hyperion-private-cert.pem'."},
        {"text": "NexusQueue task dispatcher uses RabbitMQ cluster running on nodes nexus-node-01 through 03 on port 5673. Authentication string: 'nexus-rabbit-secret-pass-2026'."},
        {"text": "Project Antigravity coordinates up to 64 micro-agents concurrently across a virtualized network mesh. The system is designed to run locally on multi-GPU consumer workstations."},
        {"text": "Database credentials for the production environment are set to database URL: postgresql://postgres:auth-key-9988@localhost:5432/production_db"},
        {"text": "JWT Token signing key is configured to jwt-secret-string-alpha-beta-12345 in the auth API gateway."},
        {"text": "The application framework uses Node.js, Fastify, and TypeORM for postgres database connections."}
    ]
    all_chunks.extend(test_docs)
    
    print(f"Generated {len(all_chunks)} code chunks (including {len(test_docs)} project facts).")

    # Initialize LanceDB
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = lancedb.connect(db_path)

    # Use a small local model for embedding
    embedding_func = get_registry().get("sentence-transformers").create(name="BAAI/bge-small-en-v1.5")

    class RaptorIndex(LanceModel):
        text: str = embedding_func.SourceField()
        vector: Vector(embedding_func.ndims()) = embedding_func.VectorField()

    table_name = "raptor_collapsed_index"
    print(f"Overwriting LanceDB table '{table_name}' at {db_path}...")
    table = db.create_table(table_name, schema=RaptorIndex, mode="overwrite")

    # Ingest chunks
    print("Computing embeddings and adding to database (running locally on CPU)...")
    batch_size = 64
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]
        table.add(batch)
        print(f"  Added batch {i//batch_size + 1}/{len(all_chunks)//batch_size + 1} ({len(batch)} chunks)...")

    # print("Creating vector index IVF_RQ...")
    # table.create_index(vector_column_name="vector", index_type="IVF_RQ")
    
    print("Ingestion of 'requests' repository completed successfully!")

if __name__ == "__main__":
    main()
