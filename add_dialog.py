import json

with open('node_red_flow.json', 'r', encoding='utf-8') as f:
    flow = json.load(f)

# Find the mqtt_in_sim_complete node and add extract_dialog to its wires
for n in flow:
    if n.get('id') == 'mqtt_in_sim_complete':
        n['wires'][0].append('extract_dialog')

# Add the extract_dialog function node
flow.append({
    "id": "extract_dialog",
    "type": "function",
    "name": "Extract Dialog Text",
    "func": "let p = msg.payload;\nif (typeof p === 'string' || Buffer.isBuffer(p)) {\n    try { p = JSON.parse(p.toString()); } catch(e) { return null; }\n}\nif (p && p.dialog) {\n    msg.payload = p.dialog.replace(/\\\\n/g, '\\n');\n    return msg;\n}\nreturn null;",
    "outputs": 1,
    "x": 350,
    "y": 280,
    "wires": [
        ["dialog_toast"]
    ]
})

# Add the ui_toast dialog node
flow.append({
    "id": "dialog_toast",
    "type": "ui_toast",
    "position": "dialog",
    "displayTime": "3",
    "highlight": "",
    "sendall": True,
    "outputs": 1,
    "ok": "Dismiss",
    "cancel": "",
    "raw": False,
    "className": "",
    "topic": "Simulation Results",
    "name": "Simulation Dialog Box",
    "x": 550,
    "y": 280,
    "wires": [[]]
})

with open('node_red_flow.json', 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=4)

print("Nodes added successfully!")
