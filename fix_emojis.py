import json

with open('node_red_flow.json', 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    'ðŸŸ¢': '🟢',
    'ðŸ”¥': '🔥',
    'ðŸš¨': '🚨',
    'âœ…': '✅',
    'Â°C': '°C',
    'ðŸŸ£': '🔴',
    'ðŸŸ ': '🟠',
    'ðŸŸ©': '🟩',
    'â¬›': '⬛'
}

for bad, good in replacements.items():
    text = text.replace(bad, good)

with open('node_red_flow.json', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replaced!")
