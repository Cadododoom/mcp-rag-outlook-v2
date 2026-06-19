---
name: lancedb-raptor-rag-engine
description: Performs local hierarchical semantic search and document synthesis. Use when querying massive local knowledge bases or analyzing document structures.
version: 1.0.0
tools:
  - name: query_edge_rag
    description: Retrieves and compresses local documents utilizing LanceDB 1-bit RaBitQ indexing and LLMLingua-2 context compaction.
    parameters:
      type: object
      properties:
        query:
          type: string
          description: The semantic search query.
        compression_rate:
          type: float
          default: 0.4
          description: Target retention rate for LLMLingua-2 context compression.
      required:
        - query
---

# LanceDB RAPTOR RAG Engine Skill

This skill manages the disk-backed LanceDB vector store and prompt compression pipeline. By offloading indexing and compression to the host CPU, it protects the 32 GB GPU VRAM budget.
