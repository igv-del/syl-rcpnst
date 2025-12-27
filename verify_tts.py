from tts_manager import TTSManager
import os

def test_tts():
    print("Initializing TTSManager...")
    try:
        tts = TTSManager()
        text = "Hello! This is a test of the human-like VibeVoice receptionist. I hope I sound natural!"
        print(f"Generating audio for: '{text}'")
        filename = tts.generate_audio(text)
        
        if filename and os.path.exists(os.path.join("static", "audio", filename)):
            full_path = os.path.abspath(os.path.join("static", "audio", filename))
            print(f"SUCCESS: Audio generated at {full_path}")
            print(f"File size: {os.path.getsize(full_path)} bytes")
        else:
            print("FAILURE: Audio file not found.")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_tts()
