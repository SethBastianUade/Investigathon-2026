#!/usr/bin/env bash
# Ollama sin sudo: solo escucha en 127.0.0.1:11434.
export OLLAMA_CONTEXT_LENGTH=32768
export OLLAMA_KEEP_ALIVE=30m
nohup ~/.local/ollama/bin/ollama serve >> ~/investigathon/ollama.log 2>&1 &
echo "ollama pid $!"
