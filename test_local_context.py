"""
Simplified test to verify local LLM uses full context properly.
"""
import requests
import json
import configparser

def test_local_llm_with_context():
    # Load config
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    base_url = config.get('local', 'base_url', fallback='http://localhost:11434/v1')
    model = config.get('local', 'model', fallback='llama3.2')
    api_key = config.get('local', 'api_key', fallback='lm-studio')
    
    # Load all context files
    with open('system_context.json', 'r', encoding='utf-8') as f:
        system_config = json.load(f)
    
    with open('knowledge_base.json', 'r', encoding='utf-8') as f:
        kb = json.load(f)
    
    # Build system prompt (simplified version)
    biz = system_config.get('business_profile', {})
    persona = system_config.get('agent_persona', {})
    
    system_prompt = f"""You are an {persona.get('role')} for {biz.get('name')}.

CRITICAL INSTRUCTIONS:
{chr(10).join(persona.get('instructions', []))}

BUSINESS INFO:
- Location: {biz.get('location')}
- Phone: {biz.get('contact', {}).get('phone')}
- Services: {', '.join(system_config.get('services', []))}

SPECIAL OFFERS:
{chr(10).join('- ' + offer for offer in system_config.get('special_offers', []))}

EXAMPLE RESPONSES:
"""
    
    for ex in system_config.get('conversation_examples', []):
        system_prompt += f"User: {ex['user_input']}\nYou: {ex['model_response']}\n\n"
    
    # Add KB FAQs
    system_prompt += "\nFREQUENTLY ASKED QUESTIONS:\n"
    for q in kb.get('questions', [])[:5]:  # First 5 to keep it manageable
        system_prompt += f"Keywords: {', '.join(q['keywords'])}\nAnswer: {q['answer']}\n\n"
    
    print("=" * 70)
    print("TESTING LOCAL LLM WITH FULL CONTEXT")
    print("=" * 70)
    print(f"\n📊 System Prompt Length: {len(system_prompt)} characters")
    print(f"📊 Model: {model}")
    print(f"📊 Endpoint: {base_url}")
    
    # Test queries
    test_cases = [
        {
            "query": "Hi, how much is tutoring?",
            "expected_keywords": ["$49", "assessment", "checkup"]
        },
        {
            "query": "Do you do SAT prep?",
            "expected_keywords": ["SAT", "ACT", "free practice"]
        },
        {
            "query": "My kid is struggling with math",
            "expected_keywords": ["assessment", "$49", "schedule", "book"]
        }
    ]
    
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}: {test['query']}")
        print('='*70)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": test['query']}
        ]
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 150
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content']
                
                print(f"\n✅ Response:\n{ai_response}")
                
                # Check if expected keywords are present
                print(f"\n📋 Expected Keywords: {', '.join(test['expected_keywords'])}")
                found = [kw for kw in test['expected_keywords'] if kw.lower() in ai_response.lower()]
                missing = [kw for kw in test['expected_keywords'] if kw.lower() not in ai_response.lower()]
                
                if found:
                    print(f"✅ Found: {', '.join(found)}")
                if missing:
                    print(f"⚠️  Missing: {', '.join(missing)}")
                    
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print('='*70)

if __name__ == "__main__":
    test_local_llm_with_context()
