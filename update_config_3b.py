import configparser

config = configparser.ConfigParser()
config.read('config.ini')

if 'local' not in config:
    config['local'] = {}

config['local']['model'] = 'qwen2.5:3b'
config['local']['base_url'] = 'http://localhost:11434/v1'
config['local']['api_key'] = 'lm-studio'

if 'llm' not in config:
    config['llm'] = {}
config['llm']['provider'] = 'local'

with open('config.ini', 'w') as configfile:
    config.write(configfile)

print("Updated config.ini to model=qwen2.5:3b")
