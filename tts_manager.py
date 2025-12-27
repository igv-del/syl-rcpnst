import os
import torch
import time
import copy
import hashlib
from typing import Optional
from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference
from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor

class TTSManager:
    def __init__(self, model_path: str = "microsoft/VibeVoice-Realtime-0.5B", 
                 voice_name: str = "Emma",
                 device: Optional[str] = None):
        self.model_path = model_path
        self.voice_name = voice_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.output_dir = os.path.join("static", "audio")
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"[TTS] Initializing VibeVoice on {self.device}...")
        self.processor = VibeVoiceStreamingProcessor.from_pretrained(model_path)
        
        # Decide dtype & attention implementation
        if self.device == "cuda":
            self.load_dtype = torch.bfloat16
            self.attn_impl = "flash_attention_2"
        else:
            self.load_dtype = torch.float32
            self.attn_impl = "sdpa"
            
        try:
            self.model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                model_path,
                torch_dtype=self.load_dtype,
                device_map=self.device,
                attn_implementation=self.attn_impl,
            )
        except Exception as e:
            print(f"[TTS] Warning: Failed to load {self.attn_impl}. Falling back to sdpa. Error: {e}")
            self.model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                model_path,
                torch_dtype=self.load_dtype,
                device_map=self.device,
                attn_implementation="sdpa",
            )
            
        self.model.eval()
        self.model.set_ddpm_inference_steps(num_steps=5)
        
        # Load voice preset
        self.voice_preset_path = self._find_voice_preset(voice_name)
        if self.voice_preset_path:
            self.cached_voice = torch.load(self.voice_preset_path, map_location=self.device, weights_only=False)
            print(f"[TTS] Loaded voice preset: {voice_name}")
        else:
            self.cached_voice = None
            print(f"[TTS] Warning: Voice preset '{voice_name}' not found.")

    def _find_voice_preset(self, name: str) -> Optional[str]:
        preset_dir = os.path.join("VibeVoice", "demo", "voices", "streaming_model")
        for f in os.listdir(preset_dir):
            if name.lower() in f.lower() and f.endswith(".pt"):
                return os.path.join(preset_dir, f)
        return None

    def generate_audio(self, text: str) -> str:
        """
        Generates audio for the given text and returns the filename.
        Uses md5 hash of text for caching.
        """
        if not text:
            return ""
            
        # Clean text
        text = text.replace("’", "'").replace('“', '"').replace('”', '"').strip()
        
        # Check cache
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        filename = f"{text_hash}.wav"
        filepath = os.path.join(self.output_dir, filename)
        
        if os.path.exists(filepath):
            # print(f"[TTS] Using cached audio for: {text[:30]}...")
            return filename

        print(f"[TTS] Generating audio for: {text[:50]}...")
        start_time = time.time()
        
        try:
            inputs = self.processor.process_input_with_cached_prompt(
                text=text,
                cached_prompt=self.cached_voice,
                padding=True,
                return_tensors="pt",
                return_attention_mask=True,
            )
            
            for k, v in inputs.items():
                if torch.is_tensor(v):
                    inputs[k] = v.to(self.device)
                    
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=None,
                cfg_scale=1.5,
                tokenizer=self.processor.tokenizer,
                generation_config={'do_sample': False},
                all_prefilled_outputs=copy.deepcopy(self.cached_voice) if self.cached_voice is not None else None,
            )
            
            self.processor.save_audio(
                outputs.speech_outputs[0],
                output_path=filepath,
            )
            
            gen_time = time.time() - start_time
            print(f"[TTS] Generated in {gen_time:.2f}s")
            return filename
            
        except Exception as e:
            print(f"[TTS] Error generating audio: {e}")
            return ""

if __name__ == "__main__":
    # Test
    tts = TTSManager()
    tts.generate_audio("Hello, I am your Sylvan AI receptionist. How can I help you today?")
