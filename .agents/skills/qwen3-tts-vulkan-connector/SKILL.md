---
name: qwen3-tts-vulkan-connector
description: Generates high-quality, ultra-low-latency synthetic speech via the Vulkan-accelerated Qwen3-TTS workstation on Windows 11. Use to output vocal responses.
version: 1.0.0
tools:
  - name: generate_vulkan_speech
    description: Synthesizes continuous audio speech using the fast, quantized Q8_0 Base model and a pre-saved speaker embedding JSON.
    parameters:
      type: object
      properties:
        text:
          type: string
          description: The input text to synthesize into speech.
        speaker_persona_path:
          type: string
          description: Relative path to the saved speaker embedding JSON file.
          default: "./models/preset_speakers/gravelly_british_narrator.json"
      required:
        - text
---

# Qwen3-TTS Vulkan Connector Skill

This skill routes speech synthesis tasks to the local KoboldCpp server running on port 5001. The tool bypasses CPU and main-GPU bottlenecks by utilizing Vulkan hardware acceleration.
