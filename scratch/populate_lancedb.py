#!/usr/bin/env python3
import os
import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from llama_index.core.schema import TextNode, NodeRelationship

def main():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/lancedb_store"))
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

    os.environ["OPENAI_API_KEY"] = "sk-dummy"
    base_url = "http://host.docker.internal:8080/v1" if os.path.exists("/.dockerenv") else "http://localhost:8080/v1"
    embedding_func = get_registry().get("nomic-vulkan").create(
        name="nomic-embed-text-v1.5", 
        base_url=base_url
    )

    class RaptorIndex(LanceModel):
        text: str = embedding_func.SourceField()
        vector: Vector(embedding_func.ndims()) = embedding_func.VectorField()
        parent_text: str
        file_path: str

    table_name = "raptor_collapsed_index"
    
    # Create/overwrite the table
    print(f"Creating table '{table_name}' in LanceDB at {db_path}...")
    table = db.create_table(table_name, schema=RaptorIndex, mode="overwrite")

    # Paths to index
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    requests_dir = os.path.join(root_dir, "scratch/requests_repo")
    
    exclude_dirs = {"venv", "volumes", ".git", "node_modules", "data", "models", "scratch"}
    
    files_to_index = []
    
    # 1. Walk main pipeline repo (except scratch)
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
                files_to_index.append(os.path.join(root, file))
                
    # 2. Walk requests_repo source files and tests
    if os.path.exists(requests_dir):
        for root, dirs, files in os.walk(requests_dir):
            dirs[:] = [d for d in dirs if d not in {".git", "docs"}]
            for file in files:
                if file.endswith(('.py', '.js', '.ts')):
                    files_to_index.append(os.path.join(root, file))

    print(f"Found {len(files_to_index)} code files to index.")

    child_nodes_data = []

    for file_path in files_to_index:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if not content.strip():
                continue
                
            # Detect language
            ext = os.path.splitext(file_path)[1].lower()
            lang = None
            if ext == '.py':
                lang = Language.PYTHON
            elif ext in ('.js', '.jsx'):
                lang = Language.JS
            elif ext in ('.ts', '.tsx'):
                lang = Language.TS
                
            # Setup splitters
            if lang:
                parent_splitter = RecursiveCharacterTextSplitter.from_language(
                    language=lang, chunk_size=1024, chunk_overlap=128
                )
                child_splitter = RecursiveCharacterTextSplitter.from_language(
                    language=lang, chunk_size=256, chunk_overlap=32
                )
            else:
                parent_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1024, chunk_overlap=128
                )
                child_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=256, chunk_overlap=32
                )
                
            # Hierarchical parsing
            parent_chunks = parent_splitter.split_text(content)
            for p_chunk in parent_chunks:
                parent_node = TextNode(text=p_chunk, metadata={"file_path": file_path})
                
                child_chunks = child_splitter.split_text(p_chunk)
                for c_chunk in child_chunks:
                    child_node = TextNode(text=c_chunk, metadata={"file_path": file_path})
                    child_node.relationships[NodeRelationship.PARENT] = parent_node.as_related_node_info()
                    
                    # Store data
                    child_nodes_data.append({
                        "text": f"search_document: {child_node.text}",
                        "parent_text": p_chunk,
                        "file_path": os.path.relpath(file_path, root_dir)
                    })
        except Exception as e:
            print(f"Warning: Failed to index {file_path}: {e}")

    # Fallback to default test documents if no files are indexed
    if not child_nodes_data:
        print("No files found. Falling back to test documents...")
        test_docs = [
            "The AlphaCoreEngine thrust controller uses frequency modulation on 433.5MHz with secret auth token: 'alpha-thrust-secure-key-9988'.",
            "QuantumVault secure session memory vaults use AES-256-GCM. The primary decrypt key is located in memory registry under name 'quantum-vault-key-alpha-delta'.",
            "The HyperionGateway internal routing gateway connects on port 10190 and requires SSL key certificate stored at '/etc/ssl/hyperion-private-cert.pem'.",
            "NexusQueue task dispatcher uses RabbitMQ cluster running on nodes nexus-node-01 through 03 on port 5673. Authentication string: 'nexus-rabbit-secret-pass-2026'."
        ]
        for t in test_docs:
            child_nodes_data.append({
                "text": f"search_document: {t}",
                "parent_text": t,
                "file_path": "test_document.txt"
            })

    print(f"Adding {len(child_nodes_data)} child chunks to LanceDB (with parent context expansion)...")
    table.add(child_nodes_data)
    print("LanceDB database rebuilt successfully!")

if __name__ == "__main__":
    main()
