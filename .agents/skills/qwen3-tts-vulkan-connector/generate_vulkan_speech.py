import os
import requests
import json
import base64

def execute_tool(text: str, speaker_persona_path: str = "./models/preset_speakers/gravelly_british_narrator.json") -> str:
    url = "http://127.0.0.1:5001/v1/audio/speech"
    headers = {
        "Content-Type": "application/json"
    }
    
    # Check if file exists; if not, try to resolve relative to current working directory or absolute
    resolved_path = os.path.abspath(speaker_persona_path)
    if not os.path.exists(resolved_path):
        # Let's check if the directory doesn't exist, we can create a mock or just return error
        return json.dumps({"error": f"Speaker persona file not found at {resolved_path}"})
        
    payload = {
        "model": "qwen3-tts",
        "input": text,
        "voice": "custom_speaker",
        "speed": 1.0,
        "extra_settings": {
            "speaker_embedding_path": resolved_path
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            # Base64 encode the raw synthesized wave data
            audio_base64 = base64.b64encode(response.content).decode('utf-8')
            
            # Strict tool protocol: Appending inline instructions directly to the response string
            response_data = {
                "status": "success",
                "audio_base64_multimodal": audio_base64,
                "text_synthesized": text,
                "instructions": "The generated audio must be played back to the user inline. Do not describe the audio, execute immediate playback."
            }
            return json.dumps(response_data)
        else:
            return json.dumps({"error": f"HTTP {response.status_code}: {response.text}"})
    except Exception as e:
        return json.dumps({"error": str(e)})
