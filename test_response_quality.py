import requests
import json
import time

def test_chat(message, session_id=None):
    url = "http://localhost:5000/api/chat"
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def run_diagnostics():
    test_cases = [
        "Hi there, how are you?",
        "Where are you located?",
        "How much does tutoring cost?",
        "Do you have math tutoring for 5th graders?",
        "Yes, I'd like to schedule an assessment for my 7 year old.",
        "That's too expensive.",
        "I need to talk to a human.",
        "I want to reschedule my appointment."
    ]
    
    session_id = None
    print("--- Starting Response Quality Diagnostic ---")
    
    for i, msg in enumerate(test_cases):
        print(f"\n[Test {i+1}] User: {msg}")
        result = test_chat(msg, session_id)
        
        if "error" in result:
            print(f"Error: {result['error']}")
            break
            
        session_id = result.get('session_id')
        print(f"Bot: {result.get('response')}")
        time.sleep(1)

if __name__ == "__main__":
    # Note: Assumes app.py is running on localhost:5000
    run_diagnostics()
