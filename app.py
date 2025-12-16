import json
import os
import configparser
import requests
import google.generativeai as genai
import time
import uuid
from flask import Flask, render_template, request, jsonify
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

# ----------------------------
# Load Configuration
# ----------------------------

def load_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

config = load_config()

# ----------------------------
# Load Knowledge Base JSON
# ----------------------------

def load_knowledge_base():
    try:
        with open('knowledge_base.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading knowledge_base.json:", e)
        return {}

def load_conversation_config():
    try:
        with open('conversation_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading conversation_config.json:", e)
        return {}

knowledge_base = load_knowledge_base()
conversation_config = load_conversation_config()

# ----------------------------
# Conversation Memory
# ----------------------------

conversations = {}

class ConversationSession:
    def __init__(self):
        self.history = []
        self.last_active = time.time()
        self.context = {}

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})
        self.last_active = time.time()
        # Keep history manageable - last 10 messages (5 turns)
        if len(self.history) > 10:
            self.history = self.history[-10:]

    def get_history_string(self):
        history_str = ""
        for msg in self.history:
            role_name = "User" if msg["role"] == "user" else "Receptionist"
            history_str += f"{role_name}: {msg['content']}\n"
        return history_str

def get_session(session_id):
    # Clean up old sessions first
    cleanup_sessions()
    if not session_id or session_id not in conversations:
        session_id = str(uuid.uuid4())
        conversations[session_id] = ConversationSession()
    return session_id, conversations[session_id]

def cleanup_sessions():
    current_time = time.time()
    # Remove sessions older than 30 minutes
    timeout = 30 * 60
    expired = [sid for sid, session in conversations.items()
               if current_time - session.last_active > timeout]
    for sid in expired:
        del conversations[sid]

# ----------------------------
# Initialize Gemini AI
# ----------------------------

def init_gemini():
    api_key = config.get('gemini', 'api_key', fallback='')
    if api_key and api_key != 'YOUR_GEMINI_API_KEY_HERE':
        genai.configure(api_key=api_key)
        model_name = config.get('gemini', 'model', fallback='gemini-pro')
        return genai.GenerativeModel(model_name)
    else:
        return None

gemini_model = init_gemini()

# ----------------------------
# System Prompt & Context
# ----------------------------

def load_system_context():
    """Load business-specific context from JSON."""
    try:
        with open('system_context.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading system_context.json: {e}")
        return {}

system_config = load_system_context()

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

SYSTEM_PROMPT = build_system_prompt(system_config)

def load_context():
    """Load context from knowledge base to build system prompt extension."""
    context_str = ""
    # Load Knowledge Base
    try:
        with open('knowledge_base.json', 'r') as f:
            kb_data = json.load(f)
        context_str += "\n\n**Frequently Asked Questions:**\n"
        for q in kb_data.get('questions', []):
            context_str += f"- Q: {', '.join(q['keywords'])}\n  A: {q['answer']}\n"
    except Exception as e:
        print(f"[ERROR] Failed to load knowledge_base.json: {e}")

    return context_str

DYNAMIC_CONTEXT = load_context()

# ----------------------------
# Backchannel / Short Reply Handling
# ----------------------------

def classify_short_reply(user_text: str) -> str:
    """
    Very small heuristic classifier for short / vague replies.
    Returns: 'affirmative', 'uncertain', 'small_talk', or 'other'.
    """
    text = user_text.strip().lower()
    keywords = conversation_config.get('keywords', {})
    
    if len(text.split()) <= 3:
        if any(p in text for p in keywords.get('affirmative', [])):
            return "affirmative"
        if any(p in text for p in keywords.get('uncertain', [])):
            return "uncertain"
        if any(p in text for p in keywords.get('small_talk', [])):
            return "small_talk"
    return "other"

# ----------------------------
# Response Validation & Post-Processing
# ----------------------------

def validate_response(user_message, response_text, session=None):
    """Ensure response quality and consistency."""
    user_lower = user_message.lower().strip()
    resp_lower = response_text.lower()

    # --- Short reply handling ---
    reply_type = classify_short_reply(user_message)
    last_bot_msg = None
    if session and session.history and session.history[-1]['role'] == 'assistant':
        last_bot_msg = session.history[-1]['content'].lower()

    # Access scripted responses
    scripts = conversation_config.get('responses', {})

    # If last bot message was offering to schedule and user says yes/ok/etc.
    if reply_type == "affirmative" and last_bot_msg:
        if any(k in last_bot_msg for k in ['schedule', 'book', 'assessment', 'checkup', 'appointment', 'time', 'availability']):
            response_text = scripts.get('affirmative_scheduling', 
                "Awesome. What works better for you—weekdays after school or weekends?"
            )
        elif "price" in last_bot_msg or "cost" in last_bot_msg:
            response_text = scripts.get('pricing_needs_info',
                "Got it. To give you an exact price, I just need your child's grade and what subject they're struggling with?"
            )

    elif reply_type == "uncertain":
        response_text = scripts.get('uncertain_offer',
            "Totally fair. Want a quick rundown of how we work, or should we just book the $49 checkup?"
        )

    elif reply_type == "small_talk" and not response_text:
        response_text = scripts.get('greeting_small_talk',
            "Hi! I'm here to help. What's going on with your child's learning?"
        )

    # --- Existing calendar / scheduling logic ---
    if session and session.history:
        if len(session.history) > 0 and session.history[-1]['role'] == 'assistant':
            last_bot_msg = session.history[-1]['content'].lower()
            affirmative_responses = ['yes', 'sure', 'ok', 'okay', 'please', 'i would', 'id like that', 'go ahead']
            is_affirmative = any(phrase in user_lower for phrase in affirmative_responses)
            was_offering_schedule = any(k in last_bot_msg for k in ['schedule', 'book', 'assessment', 'checkup', 'time'])
            if is_affirmative and was_offering_schedule and '[CALENDAR_EMBED]' not in response_text:
                if "calendar" not in resp_lower:
                    response_text += "\n\nAwesome. Pick a time right here:\n[CALENDAR_EMBED]"
                else:
                    response_text += "\n[CALENDAR_EMBED]"

    scheduling_keywords = ['schedule', 'book', 'appointment', 'visit', 'cost', 'price', 'checkup', 'assessment', 'weekdays', 'weekends', 'morning', 'afternoon', 'evening']
    if any(k in user_lower for k in scheduling_keywords) and '[CALENDAR_EMBED]' not in response_text:
        if "calendar" not in resp_lower:
            response_text += "\n\nLet's get you on the books. Pick a time:\n[CALENDAR_EMBED]"
        else:
            response_text += "\n[CALENDAR_EMBED]"

    # 2. Check for empty response
    if not response_text or len(response_text) < 5:
        response_text = "Sorry, missed that. Could you say it again?"

    # --- Reschedule / Notify Logic ---
    # Heuristic: If bot says "director" and "let" or "know" in response to a reschedule intent, assume it's done.
    # Ideally, we should parse intent more robustly, but this works for the "dummy" phase.
    if "director" in resp_lower and ("know" in resp_lower or "email" in resp_lower or "message" in resp_lower):
         print(f"[DUMMY NOTIFICATION] Sending email to director regarding: {user_message}")

    return response_text

# ----------------------------
# OpenRouter Fallback
# ----------------------------

def get_openrouter_response(user_message, session):
    """Fallback to OpenRouter API with history."""
    print("[DEBUG] Trying OpenRouter fallback...")
    api_key = config.get('openrouter', 'api_key', fallback='')
    model = config.get('openrouter', 'model', fallback='meta-llama/llama-3.2-3b-instruct:free')
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        # Build messages with history
        messages = [{"role": "system", "content": SYSTEM_PROMPT + DYNAMIC_CONTEXT}]
        messages.extend(session.history)
        messages.append({"role": "user", "content": user_message})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7
        }
        print(f"[DEBUG] Calling OpenRouter with model: {model}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            print(f"[DEBUG] OpenRouter Error: {response.text}")
            return "OPENROUTER_FAILED"
        result = response.json()
        ai_response = result['choices'][0]['message']['content']
        return ai_response
    except Exception as e:
        print(f"[DEBUG] OpenRouter error: {type(e).__name__}: {e}")
        return "OPENROUTER_FAILED"

# ----------------------------
# Gemini Response
# ----------------------------

def get_gemini_response(user_message, session):
    """Try Gemini with history."""
    if not gemini_model:
        return get_openrouter_response(user_message, session)
    try:
        # Construct chat with history
        history_str = session.get_history_string()
        full_prompt = f"{SYSTEM_PROMPT + DYNAMIC_CONTEXT}\n\nConversation History:\n{history_str}\nUser: {user_message}\nReceptionist:"
        chat = gemini_model.start_chat(history=[])
        response = chat.send_message(full_prompt)
        return response.text
    except Exception as e:
        print(f"[DEBUG] Gemini API error: {e}")
        return get_openrouter_response(user_message, session)

# ----------------------------
# Main Logic
# ----------------------------

def find_answer(message, session_id):
    _, session = get_session(session_id)
    # Get Response
    ai_response = get_gemini_response(message, session)
    if ai_response == "OPENROUTER_FAILED":
        # from knowledge_base_search import search_knowledge_base  # type: ignore
        ai_response = search_knowledge_base(message, knowledge_base)
    # Validate & Post-process
    final_response = validate_response(message, ai_response, session)
    # Update History
    session.add_message("user", message)
    session.add_message("assistant", final_response)
    return final_response

# ----------------------------
# Web Interface Routes
# ----------------------------

@app.route('/')
def home():
    calendar_url = config.get('calendar', 'calendar_url', fallback='')
    contact_phone = config.get('contact', 'phone', fallback='1-800-EDUCATE')
    contact_email = config.get('contact', 'email', fallback='info@sylvanlearning.com')
    return render_template(
        'index.html',
        calendar_url=calendar_url,
        contact_phone=contact_phone,
        contact_email=contact_email
    )

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    session_id = data.get('session_id')
    # Ensure session exists
    session_id, _ = get_session(session_id)
    response_text = find_answer(user_message, session_id)
    print(f"[DEBUG] Raw response: {response_text}")
    # Replace calendar embed
    if '[CALENDAR_EMBED]' in response_text:
        calendar_url = config.get('calendar', 'calendar_url', fallback='')
        if calendar_url:
            calendar_html = f''
            response_text = response_text.replace('[CALENDAR_EMBED]', calendar_html)
        else:
            response_text = response_text.replace(
                '[CALENDAR_EMBED]',
                'Please contact us at (636) 552-4351 to schedule an appointment.'
            )
    return jsonify({'response': response_text, 'session_id': session_id})

# ----------------------------
# Twilio Voice Routes
# ----------------------------

@app.route('/voice', methods=['POST'])
def voice():
    resp = VoiceResponse()
    greet = knowledge_base.get("greeting", "Welcome to Sylvan Learning!")
    gather = resp.gather(input='speech', action='/voice/handle-input', timeout=3)
    gather.say("Welcome to Sylvan Learning. " + greet)
    resp.say("I didn't hear anything. Please call back. Goodbye!")
    return str(resp)

@app.route('/voice/handle-input', methods=['POST'])
def voice_handle_input():
    resp = VoiceResponse()
    user_speech = request.values.get('SpeechResult', '').lower()

    if user_speech:
        reply_type = classify_short_reply(user_speech)

        # Fast‑path for short affirmations / uncertainty on voice
        scripts = conversation_config.get('responses', {})
        
        if reply_type == "affirmative":
            gather = resp.gather(input='speech', action='/voice/handle-input', timeout=3)
            msg = scripts.get('voice_affirmative_scheduling', "Great. What day and time generally work best for you, weekdays after school or weekends?")
            gather.say(msg)
            return str(resp)
        elif reply_type == "uncertain":
            gather = resp.gather(input='speech', action='/voice/handle-input', timeout=3)
            msg = scripts.get('voice_uncertain_offer', "That’s okay. Would you like a quick overview of our programs, or do you prefer to talk about pricing first?")
            gather.say(msg)
            return str(resp)

        # Fallback to full AI flow
        answer = find_answer(user_speech, None)
        
        # Check for HANGUP token
        should_hangup = False
        if '[HANGUP]' in answer:
            should_hangup = True
            answer = answer.replace('[HANGUP]', '').strip()

        # Strip calendar embed from voice response
        voice_answer = answer.replace('[CALENDAR_EMBED]', '').replace('calendar below', 'our website')
        
        gather = resp.gather(input='speech', action='/voice/handle-input', timeout=3)
        gather.say(voice_answer)
        
        if should_hangup:
             resp.hangup()
        else:
             resp.append(gather)

        if not should_hangup and not "questions" in voice_answer.lower():
             # resp.say("Do you have any other questions?")
             pass
    else:
        resp.say("I didn't catch that.")
        resp.redirect('/voice')

    return str(resp)

# ----------------------------
# Helpers
# ----------------------------

def search_knowledge_base(message, kb):
    """Simple keyword fallback"""
    message = message.lower()
    for entry in kb.get("questions", []):
        if any(keyword.lower() in message for keyword in entry.get("keywords", [])):
            return entry.get("answer", "")
    return kb.get("default", "I'm not sure, but please call us!")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
