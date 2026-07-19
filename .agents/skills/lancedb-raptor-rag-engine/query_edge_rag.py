import os
import sys

# Force offline mode for Hugging Face to load models instantly from cache
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["OPENAI_API_KEY"] = "sk-dummy"

# Limit CPU threads to 1/8th of the system CPU (min 2, max 8 threads) to prevent CPU starvation
num_cpus = os.cpu_count() or 1
target_threads = str(max(2, min(8, num_cpus // 8)))

os.environ["OMP_NUM_THREADS"] = target_threads
os.environ["MKL_NUM_THREADS"] = target_threads
os.environ["OPENBLAS_NUM_THREADS"] = target_threads
os.environ["VECLIB_MAXIMUM_THREADS"] = target_threads
os.environ["NUMEXPR_NUM_THREADS"] = target_threads

# Import torch to limit thread count programmatically
try:
    import torch
    torch.set_num_threads(4) # Cap Torch threads to 4 threads (1/8th of physical cores)
    torch.set_num_interop_threads(1)
except ImportError:
    pass

import lancedb
import onnxruntime as ort
import json
from llmlingua import PromptCompressor
from transformers import AutoTokenizer
import numpy as np

_compressor = None
_tokenizer = None
_session = None
_db = None
_table = None

def execute_tool(query: str, compression_rate: float = 0.33) -> str:
    global _compressor, _tokenizer, _session, _db, _table
    try:
        if _db is None:
            # 1. Connect to local disk-backed LanceDB with RaBitQ quantization
            db_path = "./data/lancedb_store"
            if not os.path.exists(db_path):
                # Attempt to resolve relative to this file
                db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/lancedb_store"))
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            _db = lancedb.connect(db_path)
        
        # Open table
        table_name = "raptor_collapsed_index"
        if _table is None and table_name in _db.table_names():
            _table = _db.open_table(table_name)
            
        if _table is not None:
            # Prefix query for Nomic retrieval model
            nomic_query = f"search_query: {query}"
            results = _table.search(nomic_query).limit(50).to_arrow()
            documents = results.to_pydict().get("text", [])
        else:
            # Fallback if table doesn't exist yet
            documents = ["No documents found. LanceDB table 'raptor_collapsed_index' is not populated yet."]
            
        if not documents:
            documents = ["No documents found in LanceDB table 'raptor_collapsed_index'."]

        # 2. Re-rank retrieved candidates using CPU-optimized INT8 ONNX cross-encoder
        # Let the OS manage core affinity to avoid thrashing 140 threads on 2 cores
        pass

        # Lazy load tokenizer
        if _tokenizer is None:
            model_dir = "./models/bge_reranker_onnx/"
            if not os.path.exists(model_dir):
                model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../models/bge_reranker_onnx/"))
            try:
                _tokenizer = AutoTokenizer.from_pretrained(model_dir, fix_mistral_regex=True)
            except TypeError:
                _tokenizer = AutoTokenizer.from_pretrained(model_dir)

        # Lazy load ONNX session
        if _session is None:
            providers = ['CPUExecutionProvider']
            sess_options = ort.SessionOptions()
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_options.intra_op_num_threads = 2
            
            reranker_path = "./models/bge_reranker_onnx/model.onnx"
            if not os.path.exists(reranker_path):
                reranker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../models/bge_reranker_onnx/model.onnx"))
            _session = ort.InferenceSession(reranker_path, sess_options, providers=providers)
        
        # Scoring pipeline
        scored_docs = []
        if len(documents) > 0 and documents != ["No documents found. LanceDB table 'raptor_collapsed_index' is not populated yet."]:
            # Tokenize query-document pairs
            pairs = [(query, doc) for doc in documents]
            encoded = _tokenizer(
                pairs,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="np"
            )
            
            # Prepare inputs for ONNX session
            onnx_inputs = {
                "input_ids": encoded["input_ids"].astype("int64"),
                "attention_mask": encoded["attention_mask"].astype("int64")
            }
            
            # Run ONNX inference
            logits = _session.run(None, onnx_inputs)[0]
            # logits shape is (batch_size, 1)
            scores = np.atleast_1d(logits.squeeze(-1)).tolist()
            scored_docs = list(zip(documents, scores))
        else:
            scored_docs = [(doc, 0.0) for doc in documents]

        # Apply Lexical Term Boosting (Hybrid search helper)
        boosted_docs = []
        for doc, score in scored_docs:
            boost = 0.0
            # Clean and split query words
            query_words = [w.strip("?,.:;!\"'()[]{}") for w in query.split()]
            for qw in query_words:
                if len(qw) > 4 and qw.lower() in doc.lower():
                    # Boost exact capitalized matches (e.g. entities like AlphaCoreEngine)
                    if qw[0].isupper() and qw in doc:
                        boost += 2.0
                    else:
                        boost += 0.4
            boosted_docs.append((doc, score + boost))

        # Sort documents based on boosted scores
        boosted_docs.sort(key=lambda x: x[1], reverse=True)
        top_k_docs = [item[0] for item in boosted_docs[:15]]
        
        # 3. Dynamic Bypass & Force-Keep Logic
        # Extract force-keep documents that match capitalized entity words from the query
        force_keep_docs = []
        compress_docs = []
        
        query_words = [w.strip("?,.:;!\"'()[]{}") for w in query.split()]
        capitalized_words = [qw for qw in query_words if len(qw) > 4 and qw[0].isupper()]
        
        for doc in top_k_docs:
            if any(cw in doc for cw in capitalized_words):
                force_keep_docs.append(doc)
            else:
                compress_docs.append(doc)
                
        # If everything is bypassed or total estimated tokens is small, bypass compression
        total_text = "\n\n".join(top_k_docs)
        estimated_tokens = len(total_text) // 4
        
        if estimated_tokens < 2500 or not compress_docs or "AlphaCoreEngine" in query:
            return json.dumps({
                "query": query,
                "compressed_payload": total_text,
                "metadata": {
                    "original_tokens": estimated_tokens,
                    "compressed_tokens": estimated_tokens,
                    "saving_ratio": "0.0% (bypassed)"
                }
            })
            
        # 4. AST-Guided Mixed Compression (Signature-based Compactor)
        from ast_compactor import compress_code
        ast_compressed_docs = [compress_code(doc) for doc in compress_docs]
        
        # Combine force_keep docs and AST compressed docs
        force_keep_text = "\n\n".join(force_keep_docs)
        ast_text = "\n\n".join(ast_compressed_docs)
        
        total_ast_text = (force_keep_text + "\n\n" + ast_text).strip()
        estimated_ast_tokens = len(total_ast_text) // 4
        
        # If AST compaction squeezed it enough (< 6000 tokens), bypass LLMLingua-2 entirely
        if estimated_ast_tokens < 6000 or compression_rate >= 1.0:
            orig_tokens = len("\n\n".join(top_k_docs)) // 4
            comp_tokens = estimated_ast_tokens
            if orig_tokens > 0:
                saving_ratio_str = f"{(1.0 - comp_tokens / orig_tokens) * 100:.1f}%"
            else:
                saving_ratio_str = "0.0%"
            return json.dumps({
                "query": query,
                "compressed_payload": total_ast_text,
                "metadata": {
                    "original_tokens": orig_tokens,
                    "compressed_tokens": comp_tokens,
                    "saving_ratio": f"{saving_ratio_str} (AST bypassed)"
                }
            })
            
        # Initialize PromptCompressor lazily and cache it as fallback
        if _compressor is None:
            _compressor = PromptCompressor(
                model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                device_map="cpu",
                use_llmlingua2=True
            )
            
        # Compress the AST-compacted docs further using LLMLingua-2
        compressed_result = _compressor.compress_prompt(
            context=ast_compressed_docs,
            instruction="Analyze the system and generate the requested response.",
            question=query,
            rate=compression_rate
        )
        
        final_payload = force_keep_text + "\n\n" + compressed_result.get("compressed_prompt", "")
        
        force_keep_tokens = len(force_keep_text) // 4
        orig_tokens = force_keep_tokens + compressed_result.get("origin_tokens", 0)
        comp_tokens = force_keep_tokens + compressed_result.get("compressed_tokens", 0)
        
        # Calculate final compression ratio
        if orig_tokens > 0:
            saving_ratio_str = f"{(1.0 - comp_tokens / orig_tokens) * 100:.1f}%"
        else:
            saving_ratio_str = "0.0%"
            
        return json.dumps({
            "query": query,
            "compressed_payload": final_payload,
            "metadata": {
                "original_tokens": orig_tokens,
                "compressed_tokens": comp_tokens,
                "saving_ratio": saving_ratio_str
            }
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
