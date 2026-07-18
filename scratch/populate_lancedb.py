import os
import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

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

    table_name = "raptor_collapsed_index"
    
    # Create/overwrite the table
    print(f"Creating table '{table_name}' in LanceDB at {db_path}...")
    table = db.create_table(table_name, schema=RaptorIndex, mode="overwrite")

    # Ingest some realistic documents for testing the RAG stack
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

    print("Ingesting test documents...")
    prefixed_docs = [{"text": f"search_document: {item['text']}"} for item in test_docs]
    table.add(prefixed_docs)
    
    print("LanceDB test database populated successfully!")

if __name__ == "__main__":
    main()
