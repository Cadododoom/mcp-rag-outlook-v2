import os
import requests
import json

def execute_tool(prompt: str, max_tokens: int = 2048, temperature: float = 0.0) -> str:
    url = "http://127.0.0.1:30000/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer local-token-unused"
    }
    payload = {
        "model": "rdtand/Qwen3.6-35B-A3B-PrismaQuant-4.75bit-vllm",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "extra_body": {
            "speculative_num_draft_tokens": 6
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result.get("choices"), list) and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
            else:
                content = result["choices"]["message"]["content"]
            
            # Strict compliance: Return a valid JSON string mapping tool outputs directly
            return json.dumps({
                "response": content,
                "metadata": {
                    "model": "rdtand/Qwen3.6-35B-A3B-PrismaQuant-4.75bit-vllm",
                    "speculation_window": 6,
                    "engine": "SGLang Spec V2"
                }
            })
        else:
            return json.dumps({"error": f"HTTP {response.status_code}: {response.text}"})
    except Exception as e:
        return json.dumps({"error": str(e)})
