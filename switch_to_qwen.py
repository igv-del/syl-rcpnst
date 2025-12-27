import configparser
import os

config = configparser.ConfigParser()
config_path = 'config.ini'

if os.path.exists(config_path):
    config.read(config_path)

if 'local' not in config.sections():
    config.add_section('local')

config.set('local', 'model', 'qwen2.5:1.5b')

with open(config_path, 'w') as configfile:
    config.write(configfile)

print("Successfully updated config.ini to use qwen2.5:1.5b")
