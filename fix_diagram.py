import json

with open('diagram.json', 'r') as f:
    diagram = json.load(f)

# Rebuild parts list with two 16x16 matrices
parts = [
    { "type": "wokwi-esp32-devkit-v1", "id": "esp", "top": 0, "left": 0, "attrs": {} },
    { "type": "wokwi-buzzer", "id": "bz1", "top": -60, "left": 60, "attrs": {} },
    # Top Matrix (Rows 0-15)
    { "type": "wokwi-neopixel-matrix", "id": "matrix1", "top": -450, "left": 200, "attrs": { "rows": "16", "cols": "16" } },
    # Bottom Matrix (Rows 16-31)
    { "type": "wokwi-neopixel-matrix", "id": "matrix2", "top": -150, "left": 200, "attrs": { "rows": "16", "cols": "16" } }
]

# Rebuild connections
connections = [
    # Power and Ground for both matrices
    [ "matrix1:VCC", "esp:3V3", "red", [] ],
    [ "matrix1:GND", "esp:GND.1", "black", [] ],
    [ "matrix2:VCC", "esp:3V3", "red", [] ],
    [ "matrix2:GND", "esp:GND.1", "black", [] ],
    # Buzzer
    [ "bz1:1", "esp:D5", "green", [] ],
    [ "bz1:2", "esp:GND.2", "black", [] ],
    # Serial Monitor
    [ "esp:TX0", "$serialMonitor:RX", "", [] ],
    [ "esp:RX0", "$serialMonitor:TX", "", [] ],
    # Data Line Daisy-Chain (ESP -> Matrix 1 -> Matrix 2)
    [ "esp:D4", "matrix1:DIN", "green", [] ],
    [ "matrix1:DOUT", "matrix2:DIN", "green", [] ]
]

diagram['parts'] = parts
diagram['connections'] = connections

with open('diagram.json', 'w') as f:
    json.dump(diagram, f, indent=2)

print("diagram.json updated for daisy-chaining!")
