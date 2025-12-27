"""
Test script to verify local LLM is using the full system context properly.
"""
import configparser
import json
from llm_manager import LLMManager

def load_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

def load_system_context():
    with open('system_context.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_knowledge_base():
    with open('knowledge_base.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def build_system_prompt(config):
    if not config:
        return "You are a helpful AI assistant."

    biz = config.get('business_profile', {})
    persona = config.get('agent_persona', {})
    
    prompt = f"""You are a {persona.get('role', 'Helpful Assistant')} for {biz.get('name', 'this business')}. {biz.get('description', '')}

**Your Personality:**
"""
    for trait in persona.get('tone', []):
        prompt += f"- {trait}\n"

    prompt += f"""
**Key Information:**
- **Location:** {biz.get('location', '')}
- **Phone:** {biz.get('contact', {}).get('phone', '')}
- **Services:** {', '.join(config.get('services', []))}
"""
    
    if config.get('key_selling_points'):
         prompt += "- **Why Choose Us:** " + " ".join(config.get('key_selling_points', [])) + "\n"
    
    if config.get('special_offers'):
        prompt += "\n**Current Special Offers:**\n"
        for offer in config.get('special_offers', []):
            prompt += f"- {offer}\n"

    prompt += "\n**Response Guidelines:**\n"
    for idx, rule in enumerate(persona.get('instructions', []), 1):
        prompt += f"{idx}. {rule}\n"

    if config.get('conversation_examples'):
        prompt += "\n**Conversation Flow Examples:**\n"
        for ex in config.get('conversation_examples', []):
            prompt += f"\n*User: \"{ex['user_input']}\"*\n*Receptionist: \"{ex['model_response']}\"*\n"
            
    return prompt

def load_context():
    """Load context from knowledge base to build system prompt extension."""
    context_str = ""
    try:
        with open('knowledge_base.json', 'r') as f:
            kb_data = json.load(f)
        context_str += "\n\n**Frequently Asked Questions:**\n"
        for q in kb_data.get('questions', []):
            context_str += f"- Q: {', '.join(q['keywords'])}\n  A: {q['answer']}\n"
    except Exception as e:
        print(f"[ERROR] Failed to load knowledge_base.json: {e}")
    return context_str

def main():
    print("=" * 60)
    print("Testing Local LLM with Full Context")
    print("=" * 60)
    
    # Load everything
    config = load_config()
    system_config = load_system_context()
    kb = load_knowledge_base()
    
    # Build prompts
    system_prompt = build_system_prompt(system_config)
    dynamic_context = load_context()
    full_prompt = system_prompt + dynamic_context
    
    print("\n📋 SYSTEM PROMPT LENGTH:", len(full_prompt), "characters")
    print("\n📋 FIRST 500 CHARS OF PROMPT:")
    print("-" * 60)
    print(full_prompt[:500])
    print("...")
    print("-" * 60)
    
    # Initialize LLM Manager
    llm_manager = LLMManager(config, full_prompt)
    
    # Test queries
    test_queries = [
        "Hi, how much is tutoring?",
        "Do you do SAT prep?",
        "Where are you located?",
        "My kid is struggling with math",
        "What are your hours?"
    ]
    
    print("\n🧪 TESTING QUERIES:")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n[Test {i}] User: {query}")
        print("-" * 60)
        
        # Empty history for each test
        history = []
        response = llm_manager.get_local_response(query, history)
        
        if response == "LOCAL_FAILED":
            print("❌ LOCAL LLM FAILED")
        else:
            print(f"✅ Response: {response}")
        
        print("-" * 60)

if __name__ == "__main__":
    main()
