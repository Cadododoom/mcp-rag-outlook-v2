#!/usr/bin/env bash
# Launch Script for Native Vulkan Embedding Server on AMD RX 5700
# Run this to start the embedding server on your host machine

BinDir="/home/theworks/.gemini/antigravity/scratch/mcp-rag-outlook/bin/llama-cpp-vulkan"
ModelPath="/home/theworks/.gemini/antigravity/scratch/mcp-rag-outlook/models/nomic-embed-text-v1.5.Q8_0.gguf"
LlamaServer="$BinDir/llama-server"

echo "Starting Vulkan embedding server on host port 8080..."
echo "Offloading 100% of layers to GPU..."

exec "$LlamaServer" -m "$ModelPath" -c 2048 --port 8080 --embedding --device "Vulkan0" -ngl 99
