import requests
import json
import sys

def test_local_llm():
    base_url = "http://localhost:11434/v1"
    model = "llama3.2"
    api_key = "lm-studio"
    
    print(f"Testing Local LLM at {base_url} with model {model}...")
    
    # 1. Test basic connectivity (list models)
    try:
        print("1. Checking connection and available models...")
        models_url = f"{base_url.rstrip('/v1')}/api/tags" # Ollama specific usually
        # But for OpenAI compatible endpoints (Ollama serves this too at /v1/models)
        models_url_v1 = f"{base_url}/models"
        
        print(f"   GET {models_url_v1}")
        response = requests.get(models_url_v1, timeout=5)
        if response.status_code == 200:
            print("   SUCCESS. Models available:")
            data = response.json()
            # Handle different formats
            if 'data' in data:
                for m in data['data']:
                    print(f"    - {m.get('id')}")
            else:
                 print(f"    Raw: {data}")
        else:
            print(f"   FAILED to list models. Status: {response.status_code}, Body: {response.text}")
            
    except Exception as e:
        print(f"   CONNECTION FAILED: {e}")
        print("   Is the local LLM server (Ollama/LM Studio) running?")
        # Return here as we likely can't chat
        
    # 2. Test Chat Completion
    print("\n2. Testing Chat Completion...")
    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hello, are you working?"}],
        "temperature": 0.7
    }
    
    try:
        print(f"   POST {url}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"   SUCCESS. Response: {content}")
        else:
            print(f"   FAILED. Status: {response.status_code}")
            print(f"   Body: {response.text}")
            
    except Exception as e:
        print(f"   CHAT FAILED: {e}")

if __name__ == "__main__":
    test_local_llm()
