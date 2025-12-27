
import json
import configparser
from app import validate_response
from llm_manager import LLMManager

def load_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

def main():
    config = load_config()
    system_prompt = "You are a helpful assistant for Sylvan Learning."
    llm_manager = LLMManager(config, system_prompt)
    
    test_queries = [
        "Hi",
        "Hello"
    ]
    
    for query in test_queries:
        print(f"\nUser: {query}")
        response = llm_manager.get_local_response(query, [])
        if response != "LOCAL_FAILED":
            print(f"Raw Response: {response}")
            validated = validate_response(query, response)
            print(f"Validated Response: {validated}")
        else:
            print("Local LLM failed.")

if __name__ == "__main__":
    main()
