import requests
import google.generativeai as genai
import time

class LLMManager:
    def __init__(self, config, system_prompt):
        self.config = config
        self.system_prompt = system_prompt
        self.gemini_model = self._init_gemini()

    def _init_gemini(self):
        project_id = self.config.get('gemini', 'project_id', fallback='')
        location = self.config.get('gemini', 'location', fallback='us-central1')
        
        # Authenticate using Vertex AI (assuming default credentials or similar logic as before)
        # Note: The original code used genai.configure(api_key=...).
        # We'll stick to the original implementation logic.
        api_key = self.config.get('gemini', 'api_key', fallback='')
        if api_key and api_key != 'YOUR_GEMINI_API_KEY_HERE':
            genai.configure(api_key=api_key)
            model_name = self.config.get('gemini', 'model', fallback='gemini-pro')
            return genai.GenerativeModel(model_name)
        return None

    def get_local_response(self, user_message, history, dynamic_context=""):
        """Support for local OpenAI-compatible endpoints (Ollama, LM Studio)."""
        base_url = self.config.get('local', 'base_url', fallback='http://localhost:11434/v1')
        model = self.config.get('local', 'model', fallback='qwen2.5:1.5b')
        api_key = self.config.get('local', 'api_key', fallback='lm-studio')
        
        if not base_url.endswith('/chat/completions'):
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            url = base_url

        print(f"[DEBUG] Trying Local LLM: {url} with model {model}")
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            system_content = self.system_prompt
            if dynamic_context:
                system_content += "\n\n**Relevant Context:**\n" + dynamic_context
                
            messages = [{"role": "system", "content": system_content}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3, # Lowered from 0.5 for more focus
                "top_p": 0.9,       # Slightly increased for better vocabulary variety
                "max_tokens": 150,   # Reduced as we want concise answers
                "frequency_penalty": 0.2, # Slightly increased to avoid repetition
                "presence_penalty": 0.1
            }
            
            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            latency = time.time() - start_time
            print(f"[DEBUG] Local LLM Response Latency: {latency:.2f}s")
            
            if response.status_code != 200:
                print(f"[DEBUG] Local LLM Error: {response.text}")
                return "LOCAL_FAILED"
                
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"[DEBUG] Local LLM connectivity error: {e}")
            return "LOCAL_FAILED"

    def get_openai_response(self, user_message, history):
        """Direct OpenAI API support."""
        api_key = self.config.get('openai', 'api_key', fallback='')
        model = self.config.get('openai', 'model', fallback='gpt-4o-mini')
        
        if not api_key or api_key == 'YOUR_OPENAI_API_KEY':
            return "OPENAI_FAILED"

        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code != 200:
                print(f"[DEBUG] OpenAI Error: {response.text}")
                return "OPENAI_FAILED"
                
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"[DEBUG] OpenAI connectivity error: {e}")
            return "OPENAI_FAILED"

    def get_openrouter_response(self, user_message, history):
        """Fallback to OpenRouter API."""
        print("[DEBUG] Trying OpenRouter fallback...")
        api_key = self.config.get('openrouter', 'api_key', fallback='')
        model = self.config.get('openrouter', 'model', fallback='meta-llama/llama-3.2-3b-instruct:free')
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code != 200:
                print(f"[DEBUG] OpenRouter Error: {response.text}")
                return "OPENROUTER_FAILED"
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"[DEBUG] OpenRouter error: {type(e).__name__}: {e}")
            return "OPENROUTER_FAILED"

    def get_gemini_response(self, user_message, history):
        """Try Gemini."""
        if not self.gemini_model:
            return "GEMINI_NOT_CONFIGURED"
        try:
            # Construct chat with history manually for Gemini
            # Note: Gemini history format is different, but for simplicity we rely on string concatenation here 
            # or we could map standard messages to Gemini content objects.
            # Sticking to the previous simpler prompt concatenation strategy for stability.
            
            history_str = ""
            for msg in history:
                role_name = "User" if msg["role"] == "user" else "Receptionist"
                history_str += f"{role_name}: {msg['content']}\n"

            full_prompt = f"{self.system_prompt}\n\nConversation History:\n{history_str}\nUser: {user_message}\nReceptionist:"
            
            chat = self.gemini_model.start_chat(history=[])
            response = chat.send_message(full_prompt)
            return response.text
        except Exception as e:
            print(f"[DEBUG] Gemini API error: {e}")
            return "GEMINI_FAILED"

    def get_response(self, user_message, history):
        """Dispatch to the configured LLM provider with fallback."""
        provider = self.config.get('llm', 'provider', fallback='gemini').lower()
        
        response = None
        
        # Primary Provider
        if provider == 'local':
            response = self.get_local_response(user_message, history)
            # FORCE LOCAL ONLY: Return result immediately, even if it failed.
            # If it failed, the app will receive "LOCAL_FAILED" and handle it (likely calling KB).
            return response
            
            # Legacy fallback logic below is bypassed for 'local' provider
            # if response != "LOCAL_FAILED": return response
            # print("[WARN] Local LLM failed. Falling back to OpenAI (if configured).")
            
            # Fallback 1: OpenAI
            response = self.get_openai_response(user_message, history)
            if response != "OPENAI_FAILED": return response
            print("[WARN] OpenAI fallback failed. Falling back to Gemini.")

        elif provider == 'openai':
             response = self.get_openai_response(user_message, history)
             if response != "OPENAI_FAILED": return response
             print("[WARN] OpenAI failed. Falling back to Gemini.")

        elif provider == 'openrouter':
            response = self.get_openrouter_response(user_message, history)
            if response != "OPENROUTER_FAILED": return response

        # Default / Ultimate Fallback: Gemini
        response = self.get_gemini_response(user_message, history)
        if response not in ["GEMINI_FAILED", "GEMINI_NOT_CONFIGURED"]: return response
        
        # If Gemini fails, try OpenRouter as last resort if not already tried
        if provider != 'openrouter':
             return self.get_openrouter_response(user_message, history)
             
        return None
