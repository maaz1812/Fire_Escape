import json

with open('node_red_flow.json', 'r') as f:
    flow = json.load(f)

# Add group
flow.append({
    'id': 'group_legend',
    'type': 'ui_group',
    'name': 'Dashboard Legend & Guide',
    'tab': 'dashboard_tab',
    'order': 10,
    'width': 12
})

# Add template
legend_html = """
<div style="padding:15px; color:#ddd; font-family:sans-serif; background:#222; border-radius:8px;">
    <h3 style="color:#00acc1; margin-top:0;">How to read this dashboard</h3>
    <ul style="line-height:1.6;">
        <li><b>Rooms on Fire (Donut Chart):</b> Counts any room with a Flame, Temp > 47°C, OR Smoke > 11 PPM.</li>
        <li><b>🔴 Red Rooms (2D Grid):</b> Extreme hazard (Active Flame or Temp > 47°C). Total blockage.</li>
        <li><b>🟠 Orange Rooms (2D Grid):</b> High smoke hazard (> 11 PPM). Victims suffer damage.</li>
        <li><b>🟢 Bright Green Rooms (2D Grid):</b> The active escape route calculated by the algorithm. <i>Note: Green color visually overrides red/orange if the router is forced to send victims through a hazardous room due to blockages elsewhere!</i></li>
        <li><b>🟩 Dark Green Rooms (2D Grid):</b> Safe exits.</li>
        <li><b>⬛ Dark Grey Rooms (2D Grid):</b> Safe, unaffected rooms.</li>
    </ul>
</div>
"""

flow.append({
    'id': 'ui_legend_text',
    'type': 'ui_template',
    'group': 'group_legend',
    'name': 'Legend Template',
    'order': 1,
    'width': 12,
    'height': 8,
    'format': legend_html,
    'x': 400,
    'y': 800,
    'wires': [[]]
})

with open('node_red_flow.json', 'w') as f:
    json.dump(flow, f, indent=4)
