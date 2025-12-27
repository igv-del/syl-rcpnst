import configparser

config = configparser.ConfigParser()
config.read('config.ini')

if 'llm' not in config:
    config['llm'] = {}

config['llm']['provider'] = 'local'

# Ensure local section exists
if 'local' not in config:
    config['local'] = {}
    config['local']['base_url'] = 'http://localhost:11434/v1'
    config['local']['model'] = 'llama3.2'
    config['local']['api_key'] = 'lm-studio'

with open('config.ini', 'w') as configfile:
    config.write(configfile)

print("Updated config.ini to provider=local")
