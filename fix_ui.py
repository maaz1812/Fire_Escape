import json

with open('node_red_flow.json', 'r', encoding='utf-8') as f:
    flow = json.load(f)

for n in flow:
    # Fix emojis in Set ONLINE
    if n.get('id') == 'health_online':
        n['func'] = 'msg.payload = `<div style="padding:10px; background:#2e7d32; color:white; text-align:center; font-weight:bold; border-radius:5px; font-size:18px;">\u2705 ESP32 Node Network: ONLINE</div>`;\nreturn msg;'

    # Fix emojis in Set OFFLINE
    if n.get('id') == 'health_offline':
        n['func'] = 'msg.payload = `<div style="padding:10px; background:#c62828; color:white; text-align:center; font-weight:bold; border-radius:5px; font-size:18px;">\u26a0\ufe0f ESP32 Node Network: OFFLINE (Signal Lost)</div>`;\nreturn msg;'
        
    # Fix emojis in Extract Analytics
    if n.get('id') == 'calc_analytics':
        func = n['func']
        # Replace the mangled emoji or any flame with the standard unicode escape for flame
        # We'll just hardcode the inner HTML part
        new_func = """let h = msg.payload;
if (typeof h === 'string' || Buffer.isBuffer(h)) { try { h = JSON.parse(h.toString()); } catch(e) { return null; } }
if (!h || !h.node_id) return null;

let nodes = context.get('nodes') || {};
nodes[h.node_id] = h;
context.set('nodes', nodes);

let maxTemp = 0;
let maxSmoke = 0;
let hazardCount = 0;
let fireZones = [];

for (let id in nodes) {
    if (nodes[id].T > maxTemp) maxTemp = nodes[id].T;
    if (nodes[id].ppm > maxSmoke) maxSmoke = nodes[id].ppm;
    if (nodes[id].T > 47 || nodes[id].ppm > 11 || nodes[id].flame) {
        hazardCount++;
        fireZones.push(id);
    }
}

let fireHtml = "";
if (fireZones.length > 0) {
    fireHtml = "<div style='display:flex; flex-wrap:wrap; gap:10px;'>";
    for(let i=0; i<fireZones.length; i++){
        fireHtml += `<div style='background:#e53935; color:white; padding:8px 15px; border-radius:5px; font-weight:bold; box-shadow: 0 0 10px #e53935;'>\\uD83D\\uDD25 ${fireZones[i]}</div>`;
    }
    fireHtml += "</div>";
} else {
    fireHtml = "<div style='color:#4CAF50; font-weight:bold; font-size:18px;'>\\u2705 All zones clear</div>";
}

return [{payload: maxTemp}, {payload: maxSmoke}, {payload: hazardCount}, {payload: hazardCount}, {payload: fireHtml}];"""
        n['func'] = new_func

    # Fix emojis in HVAC Auto-Shutoff
    if n.get('id') == 'hvac_logic':
        func = n['func']
        new_func = """let maxSmoke = msg.payload;
let wasHvacEngaged = context.get("hvacEngaged") || false;
let isHvacEngaged = (maxSmoke > 10);
let html = "";
let speech = null;

if (isHvacEngaged) {
    html = `<div style="padding:15px; background:#c62828; color:white; text-align:center; font-weight:bold; border-radius:5px; font-size:18px;">\\uD83D\\uDEA8 HVAC: EMERGENCY O2 STARVATION MODE ENGAGED</div>`;
    if (!wasHvacEngaged) {
        speech = "Critical smoke levels detected. HVAC oxygen starvation protocol engaged. Air flow restricted.";
    }
} else {
    html = `<div style="padding:15px; background:#2e7d32; color:white; text-align:center; font-weight:bold; border-radius:5px; font-size:18px;">\\u2705 HVAC: NORMAL VENTILATION</div>`;
    if (wasHvacEngaged) {
        speech = "Smoke cleared. HVAC returning to normal ventilation.";
    }
}

context.set("hvacEngaged", isHvacEngaged);
return [{payload: html}, speech ? {payload: speech} : null];"""
        n['func'] = new_func

    # Fix ui_health template to bypass sanitization
    if n.get('id') == 'ui_health':
        n['format'] = """<div id="health-container"></div>
<script>
(function(scope) {
    scope.$watch('msg', function(msg) {
        if (msg && msg.payload) {
            var c = document.getElementById('health-container');
            if (c) c.innerHTML = msg.payload;
        }
    });
})(scope);
</script>"""

    # Fix ui_hvac_status template to bypass sanitization
    if n.get('id') == 'ui_hvac_status':
        n['format'] = """<div id="hvac-container"></div>
<script>
(function(scope) {
    scope.$watch('msg', function(msg) {
        if (msg && msg.payload) {
            var c = document.getElementById('hvac-container');
            if (c) c.innerHTML = msg.payload;
        }
    });
})(scope);
</script>"""

    # Fix ui_fire_map template to bypass sanitization
    if n.get('id') == 'ui_fire_map':
        n['format'] = """<h2>Active Fire Zones</h2>
<div style="padding:15px; background:#222; border-radius:8px; border-left: 5px solid #e53935; min-height:50px;">
    <div id="fire-map-container"></div>
</div>
<script>
(function(scope) {
    scope.$watch('msg', function(msg) {
        if (msg && msg.payload) {
            var c = document.getElementById('fire-map-container');
            if (c) c.innerHTML = msg.payload;
        }
    });
})(scope);
</script>"""

with open('node_red_flow.json', 'w', encoding='utf-8') as f:
    json.dump(flow, f, indent=4)

print("Flow completely updated and sanitized!")
