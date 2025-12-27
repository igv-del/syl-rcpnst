import requests
import time

BASE_URL = "http://localhost:5000/api/chat"

def test_closing():
    print("\n--- Testing Closing Logic ---")
    session_id = None
    
    # 1. Trigger vague need then provide phone
    inputs = [
        "I need help with something complicated",
        "Sure, call me at 555-0199"
    ]
    
    for user_input in inputs:
        print(f"\nUser: {user_input}")
        payload = {"message": user_input}
        if session_id:
            payload["session_id"] = session_id
            
        try:
            resp = requests.post(BASE_URL, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                print(f"Assistant: {data['response']}")
                session_id = data['session_id']
                
                if "Looking forward to serve you" in data['response'] and "[HANGUP]" in data['response']:
                     print("SUCCESS: Correct closing message received.")
            else:
                print(f"Error: {resp.status_code} - {resp.text}")
                break
        except Exception as e:
            print(f"Request failed: {e}")
            break

if __name__ == "__main__":
    test_closing()
