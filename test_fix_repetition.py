import requests
import time

BASE_URL = "http://localhost:5000/api/chat"

def test_repetition():
    print("\n--- Testing Repetition Fix ---")
    session_id = None
    
    # 1. Trigger an assessment offer
    inputs = [
        "My child struggles with math",
        "Yes, I'd like to book an assessment"  # This should trigger the affirmative logic
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
                
                # Check for double awesome
                if "Awesome. Awesome" in data['response'] or "Awesome. What works better for you—weekdays after school or weekends? Awesome." in data['response']:
                     print("FAILURE: Duplicate 'Awesome' detected.")
                elif "Select a time below" in data['response'] or "Weekdays after school or weekends" in data['response']:
                     print("SUCCESS: Response looks clean.")
            else:
                print(f"Error: {resp.status_code} - {resp.text}")
                break
        except Exception as e:
            print(f"Request failed: {e}")
            break

if __name__ == "__main__":
    test_repetition()
