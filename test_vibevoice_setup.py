import torch
from transformers import AutoModel, AutoTokenizer
import time

print("Loading VibeVoice-Realtime-0.5B model...")
start_time = time.time()
try:
    # This will download the weights and verify the model loading
    model_path = "microsoft/VibeVoice-Realtime-0.5B"
    # Note: VibeVoice might have a custom loading mechanism in its package
    # but let's try standard transformers first to see if it works or if we need vibevoice specifically
    print(f"Attempting to download/load from {model_path}...")
    # Based on README, they use custom scripts, but let's see if we can import the package
    import vibevoice
    print("VibeVoice package imported successfully.")
except Exception as e:
    print(f"Error: {e}")

print(f"Finished check in {time.time() - start_time:.2f}s")
