import requests
import xml.etree.ElementTree as ET

BASE_URL = "http://localhost:5000"

def test_voice_greeting():
    print("\n--- Testing Voice Greeting (/voice) ---")
    try:
        response = requests.post(f"{BASE_URL}/voice")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Parse TwiML
            root = ET.fromstring(response.text)
            
            # Check for Gather
            gather = root.find('Gather')
            if gather is not None:
                print("SUCCESS: Found <Gather> verb")
                
                # Check for Say inside Gather
                say = gather.find('Say')
                if say is not None:
                    print(f"SUCCESS: Found greeting text: '{say.text}'")
                else:
                    print("FAILURE: No <Say> inside <Gather>")
            else:
                print("FAILURE: No <Gather> verb found")
        else:
            print("FAILURE: Endpoint returned error")
            
    except Exception as e:
        print(f"ERROR: {e}")

def test_voice_input(speech_text):
    print(f"\n--- Testing Voice Input (/voice/handle-input) with '{speech_text}' ---")
    try:
        data = {'SpeechResult': speech_text}
        response = requests.post(f"{BASE_URL}/voice/handle-input", data=data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Parse TwiML
            root = ET.fromstring(response.text)
            
            # Check for Gather (continuation of conversation)
            gather = root.find('Gather')
            if gather is not None:
                say = gather.find('Say')
                if say is not None:
                    print(f"SUCCESS: AI Response: '{say.text}'")
                else:
                    print("FAILURE: No <Say> inside <Gather>")
            else:
                # Might be a direct Say if conversation ended (though app logic uses Gather loop)
                say = root.find('Say')
                if say is not None:
                    print(f"SUCCESS: AI Response (No Gather): '{say.text}'")
                else:
                    print("FAILURE: No <Gather> or <Say> found")
        else:
            print("FAILURE: Endpoint returned error")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_voice_greeting()
    test_voice_input("What are your hours?")
    test_voice_input("Do you offer math tutoring?")
