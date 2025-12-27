import subprocess
import requests
import time
import os

def is_ollama_running(base_url="http://localhost:11434/v1"):
    try:
        # Check /v1/models or just the root
        response = requests.get(base_url.rstrip("/v1") + "/", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def ensure_ollama_running():
    if is_ollama_running():
        print("[LLM STARTUP] Ollama is already running.")
        return True
    
    print("[LLM STARTUP] Ollama not detected. Attempting to start...")
    try:
        # Try to start Ollama in the background
        # On Windows, 'ollama serve' usually works if installed
        subprocess.Popen(["ollama", "serve"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        
        # Wait for it to spin up
        for i in range(10):
            print(f"   Waiting for Ollama to initialize... ({i+1}/10)")
            time.sleep(2)
            if is_ollama_running():
                print("[LLM STARTUP] Ollama started successfully.")
                return True
    except Exception as e:
        print(f"[LLM STARTUP] Failed to start Ollama automatically: {e}")
        print("Please ensure Ollama is installed and in your PATH.")
    
    return False

def ensure_model_available(model_name):
    if not is_ollama_running():
        return False
        
    print(f"[LLM STARTUP] Checking if model '{model_name}' is available...")
    base_url = "http://localhost:11434"
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            # Check if any model name matches (Ollama often appends :latest)
            if any(model_name in m['name'] for m in models):
                print(f"[LLM STARTUP] Model '{model_name}' is ready.")
                return True
        
        print(f"[LLM STARTUP] Model '{model_name}' not found. Pulling... (This may take a while)")
        # Non-blocking pull isn't ideal for first run, but for simplicity:
        subprocess.run(["ollama", "pull", model_name], check=True)
        print(f"[LLM STARTUP] Model '{model_name}' pulled successfully.")
        return True
    except Exception as e:
        print(f"[LLM STARTUP] Error ensuring model availability: {e}")
    return False

def setup_local_llm(model_name="qwen2.5:1.5b"):
    """Orchestrate Ollama startup and model check."""
    if ensure_ollama_running():
        ensure_model_available(model_name)
    else:
        print("[LLM STARTUP] Warning: Could not verify local LLM setup. App may experience errors.")
