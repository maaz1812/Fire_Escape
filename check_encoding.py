import json
with open('node_red_flow.json', 'r', encoding='cp1252') as f:
    text = f.read()

print("Mangled fire emoji in cp1252 file:", 'ðŸ”¥' in text)
print("Mangled green circle in cp1252 file:", 'ðŸŸ¢' in text)
