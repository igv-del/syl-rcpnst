import json
import sys

file_path = r'c:\Users\rashm\.gemini\antigravity\scratch\sylvan_receptionist\system_context.json'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    json.loads(content)
    print("SUCCESS: JSON is valid.")
except json.JSONDecodeError as e:
    print(f"FAILED: JSON error at line {e.lineno}, column {e.colno} (char {e.pos}): {e.msg}")
    # Print the context around the error
    lines = content.splitlines()
    start = max(0, e.lineno - 5)
    end = min(len(lines), e.lineno + 5)
    for i in range(start, end):
        marker = ">>> " if i + 1 == e.lineno else "    "
        print(f"{marker}{i+1}: {lines[i]}")
except Exception as e:
    print(f"ERROR: {e}")
