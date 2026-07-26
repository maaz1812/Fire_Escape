import json
with open('node_red_flow.json', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'\\u00[a-f0-9]{2}\\u01[a-f0-9]{2}.*', repr(text))
for m in matches:
    print(m[:50])

print("---")
# Also check for \u00e2 (which is start of 3 byte utf-8 like checkmark)
matches2 = re.findall(r'\\u00e2[a-zA-Z0-9\\]*', repr(text))
for m in set(matches2):
    print(m[:50])
