import json
import os
import configparser
import requests
import google.generativeai as genai
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
        with open('knowledge_base.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading knowledge_base.json:", e)
        return {}

knowledge_base = load_knowledge_base()

# ----------------------------
# Initialize Gemini AI
# ----------------------------
def init_gemini():
    api_key = config.get('gemini', 'api_key', fallback='')
    print(f"[DEBUG] Gemini API key from config: {api_key[:20]}..." if len(api_key) > 20 else f"[DEBUG] Gemini API key: {api_key}")
    
    if api_key and api_key != 'YOUR_GEMINI_API_KEY_HERE':
        print("[DEBUG] Initializing Gemini model...")
        genai.configure(api_key=api_key)
        model_name = config.get('gemini', 'model', fallback='gemini-pro')
        print(f"[DEBUG] Using model: {model_name}")
        return genai.GenerativeModel(model_name)
    else:
        print("[DEBUG] Gemini API key not configured or is placeholder")
        return None

gemini_model = init_gemini()


# ----------------------------
# System Prompt
# ----------------------------
SYSTEM_PROMPT = """You are a friendly and helpful AI receptionist for Sylvan Learning of Ballwin.

**Location Information:**
- Address: 14248 G Manchester Rd, Ballwin, MO 63011
- Phone: (636) 552-4351
- Also serving: Chesterfield, Kirkwood, South and North County

**Services Offered:**
- Tutoring: Math, Reading, Writing, Science (K-12)
- Test Prep: SAT, ACT, IB, State Tests, GRE, GED, ASVAB
- Courses: Study Skills, Academic Camps

**Key Information:**
- We offer personalized tutoring that delivers results
- We start with a Sylvan Insight Assessment to pinpoint where your child needs help
- Pricing varies depending on the specific program and your child's needs
- Hours: Generally Monday-Thursday 10am-7pm, Saturdays 9am-1pm (may vary)

**Your Role:**
1. Answer questions about our services, pricing, location, and hours
2. Be friendly, professional, and encouraging
3. When someone wants to schedule an appointment or assessment, respond with: "I can definitely help with that! You can use the calendar below to book a time that works best for you." followed by [CALENDAR_EMBED]
4. Keep responses concise and helpful
5. If you don't know something specific, offer to have them call (636) 552-4351 or book an assessment
6. **Prioritize specific information from the 'Website Information' section over generic answers in the 'Frequently Asked Questions' section.** For example, if the website mentions a specific price or offer (like $49), use that instead of the generic "pricing varies" answer.

**Important:** When users ask to schedule, book, or want an appointment/assessment, ALWAYS include [CALENDAR_EMBED] at the end of your response. Do not forget this marker.
"""

def load_context():
    """Load context from knowledge base and website file to build system prompt."""
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

    # Load Website Context
    try:
        with open('website_context.txt', 'r') as f:
            website_data = f.read()
            context_str += f"\n\n**Website Information:**\n{website_data}"
    except Exception as e:
        print(f"[ERROR] Failed to load website_context.txt: {e}")
        
    return context_str

# Initialize System Prompt with Dynamic Context
DYNAMIC_CONTEXT = load_context()
FULL_SYSTEM_PROMPT = SYSTEM_PROMPT + DYNAMIC_CONTEXT


# ----------------------------
# Gemini Response With Error Flag
# ----------------------------
# ----------------------------
# OpenRouter Fallback
# ----------------------------
def get_openrouter_response(user_message):
    """Fallback to OpenRouter API when Gemini fails."""
    print("[DEBUG] Trying OpenRouter fallback...")
    
    api_key = config.get('openrouter', 'api_key', fallback='')
    model = config.get('openrouter', 'model', fallback='meta-llama/llama-3.2-3b-instruct:free')
    temperature = float(config.get('openrouter', 'temperature', fallback='0.7'))
    
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        
        # Add API key if provided (not required for free models)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": FULL_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature
        }
        
        print(f"[DEBUG] Calling OpenRouter with model: {model}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        ai_response = result['choices'][0]['message']['content']
        print(f"[DEBUG] OpenRouter response: {ai_response[:100]}...")
        return ai_response
        
    except Exception as e:
        print(f"[DEBUG] OpenRouter error: {type(e).__name__}: {e}")
        return "OPENROUTER_FAILED"

# ----------------------------
# Gemini Response With Error Flag
# ----------------------------
def get_gemini_response(user_message):
    """Try Gemini, return fallback flag on error."""
    print(f"[DEBUG] get_gemini_response called with: {user_message[:50]}...")
    print(f"[DEBUG] gemini_model is: {gemini_model}")
    
    if not gemini_model:
        print("[DEBUG] Gemini not available, trying OpenRouter fallback...")
        return get_openrouter_response(user_message)

    try:
        print("[DEBUG] Starting chat...")
        chat = gemini_model.start_chat(history=[])
        full_prompt = f"{FULL_SYSTEM_PROMPT}\n\nUser: {user_message}\nReceptionist:"
        print("[DEBUG] Sending message to Gemini...")
        response = chat.send_message(full_prompt)
        print(f"[DEBUG] Got response: {response.text[:100]}...")
        return response.text
    except Exception as e:
        print(f"[DEBUG] Gemini API error: {type(e).__name__}: {e}")
        print("[DEBUG] Falling back to OpenRouter...")
        return get_openrouter_response(user_message)

# ----------------------------
# Knowledge Base Fallback
# ----------------------------
def search_knowledge_base(message):
    message = message.lower()

    for entry in knowledge_base.get("questions", []):
        keywords = entry.get("keywords", [])
        answer = entry.get("answer", "")

        if any(keyword.lower() in message for keyword in keywords):
            return answer

    return knowledge_base.get(
        "default",
        "I'm not sure I have the exact answer for that, but I'd love to help!"
    )

# ----------------------------
# Final Answer Logic (Gemini → OpenRouter → KB)
# ----------------------------
def find_answer(message):
    ai_response = get_gemini_response(message)

    # If both AI services failed, fallback to knowledge base
    if ai_response in ["OPENROUTER_FAILED"]:
        print("[DEBUG] Both AI services failed, using knowledge base fallback")
        return search_knowledge_base(message)

    return ai_response

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
    response_text = find_answer(user_message)
    print(f"[DEBUG] Raw response before processing: {response_text}")

    # Replace calendar embed
    if '[CALENDAR_EMBED]' in response_text:
        calendar_url = config.get('calendar', 'calendar_url', fallback='')
        if calendar_url:
            calendar_html = f'<div class="calendar-embed"><iframe src="{calendar_url}" style="border: 0" width="100%" height="600" frameborder="0"></iframe></div>'
            response_text = response_text.replace('[CALENDAR_EMBED]', calendar_html)
        else:
            response_text = response_text.replace('[CALENDAR_EMBED]', 'Please contact us at (636) 552-4351 to schedule an appointment.')

    return jsonify({'response': response_text})

# ----------------------------
# Twilio Voice Routes
# ----------------------------
@app.route('/voice', methods=['POST'])
def voice():
    resp = VoiceResponse()

    greet = knowledge_base.get("greeting", "Welcome to Sylvan Learning!")

    gather = resp.gather(
        input='speech',
        action='/voice/handle-input',
        timeout=3,
        speechTimeout='auto'
    )
    gather.say("Welcome to Sylvan Learning. " + greet)

    resp.say("I didn't hear anything. Please call back or visit our website. Goodbye!")
    return str(resp)

@app.route('/voice/handle-input', methods=['POST'])
def voice_handle_input():
    resp = VoiceResponse()
    user_speech = request.values.get('SpeechResult', '').lower()

    if user_speech:
        answer = find_answer(user_speech)

        gather = resp.gather(
            input='speech',
            action='/voice/handle-input',
            timeout=3
        )
        gather.say(answer + " Do you have any other questions?")
    else:
        resp.say("I'm sorry, I didn't catch that.")
        resp.redirect('/voice')

    return str(resp)

# ----------------------------
# Run App
# ----------------------------
if __name__ == '__main__':
    app.run(debug=True, port=5000)
