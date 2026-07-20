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

_session_queries = []

def reset_session():
    global _session_queries
    _session_queries = []

def balance_brackets(text: str) -> str:
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    closers = {'(': ')', '[': ']', '{': '}'}
    
    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    
    i = 0
    n = len(text)
    output = []
    
    while i < n:
        c = text[i]
        
        if in_line_comment:
            if c == '\n':
                in_line_comment = False
            output.append(c)
            i += 1
            continue
        elif in_block_comment:
            if c == '/' and i > 0 and text[i-1] == '*':
                in_block_comment = False
            output.append(c)
            i += 1
            continue
        elif in_single_quote:
            if c == "'" and text[i-1] != '\\':
                in_single_quote = False
            output.append(c)
            i += 1
            continue
        elif in_double_quote:
            if c == '"' and text[i-1] != '\\':
                in_double_quote = False
            output.append(c)
            i += 1
            continue
        elif in_backtick:
            if c == '`' and text[i-1] != '\\':
                in_backtick = False
            output.append(c)
            i += 1
            continue
            
        if c == '/' and i + 1 < n and text[i+1] == '/':
            in_line_comment = True
            output.append(c)
            output.append(text[i+1])
            i += 2
            continue
        elif c == '/' and i + 1 < n and text[i+1] == '*':
            in_block_comment = True
            output.append(c)
            output.append(text[i+1])
            i += 2
            continue
        elif c == "'":
            in_single_quote = True
            output.append(c)
            i += 1
            continue
        elif c == '"':
            in_double_quote = True
            output.append(c)
            i += 1
            continue
        elif c == '`':
            in_backtick = True
            output.append(c)
            i += 1
            continue
            
        if c in '([{':
            stack.append(c)
            output.append(c)
        elif c in ')]}':
            target = pairs[c]
            if stack and stack[-1] == target:
                stack.pop()
                output.append(c)
        else:
            output.append(c)
        i += 1
        
    while stack:
        opener = stack.pop()
        output.append(closers[opener])
        
    return "".join(output)

def execute_tool(query: str, compression_rate: float = 0.33) -> str:
    global _compressor, _tokenizer, _session, _db, _table, _session_queries
    
    # 1. Active Tool Loop Detection Guardrail
    clean_query = query.strip()
    warning_msg = ""
    if _session_queries and _session_queries[-1] == clean_query:
        warning_msg = "System Note: You are repeating the same RAG search query. Try widening your search or reading target file lines directly to proceed.\n\n"
    _session_queries.append(clean_query)

    try:
        try:
            from lancedb.embeddings import get_registry
            from lancedb.embeddings.openai import OpenAIEmbeddings
            class NomicVulkanEmbeddings(OpenAIEmbeddings):
                @property
                def _ndims(self):
                    return 768
            get_registry().register("nomic-vulkan")(NomicVulkanEmbeddings)
        except KeyError:
            pass

        if _db is None:
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/lancedb_store"))
            if not os.path.exists(db_path):
                db_path = "./data/lancedb_store"
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            _db = lancedb.connect(db_path)
        
        table_name = "raptor_collapsed_index"
        if _table is None and table_name in _db.table_names():
            _table = _db.open_table(table_name)
            
        documents_meta = []
        documents = []
        
        if _table is not None:
            nomic_query = f"search_query: {query}"
            results = _table.search(nomic_query).limit(50).to_arrow()
            pydict = results.to_pydict()
            
            raw_texts = pydict.get("text", [])
            parent_texts = pydict.get("parent_text", [])
            file_paths = pydict.get("file_path", [])
            
            for i in range(len(raw_texts)):
                doc_text = raw_texts[i]
                p_text = parent_texts[i] if i < len(parent_texts) else doc_text
                f_path = file_paths[i] if i < len(file_paths) else "unknown"
                documents_meta.append({
                    "child_text": doc_text,
                    "parent_text": p_text,
                    "file_path": f_path
                })
                documents.append(doc_text)
        else:
            documents = ["No documents found. LanceDB table 'raptor_collapsed_index' is not populated yet."]
            documents_meta = [{"child_text": documents[0], "parent_text": documents[0], "file_path": "unknown"}]
            
        if not documents:
            documents = ["No documents found in LanceDB table 'raptor_collapsed_index'."]
            documents_meta = [{"child_text": documents[0], "parent_text": documents[0], "file_path": "unknown"}]

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
        if len(documents) > 0 and documents != ["No documents found. LanceDB table 'raptor_collapsed_index' is not populated yet."] and documents != ["No documents found in LanceDB table 'raptor_collapsed_index'."]:
            pairs = [(query, doc) for doc in documents]
            encoded = _tokenizer(
                pairs,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="np"
            )
            onnx_inputs = {
                "input_ids": encoded["input_ids"].astype("int64"),
                "attention_mask": encoded["attention_mask"].astype("int64")
            }
            logits = _session.run(None, onnx_inputs)[0]
            scores = np.atleast_1d(logits.squeeze(-1)).tolist()
            scored_docs = list(zip(range(len(documents)), scores))
        else:
            scored_docs = [(i, 0.0) for i in range(len(documents))]

        # Apply Lexical Term Boosting
        boosted_docs = []
        for idx, score in scored_docs:
            doc = documents[idx]
            boost = 0.0
            query_words = [w.strip("?,.:;!\"'()[]{}") for w in query.split()]
            for qw in query_words:
                if len(qw) > 4 and qw.lower() in doc.lower():
                    if qw[0].isupper() and qw in doc:
                        boost += 2.0
                    else:
                        boost += 0.4
            boosted_docs.append((idx, score + boost))

        # Sort documents based on boosted scores
        boosted_docs.sort(key=lambda x: x[1], reverse=True)
        top_k_indices = [item[0] for item in boosted_docs[:15]]
        
        # parent context expansion & deduplication
        seen_parents = set()
        top_k_docs = []
        for idx in top_k_indices:
            meta = documents_meta[idx]
            p_text = meta["parent_text"]
            f_path = meta["file_path"]
            if p_text not in seen_parents:
                seen_parents.add(p_text)
                top_k_docs.append(f"// File: {f_path}\n{p_text}")
        
        # 3. Dynamic Bypass & Force-Keep Logic
        force_keep_docs = []
        compress_docs = []
        
        for idx, doc in enumerate(top_k_docs):
            if idx < 3:
                force_keep_docs.append(doc)
            else:
                compress_docs.append(doc)
                
        total_text = "\n\n".join(top_k_docs)
        estimated_tokens = len(total_text) // 4
        
        if estimated_tokens < 2500 or not compress_docs or "AlphaCoreEngine" in query:
            final_payload = balance_brackets(warning_msg + total_text)
            return json.dumps({
                "query": query,
                "compressed_payload": final_payload,
                "metadata": {
                    "original_tokens": estimated_tokens,
                    "compressed_tokens": len(final_payload) // 4,
                    "saving_ratio": "0.0% (bypassed)"
                }
            })
            
        # AST-Guided Mixed Compression
        from ast_compactor import compress_code
        ast_compressed_docs = [compress_code(doc) for doc in compress_docs]
        
        force_keep_text = "\n\n".join(force_keep_docs)
        ast_text = "\n\n".join(ast_compressed_docs)
        
        total_ast_text = (force_keep_text + "\n\n" + ast_text).strip()
        estimated_ast_tokens = len(total_ast_text) // 4
        
        if estimated_ast_tokens < 6000 or compression_rate >= 1.0:
            orig_tokens = len("\n\n".join(top_k_docs)) // 4
            comp_tokens = estimated_ast_tokens
            if orig_tokens > 0:
                saving_ratio_str = f"{(1.0 - comp_tokens / orig_tokens) * 100:.1f}%"
            else:
                saving_ratio_str = "0.0%"
            final_payload = balance_brackets(warning_msg + total_ast_text)
            return json.dumps({
                "query": query,
                "compressed_payload": final_payload,
                "metadata": {
                    "original_tokens": orig_tokens,
                    "compressed_tokens": len(final_payload) // 4,
                    "saving_ratio": f"{saving_ratio_str} (AST bypassed)"
                }
            })
            
        # Initialize PromptCompressor lazily
        if _compressor is None:
            _compressor = PromptCompressor(
                model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                device_map="cpu",
                use_llmlingua2=True
            )
            
        compressed_result = _compressor.compress_prompt(
            context=ast_compressed_docs,
            instruction="Analyze the system and generate the requested response.",
            question=query,
            rate=compression_rate
        )
        
        final_payload = force_keep_text + "\n\n" + compressed_result.get("compressed_prompt", "")
        final_payload = balance_brackets(warning_msg + final_payload)
        
        force_keep_tokens = len(force_keep_text) // 4
        orig_tokens = force_keep_tokens + compressed_result.get("origin_tokens", 0)
        comp_tokens = len(final_payload) // 4
        
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
