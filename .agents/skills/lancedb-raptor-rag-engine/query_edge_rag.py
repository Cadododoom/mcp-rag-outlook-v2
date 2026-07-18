import os
import sys

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

def execute_tool(query: str, compression_rate: float = 0.33) -> str:
    global _compressor, _tokenizer, _session
    try:
        # 1. Connect to local disk-backed LanceDB with RaBitQ quantization
        db_path = "./data/lancedb_store"
        if not os.path.exists(db_path):
            # Attempt to resolve relative to this file
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/lancedb_store"))
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = lancedb.connect(db_path)
        
        # Open table
        table_name = "raptor_collapsed_index"
        if table_name in db.table_names():
            table = db.open_table(table_name)
            # Prefix query for BGE retrieval model
            bge_query = f"Represent this sentence for searching relevant passages: {query}"
            results = table.search(bge_query).limit(50).to_arrow()
            documents = results.to_pydict().get("text", [])
        else:
            # Fallback if table doesn't exist yet
            documents = ["No documents found. LanceDB table 'raptor_collapsed_index' is not populated yet."]
            
        if not documents:
            documents = ["No documents found in LanceDB table 'raptor_collapsed_index'."]

        # 2. Re-rank retrieved candidates using CPU-optimized INT8 ONNX cross-encoder
        # Bind process to specific CPU cores if supported to prevent thread contention under high concurrency (32 agents)
        try:
            if hasattr(os, "sched_setaffinity"):
                num_cpus = os.cpu_count() or 1
                pid = os.getpid()
                # Bind to 2 cores matching the 2 intra-op threads
                core1 = pid % num_cpus
                core2 = (pid + 1) % num_cpus
                os.sched_setaffinity(0, {core1, core2})
        except Exception:
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

        # Sort documents based on scores
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        top_k_docs = [item[0] for item in scored_docs[:15]]
        
        # 3. Dynamic Bypass & Compression Cache
        total_text = "\n\n".join(top_k_docs)
        estimated_tokens = len(total_text) // 4
        
        if estimated_tokens < 2500:
            return json.dumps({
                "query": query,
                "compressed_payload": total_text,
                "metadata": {
                    "original_tokens": estimated_tokens,
                    "compressed_tokens": estimated_tokens,
                    "saving_ratio": "0.0% (bypassed)"
                }
            })
            
        # Initialize PromptCompressor lazily and cache it
        if _compressor is None:
            _compressor = PromptCompressor(
                model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                device_map="cpu",
                use_llmlingua2=True
            )
        
        compressed_result = _compressor.compress_prompt(
            context=top_k_docs,
            instruction="Analyze the system and generate the requested response.",
            question=query,
            rate=compression_rate
        )
        
        ratio_val = compressed_result.get('ratio', '0%')
        try:
            if isinstance(ratio_val, str):
                if ratio_val.endswith('%'):
                    saving_ratio_str = f"{float(ratio_val.replace('%', '')):.1f}%"
                elif ratio_val.endswith('x'):
                    saving_ratio_str = ratio_val
                else:
                    saving_ratio_str = f"{float(ratio_val):.1f}%"
            else:
                saving_ratio_str = f"{float(ratio_val * 100):.1f}%"
        except Exception:
            saving_ratio_str = str(ratio_val)
            
        return json.dumps({
            "query": query,
            "compressed_payload": compressed_result.get("compressed_prompt", ""),
            "metadata": {
                "original_tokens": compressed_result.get("origin_tokens", 0),
                "compressed_tokens": compressed_result.get("compressed_tokens", 0),
                "saving_ratio": saving_ratio_str
            }
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
