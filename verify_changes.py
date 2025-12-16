
import requests
import json
import time

URL = "http://127.0.0.1:5000/api/chat"
SESSION_ID = "test_sched_v1"

def send_msg(msg, session_id=SESSION_ID):
    print(f"\nUser: {msg}")
    try:
        resp = requests.post(URL, json={"message": msg, "session_id": session_id})
        data = resp.json()
        print(f"Bot: {data['response']}")
        return data['response']
    except Exception as e:
        print(f"Error: {e}")
        return ""

print("--- Test 4: Time Preference Handling ---")
send_msg("Is that $49 checkup available?")
send_msg("Weekdays are fine")
