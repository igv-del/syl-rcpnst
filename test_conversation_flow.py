import requests
import time
import random

BASE_URL = "http://localhost:5000/api/chat"

# Scenarios to test randomly
SCENARIOS = [
    {
        "name": "General Info Seeker",
        "inputs": [
            "Hi",
            "What are your hours?",
            "Do you teach math?",
            "Okay thanks"
        ]
    },
    {
        "name": "Tutoring Parent (Direct)",
        "inputs": [
            "Hello",
            "My son is struggling with 4th grade math",
            "What does that cost?",
            "Okay let's book it",
            "Monday at 4pm"
        ]
    },
    {
        "name": "Vague / Unclear Need",
        "inputs": [
            "Hi there",
            "My child needs help but I'm not sure what exactly",
            "It's complicated",
            "Okay sure have them call me at 555-0199"
        ]
    }
]

def run_conversation(scenario):
    print(f"\n--- Testing Scenario: {scenario['name']} ---")
    session_id = None
    
    for user_input in scenario['inputs']:
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
                time.sleep(1) # simulate reading time
            else:
                print(f"Error: {resp.status_code} - {resp.text}")
                break
        except Exception as e:
            print(f"Request failed: {e}")
            break

if __name__ == "__main__":
    # Pick a random scenario or run all? The user said "use random needs", let's run a couple.
    selected_scenario = random.choice(SCENARIOS)
    run_conversation(selected_scenario)
    
    # Also run the Vague one specifically if the random one wasn't it, to test that specific logic path
    if selected_scenario['name'] != "Vague / Unclear Need":
        run_conversation(SCENARIOS[2])
