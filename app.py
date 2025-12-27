import json
import os
import configparser
import re
import requests
import google.generativeai as genai
import time
import uuid
from flask import Flask, render_template, request, jsonify
from twilio.twiml.voice_response import VoiceResponse
from llm_manager import LLMManager
from llm_startup import setup_local_llm
# from tts_manager import TTSManager  # Removed to save memory (loads torch)
from flask import send_from_directory

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
    
    prompt = f"""You are {persona.get('role', 'a helpful assistant')}.

**Business Information:**
- **Name:** {biz.get('name', '')}
- **Location:** {biz.get('location', '')}
- **Phone:** {biz.get('contact', {}).get('phone', '')}
- **Description:** {biz.get('description', '')}
- **Services:** {', '.join(config.get('services', []))}
"""
    
    if config.get('key_selling_points'):
        prompt += "\n**Why Choose Us:**\n"
        for point in config.get('key_selling_points', []):
            prompt += f"- {point}\n"
    
    if config.get('special_offers'):
        prompt += "\n**Current Special Offers:**\n"
        for offer in config.get('special_offers', []):
            prompt += f"- {offer}\n"

    prompt += "\n**Your Personality & Tone:**\n"
    for trait in persona.get('tone', []):
        prompt += f"- {trait}\n"

    # Parse the new conversation_flow structure
    conv_flow = persona.get('conversation_flow', {})
    
    if conv_flow:
        prompt += "\n**CONVERSATION FLOW - FOLLOW THESE STEPS IN ORDER:**\n\n"
        
        # STEP 1: Greeting
        step1 = conv_flow.get('step_1_greeting', {})
        if step1:
            prompt += f"**STEP 1 - GREETING AND INTENT ({step1.get('goal', '')})**\n"
            prompt += f"Opening line: \"{step1.get('opening_line', '')}\"\n\n"
            
            if_vague = step1.get('if_vague', {})
            if if_vague:
                prompt += f"If caller is vague ({if_vague.get('trigger', '')}), say:\n"
                prompt += f"\"{if_vague.get('response', '')}\"\n\n"
            
            branching = step1.get('branching', {})
            if branching:
                prompt += "Branch based on intent:\n"
                for key, value in branching.items():
                    prompt += f"- {key.replace('_', ' ').title()}: {value}\n"
            prompt += "\n"
        
        # STEP 2: Know the Caller
        step2 = conv_flow.get('step_2_know_caller', {})
        if step2:
            prompt += f"**STEP 2 - KNOW THE CALLER ({step2.get('goal', '')})**\n"
            sequence = step2.get('sequence', [])
            if sequence:
                prompt += "Sequence:\n"
                for item in sequence:
                    prompt += f"- {item}\n"
            
            rules = step2.get('rules', [])
            if rules:
                prompt += "\nRules:\n"
                for rule in rules:
                    prompt += f"- {rule}\n"
            prompt += "\n"
        
        # STEP 3: Book Assessment
        step3 = conv_flow.get('step_3_book_assessment', {})
        if step3:
            prompt += f"**STEP 3 - BOOK ASSESSMENT ({step3.get('goal', '')})**\n"
            prompt += f"Trigger: {step3.get('trigger', '')}\n\n"
            prompt += f"Core script: \"{step3.get('core_script', '')}\"\n\n"
            
            if_yes = step3.get('if_yes', {})
            if if_yes:
                prompt += f"If YES / short positive ({', '.join(if_yes.get('short_positive', []))}):\n"
                prompt += f"- Say: \"{if_yes.get('response', '')}\"\n"
                prompt += f"- Then: \"{if_yes.get('then', '')}\"\n"
                prompt += f"- After booking: \"{if_yes.get('after_booking', '')}\"\n\n"
            
            if_hesitant = step3.get('if_hesitant', {})
            if if_hesitant:
                prompt += f"If they hesitate ({', '.join(if_hesitant.get('trigger', []))}):\n"
                prompt += f"\"{if_hesitant.get('response', '')}\"\n\n"
            
            if_decline = step3.get('if_decline', {})
            if if_decline:
                prompt += f"If they clearly decline assessment:\n"
                prompt += f"\"{if_decline.get('response', '')}\"\n\n"
        
        # STEP 4: Director Callback
        step4 = conv_flow.get('step_4_director_callback', {})
        if step4:
            prompt += f"**STEP 4 - DIRECTOR CALLBACK ({step4.get('goal', '')})**\n"
            triggers = step4.get('triggers', [])
            if triggers:
                prompt += "Use this ONLY for:\n"
                for trigger in triggers:
                    prompt += f"- {trigger}\n"
            
            prompt += f"\nScript: \"{step4.get('script', '')}\"\n"
            prompt += f"Confirm number: \"{step4.get('confirm_number', '')}\"\n"
            prompt += f"Ask time: \"{step4.get('ask_time', '')}\"\n"
            prompt += f"Then close: \"{step4.get('close', '')}\"\n\n"
        
        # STEP 5: Close
        step5 = conv_flow.get('step_5_close', {})
        if step5:
            prompt += f"**STEP 5 - CLOSE THE CALL ({step5.get('goal', '')})**\n"
            outcomes = step5.get('outcomes', {})
            if outcomes:
                prompt += "Closing lines:\n"
                for key, value in outcomes.items():
                    prompt += f"- {key.replace('_', ' ').title()}: \"{value}\"\n"
            prompt += "\n"
    
    # Special handling rules
    special_rules = persona.get('special_handling_rules', [])
    if special_rules:
        prompt += "**SPECIAL HANDLING RULES:**\n"
        for rule in special_rules:
            prompt += f"- {rule}\n"
        prompt += "\n"

    # Conversation examples
    if config.get('conversation_examples'):
        prompt += "\n**CONVERSATION EXAMPLES:**\n"
        for ex in config.get('conversation_examples', []):
            prompt += f"\nUser: \"{ex['user_input']}\"\n"
            prompt += f"Receptionist: \"{ex['model_response']}\"\n"
            
    return prompt

SYSTEM_PROMPT = build_system_prompt(system_config)

def load_context(user_message=""):
    """Load ONLY relevant context from knowledge base for the user's message."""
    context_str = ""
    try:
        with open('knowledge_base.json', 'r') as f:
            kb_data = json.load(f)
        
        relevant_faqs = []
        user_lower = user_message.lower()
        
        # Simple RAG: Find questions with matching keywords
        if user_lower:
            for q in kb_data.get('questions', []):
                if any(k.lower() in user_lower for k in q.get('keywords', [])):
                    relevant_faqs.append(q)
        
        # If no specific matches, include some general info
        if not relevant_faqs:
             # Basic info about location/hours is often useful
             for q in kb_data.get('questions', []):
                 if any(k in q.get('keywords', []) for k in ['location', 'hours', 'open']):
                     relevant_faqs.append(q)

        if relevant_faqs:
            context_str += "\n\n**Frequently Asked Questions:**\n"
            for q in relevant_faqs[:5]: # Limit to 5 most relevant
                context_str += f"- Q: {', '.join(q['keywords'])}\n  A: {q['answer']}\n"
    except Exception as e:
        print(f"[ERROR] Failed to load knowledge_base.json: {e}")

    return context_str

# Removed large static DYNAMIC_CONTEXT to save tokens.
# Context will be loaded dynamically per request.

# ----------------------------
# Initialize LLM Manager
# ----------------------------

# System Prompt only (Knowledge Base moved to dynamic loading)
FULL_SYSTEM_PROMPT = SYSTEM_PROMPT
llm_manager = LLMManager(config, FULL_SYSTEM_PROMPT)

# Initialize TTS Manager (Disabled - taking too much time)
# try:
#     tts_manager = TTSManager()
# except Exception as e:
#     print(f"[ERROR] Failed to initialize TTS Manager: {e}")
#     tts_manager = None
tts_manager = None

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

CALM_BLOCKLIST = [
    "unmatched score improvements",
    "incredible", "amazing", "life-changing"
]

def validate_response(user_message, response_text, session=None):
    """Ensure response quality and consistency with the 5-step flow."""
    if not response_text:
        return "Sorry, I didn't quite catch that. Could you say that again a bit differently?"

    user_lower = user_message.lower().strip()
    resp_lower = response_text.lower()

    # --- Calm Validation (User Provided) ---
    # Strip hyped-up phrases
    for phrase in CALM_BLOCKLIST:
        response_text = response_text.replace(phrase, "")

    # Preserve tags
    tags_to_preserve = ["[CALENDAR_EMBED]", "[HANGUP]"]
    preserved_tags = [tag for tag in tags_to_preserve if tag in response_text]

    # Trim to first 2–3 sentences max
    sentences = [s.strip() for s in response_text.split('.') if s.strip()]
    if len(sentences) > 3:
        response_text = '. '.join(sentences[:3]) + '.'
    
    # Re-apply tags if they were trimmed but were in the original
    for tag in preserved_tags:
        if tag not in response_text:
            response_text += " " + tag

    # Re-evaluate resp_lower after stripping/trimming
    resp_lower = response_text.lower()

    # --- Short reply handling based on new flow ---
    reply_type = classify_short_reply(user_message)
    last_bot_msg = None
    if session and session.history and len(session.history) > 0:
        # Find the last assistant message
        for msg in reversed(session.history):
            if msg['role'] == 'assistant':
                last_bot_msg = msg['content'].lower()
                break

    # Access scripted responses
    scripts = conversation_config.get('responses', {})

    # ONLY override if the AI response is very short or failed
    is_poor_response = not response_text or len(response_text.split()) < 4 or "not sure" in resp_lower or "don't know" in resp_lower

    if is_poor_response:
        if reply_type == "affirmative" and last_bot_msg:
            # If last message was asking about booking assessment
            if any(k in last_bot_msg for k in ['assessment', 'checkup', 'book that', 'want to book', 'calendar now']):
                response_text = scripts.get('affirmative_scheduling', 
                    "Great. Do weekdays after school or Saturdays work better for you?"
                )
            # If asking about time preference
            elif any(k in last_bot_msg for k in ['weekdays', 'saturdays', 'work better', 'time']):
                response_text = "Perfect. I'll find a time there. You can pick a slot on our calendar here: [CALENDAR_EMBED]"
            elif "price" in last_bot_msg or "cost" in last_bot_msg:
                response_text = scripts.get('pricing_needs_info',
                    "Got it. To give you an exact price, I just need your child's grade and what subject they're struggling with?"
                )

        elif reply_type == "uncertain":
            response_text = scripts.get('uncertain_offer',
                "That makes sense. The assessment is the best way to know exactly what they need, and it's just $29 right now. Would you like to lock in a time and then talk through details at the center?"
            )

        elif reply_type == "small_talk":
            response_text = scripts.get('greeting_small_talk',
                "Hi! I'm here to help. What's going on with your child's learning?"
            )

    # --- Enhanced calendar / scheduling logic for new flow ---
    # Detect if user just gave affirmative response to assessment booking
    affirmative_keywords = ['yes', 'yeah', 'sure', 'ok', 'okay', 'please', 'i would', "i'd like", 'go ahead', 'sounds good']
    is_affirmative = any(phrase in user_lower for phrase in affirmative_keywords)
    
    # Check if we're in the assessment booking stage
    if session and session.history and last_bot_msg:
        was_offering_assessment = any(k in last_bot_msg for k in ['$29 assessment', 'book that on our calendar', 'want to book'])
        was_asking_time_preference = any(k in last_bot_msg for k in ['weekdays', 'saturdays', 'work better for you'])
        
        # If user said yes to assessment, ask about time preference
        if is_affirmative and was_offering_assessment and '[CALENDAR_EMBED]' not in response_text:
            if 'weekdays' not in resp_lower and 'saturdays' not in resp_lower:
                response_text = "Great. Do weekdays after school or Saturdays work better for you?"
        
        # If user chose time preference, show calendar
        elif (is_affirmative or 'weekday' in user_lower or 'saturday' in user_lower or 'weekend' in user_lower) and was_asking_time_preference:
            if '[CALENDAR_EMBED]' not in response_text:
                response_text = "Perfect. I'll find a time there. You can pick a slot on our calendar here: [CALENDAR_EMBED]"

    # General scheduling keywords - IMMEDIATELY show calendar when user asks about scheduling
    scheduling_keywords = ['schedule', 'book', 'appointment', 'visit', 'assessment', 'checkup', 'when can', 'available']
    if any(k in user_lower for k in scheduling_keywords) and '[CALENDAR_EMBED]' not in response_text:
        # Show calendar immediately when user mentions scheduling, regardless of AI response
        if "director" not in resp_lower:  # Don't show calendar if directing to callback
            if '[CALENDAR_EMBED]' not in response_text:
                response_text += " You can pick a time on our calendar: [CALENDAR_EMBED]"

    # Final Length Check
    if not response_text or len(response_text) < 5:
        response_text = "Sorry, I didn't quite catch that. Could you say that again a bit differently?"

    # --- Reschedule / Notify Logic ---
    # Heuristic: If bot says "director" and "let" or "know" in response to a reschedule intent, assume it's done.
    if "director" in resp_lower and (("call" in resp_lower and "you" in resp_lower) or "reach out" in resp_lower):
        print(f"[DUMMY NOTIFICATION] Sending email to director regarding: {user_message}")

    # --- Offline/Fallback Data Capture ---
    # If the response is the default fallback, but we detect a phone number, override it.
    phone_pattern = re.compile(r'\d[\d\s\-\.]{6,}\d') 
    if "not 100% sure" in response_text and phone_pattern.search(user_message):
        response_text = "Looking forward to serve you or sorry I could not be of much help. I have noted your number. Director will reach out. [HANGUP]"
        print(f"[OFFLINE CAPTURE] Captured contact info: {user_message}")

    # --- Enforce one question at a time ---
    # Count question marks - if more than 1, it's asking multiple questions
    question_count = response_text.count('?')
    if question_count > 1:
        # Keep only the first question
        first_question_end = response_text.find('?') + 1
        response_text = response_text[:first_question_end]
        # Re-add preserved tags if needed
        for tag in preserved_tags:
            if tag not in response_text:
                response_text += " " + tag

    return response_text

# ----------------------------
# Main Logic
# ----------------------------

def find_answer(message, session_id):
    _, session = get_session(session_id)
    
    # Dynamically build context for this specific message
    dynamic_context = load_context(message)
    
    # Get Response via Manager
    ai_response = llm_manager.get_local_response(message, session.history, dynamic_context=dynamic_context)
    
    # Final Fallback to Knowledge Base Search if all LLMs fail
    if ai_response in ["OPENROUTER_FAILED", "LOCAL_FAILED", "OPENAI_FAILED", "GEMINI_FAILED", "GEMINI_NOT_CONFIGURED"] or not ai_response:
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
        # Web-specific phrasing: Add "below" if not present
        if 'below' not in response_text.lower():
            response_text = response_text.replace('on our calendar', 'on our calendar below')

        calendar_url = config.get('calendar', 'calendar_url', fallback='')
        if calendar_url:
            calendar_html = f'<div class="calendar-embed"><iframe src="{calendar_url}" style="border: 0" width="100%" height="600" frameborder="0"></iframe></div>'
            response_text = response_text.replace('[CALENDAR_EMBED]', calendar_html)
        else:
            response_text = response_text.replace(
                '[CALENDAR_EMBED]',
                'Please contact us at (636) 552-4351 to schedule an appointment.'
            )
    
    # Generate human-like audio (Disabled)
    audio_file = ""
    # if tts_manager:
    #     # Strip tags for audio generation
    #     clean_text = response_text.replace('[CALENDAR_EMBED]', '').replace('<div class="calendar-embed">', '').replace('</div>', '')
    #     # Basic heuristic to avoid generating audio for very long HTML if any left
    #     if len(clean_text) < 1000:
    #         audio_file = tts_manager.generate_audio(clean_text)
            
    audio_url = f"/api/audio/{audio_file}" if audio_file else ""
    
    return jsonify({
        'response': response_text, 
        'session_id': session_id,
        'audio_url': audio_url
    })

@app.route('/api/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(os.path.join('static', 'audio'), filename)

# ----------------------------
# Twilio Voice Routes
# ----------------------------

@app.route('/voice', methods=['POST'])
def voice():
    resp = VoiceResponse()
    greet = knowledge_base.get("greeting", "Welcome to Sylvan Learning!")
    # Use 'alice' for a standard female voice, or specify language/voice
    gather = resp.gather(input='speech', action='/voice/handle-input', timeout=3)
    gather.say("Welcome to Sylvan Learning. " + greet, voice='alice')
    resp.say("I didn't hear anything. Please call back. Goodbye!", voice='alice')
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
            gather.say(msg, voice='alice')
            return str(resp)
        elif reply_type == "uncertain":
            gather = resp.gather(input='speech', action='/voice/handle-input', timeout=3)
            msg = scripts.get('voice_uncertain_offer', "That’s okay. Would you like a quick overview of our programs, or do you prefer to talk about pricing first?")
            gather.say(msg, voice='alice')
            return str(resp)

        # Fallback to full AI flow
        answer = find_answer(user_speech, None)
        
        # Check for HANGUP token
        should_hangup = False
        if '[HANGUP]' in answer:
            should_hangup = True
            answer = answer.replace('[HANGUP]', '').strip()

        # Custom voice-friendly phrasing
        voice_answer = answer.replace('[CALENDAR_EMBED]', '')
        voice_answer = voice_answer.replace('on our calendar', 'on our website calendar')
        voice_answer = voice_answer.replace('below', 'online')
        voice_answer = voice_answer.replace('Pick a time', 'Check our availability on our website')
        voice_answer = voice_answer.replace('select a time', 'check our calendar online')
        # Fix grammar that might arise from simple replacement
        voice_answer = voice_answer.replace('on our calendar on our website', 'on our website calendar')
        voice_answer = voice_answer.replace('Select a time on our website:', 'You can pick a time on our website.')
        
        gather = resp.gather(input='speech', action='/voice/handle-input', timeout=3)
        gather.say(voice_answer, voice='alice')
        
        if should_hangup:
             resp.hangup()
        else:
             # Use VibeVoice audio for Twilio if available (Disabled)
             # if tts_manager:
             #     audio_file = tts_manager.generate_audio(voice_answer)
             #     if audio_file:
             #         # Twilio needs absolute URL. We assume the app is accessible.
             #         # For local testing, this might need Ngrok.
             #         base_url = request.url_root.rstrip('/')
             #         audio_url = f"{base_url}/api/audio/{audio_file}"
             #         resp.play(audio_url)
             #     else:
             #         resp.say(voice_answer, voice='alice')
             # else:
             #     resp.say(voice_answer, voice='alice')
             resp.say(voice_answer, voice='alice')
             resp.append(gather)
    else:
        resp.say("I didn't catch that.", voice='alice')
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
    # Start local LLM if needed
    local_model = config.get('local', 'model', fallback='qwen2.5:1.5b')
    setup_local_llm(local_model)
    
    app.run(debug=True, port=5000)
