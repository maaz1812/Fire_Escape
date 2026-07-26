"""
Fire Evacuation Router — Simulation / Injection Tool
=====================================================
Task 4.1: Visual floor plan + manual hazard injection + preset scenario
timelines (Fast Flashover / Slow Smolder), all publishing over MQTT to
the same broker/topics your ESP32 firmware already subscribes to
(proven working in Phase 3).

Run:
    python injector_tool.py

Requires:
    pip install paho-mqtt   (already installed in Phase 3)
"""

import tkinter as tk
from tkinter import ttk
import json
import time
import threading
import paho.mqtt.client as mqtt
import webbrowser

# ------------------------------------------------------------
# Config — matches your ESP32 firmware and floor_graph.json
# ------------------------------------------------------------
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_PREFIX = "fireRouter/honeywell/hazard"
TOPIC_GRAPH_CONFIG = "fireRouter/honeywell/graph/live"

GRAPH_FILE = "floor_graph.json"

# NIST-derived rise rates from Realistic_Fire_Curve_Parameters.md
FAST_FLASHOVER = {
    "temp_rate": 0.070,
    "smoke_rate": 0.027,
    "real_duration": 350,
    "peak_T": 48,
    "peak_ppm": 11,
}
SLOW_SMOLDER = {
    "temp_rate": 0.0015,
    "smoke_rate": 0.0065,
    "real_duration": 1750,
    "peak_T": 25.5,
    "peak_ppm": 12.3,
}
CHEMICAL_SPILL = {
    "temp_rate": 0.0,
    "smoke_rate": 0.05,
    "real_duration": 200,
    "peak_T": 22.0,
    "peak_ppm": 15.0,
}
SMALL_FIRE = {
    "temp_rate": 0.02,
    "smoke_rate": 0.01,
    "real_duration": 400,
    "peak_T": 32.0,
    "peak_ppm": 4.0,
}

DEMO_DURATION = 20  # seconds — how long the demo animation actually takes on screen
BASE_T = 22.0
BASE_PPM = 0.0

# ------------------------------------------------------------
# MQTT setup
# ------------------------------------------------------------
mqtt_client = mqtt.Client()

def mqtt_connect():
    def on_connect(client, userdata, flags, rc):
        client.subscribe("fireRouter/honeywell/path")
    mqtt_client.on_connect = on_connect
    try:
        mqtt_client.connect(BROKER, PORT, 60)
        mqtt_client.loop_start()
        return True
    except Exception as e:
        print(f"MQTT connection failed: {e}")
        return False

def publish_hazard(node_id, T, ppm, flame, occupancy):
    payload = json.dumps({
        "node_id": node_id,
        "T": round(T, 1),
        "ppm": round(ppm, 1),
        "flame": 1 if flame else 0,
        "occupancy": occupancy,
        "timestamp": int(time.time())
    })
    topic = f"{TOPIC_PREFIX}/{node_id}"
    mqtt_client.publish(topic, payload)
    return payload

# ------------------------------------------------------------
# Generate a floor graph on the fly
# ------------------------------------------------------------
def generate_graph(floors, rows, cols, exits=None, furniture=None, occupant_starts=None, base_distance=10):
    if exits is None: exits = ["F1_N1", "F1_N9"]
    if furniture is None: furniture = []
    if occupant_starts is None: occupant_starts = ["F2_N2"]
    
    nodes = []
    node_id_by_pos = {}
    
    # Generate nodes
    for f in range(floors):
        idx = 1
        for r in range(rows):
            for c in range(cols):
                node_id = f"F{f+1}_N{idx}"
                idx += 1
                if node_id in furniture:
                    continue  # Furniture nodes do not exist in the routing graph
                
                node_type = "exit" if node_id in exits else "room"
                nodes.append({"id": node_id, "floor": f+1, "row": r, "col": c, "type": node_type})
                node_id_by_pos[(f, r, c)] = node_id

    edges = []
    # Horizontal edges (within floors)
    for f in range(floors):
        for r in range(rows):
            for c in range(cols):
                u = node_id_by_pos.get((f, r, c))
                if not u: continue
                
                if c < cols - 1:
                    v = node_id_by_pos.get((f, r, c + 1))
                    if v: edges.append({"from": u, "to": v, "base_distance": base_distance})
                if r < rows - 1:
                    v = node_id_by_pos.get((f, r + 1, c))
                    if v: edges.append({"from": u, "to": v, "base_distance": base_distance})

    # Vertical edges (stairwells connecting floors)
    sr = rows // 2
    sc = cols // 2
    for f in range(floors - 1):
        # Normal staircase 1 (center)
        u1 = node_id_by_pos.get((f, sr, sc))
        v1 = node_id_by_pos.get((f + 1, sr, sc))
        if u1 and v1:
            edges.append({"from": u1, "to": v1, "base_distance": base_distance * 1.5, "stair_type": "normal"})
        
        # Normal staircase 2 (center-right)
        if cols > 1:
            u2 = node_id_by_pos.get((f, sr, cols - 1))
            v2 = node_id_by_pos.get((f + 1, sr, cols - 1))
            if u2 and v2:
                edges.append({"from": u2, "to": v2, "base_distance": base_distance * 1.5, "stair_type": "normal"})
        
        # Escape staircase (bottom-left edge)
        u3 = node_id_by_pos.get((f, rows - 1, 0))
        v3 = node_id_by_pos.get((f + 1, rows - 1, 0))
        if u3 and v3:
            edges.append({"from": u3, "to": v3, "base_distance": base_distance * 0.8, "stair_type": "escape"})

    graph = {
        "grid_size": f"{floors}x{rows}x{cols}",
        "max_floors": floors,
        "max_rows": rows,
        "max_cols": cols,
        "total_nodes": len(nodes),
        "exits": exits,
        "occupant_starts": occupant_starts,
        "nodes": nodes,
        "edges": edges,
    }
    return graph


# ------------------------------------------------------------
# Startup dialog
# ------------------------------------------------------------
def prompt_grid_size():
    result = {"floors": 2, "rows": 3, "cols": 3, "confirmed": False}

    dlg = tk.Tk()
    dlg.title("Fire Evacuation Router — Grid Setup")
    dlg.geometry("380x360")

    tk.Label(dlg, text="Setup Building & Obstacles", font=("Segoe UI", 13, "bold")).pack(pady=12)

    frame = tk.Frame(dlg)
    frame.pack(pady=10)

    tk.Label(frame, text="Floors:").grid(row=0, column=0, padx=5, pady=5)
    floors_entry = tk.Entry(frame, width=8)
    floors_entry.insert(0, "2")
    floors_entry.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(frame, text="Rows:").grid(row=1, column=0, padx=5, pady=5)
    rows_entry = tk.Entry(frame, width=8)
    rows_entry.insert(0, "3")
    rows_entry.grid(row=1, column=1, padx=5, pady=5)

    tk.Label(frame, text="Columns:").grid(row=2, column=0, padx=5, pady=5)
    cols_entry = tk.Entry(frame, width=8)
    cols_entry.insert(0, "3")
    cols_entry.grid(row=2, column=1, padx=5, pady=5)

    tk.Label(frame, text="Victims (comma separated):").grid(row=3, column=0, padx=5, pady=5)
    victims_entry = tk.Entry(frame, width=18)
    victims_entry.insert(0, "F3_N1, F3_N9, F1_N5")
    victims_entry.grid(row=3, column=1, padx=5, pady=5)

    tk.Label(frame, text="Exits (comma separated):").grid(row=4, column=0, padx=5, pady=5)
    exits_entry = tk.Entry(frame, width=18)
    exits_entry.insert(0, "F1_N1, F1_N9")
    exits_entry.grid(row=4, column=1, padx=5, pady=5)

    tk.Label(frame, text="Furniture Nodes (obstacles):").grid(row=5, column=0, padx=5, pady=5)
    furn_entry = tk.Entry(frame, width=18)
    furn_entry.insert(0, "F3_N2, F3_N4")
    furn_entry.grid(row=5, column=1, padx=5, pady=5)

    error_label = tk.Label(dlg, text="", fg="red")
    error_label.pack()

    def on_confirm():
        try:
            floors = int(floors_entry.get())
            rows = int(rows_entry.get())
            cols = int(cols_entry.get())
            result["floors"] = floors
            result["rows"] = rows
            result["cols"] = cols
            result["occupant_starts"] = [x.strip() for x in victims_entry.get().split(",") if x.strip()]
            result["exits"] = [x.strip() for x in exits_entry.get().split(",") if x.strip()]
            result["furniture"] = [x.strip() for x in furn_entry.get().split(",") if x.strip()]
            result["confirmed"] = True
            dlg.destroy()
        except ValueError:
            error_label.config(text="Values must be whole numbers.")

    tk.Button(dlg, text="Generate Building", bg="#4CAF50", fg="white",
              font=("Segoe UI", 10, "bold"), command=on_confirm).pack(pady=10)

    dlg.mainloop()
    return result


# ------------------------------------------------------------
# Main App
# ------------------------------------------------------------
class InjectorApp:
    def __init__(self, root, config):
        self.root = root
        self.floors = config["floors"]
        self.rows = config["rows"]
        self.cols = config["cols"]
        self.mqtt_client = mqtt_client
        
        floors = self.floors
        rows = self.rows
        cols = self.cols
        
        self.root.title(f"Fire Evacuation Router — Injection Tool ({floors} Fl, {rows}x{cols})")
        self.root.geometry("1100x800")

        self.graph = generate_graph(
            floors, rows, cols,
            exits=config["exits"],
            furniture=config["furniture"],
            occupant_starts=config["occupant_starts"]
        )
        self.exits = set(self.graph["exits"])
        self.node_buttons = {}
        self.base_btn_texts = {}
        self.log_lines = []
        
        # New Simulation State
        self.active_tool = None
        self.pending_hazards = {}
        self.victim_paths = {}
        self.current_path = [] # Merged path for rendering
        self.node_hazard_state = {n["id"]: {"flame": 0, "T": 22.0, "ppm": 0.0} for n in self.graph["nodes"]}

        # Save the generated graph
        with open(GRAPH_FILE, "w") as f:
            json.dump(self.graph, f, indent=2)

        self.build_ui(floors)
        
        mqtt_client.on_message = self.on_mqtt_message
        mqtt_connect()
        
        self.log(f"Generated {floors} floors of {rows}x{cols} grid (saved to {GRAPH_FILE})")
        self.log("Connected to MQTT broker: " + BROKER)

        # Do NOT publish immediately. We let the user stage first.

    def on_mqtt_message(self, client, userdata, msg):
        if msg.topic == "fireRouter/honeywell/path":
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
                if "victim_paths" in payload:
                    self.victim_paths = payload["victim_paths"]
                    self.current_path = []
                    for p in self.victim_paths.values():
                        self.current_path.extend(p)
                    self.root.after(0, self.redraw_all_nodes)
            except Exception as e:
                pass
                
    def redraw_all_nodes(self):
        for node_id in self.node_buttons:
            state = self.node_hazard_state[node_id]
            self.update_node_color(node_id, state["T"], state["ppm"], state["flame"])

    def publish_graph_config(self):
        payload = json.dumps(self.graph)
        self.mqtt_client.publish(TOPIC_GRAPH_CONFIG, payload, retain=False)
        self.log(f"Published graph config to ESP32 ({self.graph['total_nodes']} nodes, exits: {self.graph['exits']})")

    # ---------------- UI construction ----------------
    def build_ui(self, floors):
        top_frame = tk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

        tk.Label(top_frame, text="Fire Evacuation Router — Simulation Engine",
                 font=("Segoe UI", 16, "bold")).pack()
        
        self.tool_label = tk.Label(top_frame, text="Active Brush: [None] (Click a scenario below, then click rooms)",
                 font=("Segoe UI", 12, "bold"), fg="#ff9800", bg="black")
        self.tool_label.pack(pady=5)

        # --- Floor grid (Scrollable) ---
        wrapper = tk.Frame(self.root)
        wrapper.pack(side=tk.TOP, pady=10, fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(wrapper)
        h_scrollbar = tk.Scrollbar(wrapper, orient="horizontal", command=canvas.xview)
        v_scrollbar = tk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        grid_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        
        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        grid_frame.bind("<Configure>", on_configure)


        for f in range(floors):
            floor_frame = tk.LabelFrame(grid_frame, text=f"Floor {f+1}", font=("Segoe UI", 10, "bold"), padx=10, pady=10)
            floor_frame.grid(row=0, column=f, padx=10)
            
            for node in self.graph["nodes"]:
                if node.get("floor", 1) == f + 1:
                    r, c = node["row"], node["col"]
                    
                    btn_text = node["id"]
                    if node["id"] in self.graph.get("occupant_starts", []):
                        btn_text += "\n(Victims)"
                    
                    is_normal_stair = False
                    is_escape_stair = False
                    for edge in self.graph["edges"]:
                        if edge["from"] == node["id"] or edge["to"] == node["id"]:
                            if edge.get("stair_type") == "normal":
                                is_normal_stair = True
                            elif edge.get("stair_type") == "escape":
                                is_escape_stair = True
                                
                    if is_normal_stair: btn_text += "\n(Stairs)"
                    if is_escape_stair: btn_text += "\n(Escape)"
                    
                    self.base_btn_texts[node["id"]] = btn_text
                    
                    btn = tk.Button(
                        floor_frame, text=btn_text, width=12, height=3,
                        bg="#2E7D32" if node["id"] in self.exits else "#607D8B",
                        fg="white", font=("Segoe UI", 9, "bold"),
                        command=lambda n=node["id"]: self.handle_node_click(n)
                    )
                    btn.grid(row=r, column=c, padx=4, pady=4)
                    self.node_buttons[node["id"]] = btn

        # --- Preset scenario buttons ---
        scenario_frame = tk.Frame(self.root)
        scenario_frame.pack(side=tk.TOP, pady=15)

        tk.Button(scenario_frame, text="Fast Flashover", bg="#e53935", fg="white",
                  width=15, command=lambda: self.set_active_tool("fast")
                  ).grid(row=0, column=0, padx=5)

        tk.Button(scenario_frame, text="Slow Smolder", bg="#fb8c00", fg="white",
                  width=15, command=lambda: self.set_active_tool("slow")
                  ).grid(row=0, column=1, padx=5)
                  
        tk.Button(scenario_frame, text="Chemical Spill", bg="#8e24aa", fg="white",
                  width=15, command=lambda: self.set_active_tool("chem")
                  ).grid(row=0, column=2, padx=5)
                  
        tk.Button(scenario_frame, text="Small Fire", bg="#fdd835", fg="black",
                  width=15, command=lambda: self.set_active_tool("small")
                  ).grid(row=0, column=3, padx=5)

        reset_frame = tk.Frame(self.root)
        reset_frame.pack(side=tk.TOP, pady=5)

        tk.Button(reset_frame, text="Sync Graph to Router", bg="#2196F3", fg="white", font=("Segoe UI", 12, "bold"),
                  width=25, command=self.publish_graph_config
                  ).grid(row=0, column=0, padx=5, pady=10)

        tk.Button(reset_frame, text="Start Simulation", bg="#4CAF50", fg="white", font=("Segoe UI", 12, "bold"),
                  width=25, command=self.start_simulation
                  ).grid(row=0, column=1, padx=5, pady=10)

        links_frame = tk.Frame(self.root)
        links_frame.pack(side=tk.TOP, pady=5)
        
        tk.Button(links_frame, text="🌐 Open Live Dashboard", bg="#FF5722", fg="white", font=("Segoe UI", 10, "bold"),
                  width=25, command=lambda: webbrowser.open("https://team-maaz-alam-maazalam040-bdff-2f3a46a7.flowfuse.cloud/ui")
                  ).grid(row=0, column=0, padx=5)

        tk.Button(links_frame, text="🖥️ Open Wokwi Matrix", bg="#009688", fg="white", font=("Segoe UI", 10, "bold"),
                  width=25, command=lambda: webbrowser.open("https://wokwi.com/projects/470602613253407745")
                  ).grid(row=0, column=1, padx=5)

        # --- Log panel ---
        log_frame = tk.Frame(self.root)
        log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(log_frame, text="Activity Log:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log_box = tk.Text(log_frame, height=12, bg="#1e1e1e", fg="#00ff88", font=("Consolas", 9))
        self.log_box.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_box.see(tk.END)

    # ---------------- Interaction ----------------
    def set_active_tool(self, kind):
        self.active_tool = kind
        self.tool_label.config(text=f"Active Brush: [{kind}]")
        self.log(f"Brush set to: {kind}")

    def handle_node_click(self, node_id):
        if not self.active_tool:
            self.log("Select a brush first!")
            return
        self.pending_hazards[node_id] = self.active_tool
        self.log(f"Staged {self.active_tool} hazard at {node_id}")
        brush_colors = {"fast": "#e53935", "slow": "#fb8c00", "chem": "#8e24aa", "small": "#fdd835"}
        color = brush_colors.get(self.active_tool, "#e53935")
        self.node_buttons[node_id].config(bg=color, fg="white" if self.active_tool != "small" else "black")

        # Immediately send a preview to the ESP32 matrix so it looks awesome during staging
        if self.active_tool == "fast":
            publish_hazard(node_id, 100, 20, 1, 0) # Instant Red Flame
        elif self.active_tool == "chem":
            publish_hazard(node_id, 25, 20, 0, 0) # Instant Orange Smoke
        elif self.active_tool == "slow":
            publish_hazard(node_id, 50, 12, 0, 0) # Instant Orange Heat
        elif self.active_tool == "small":
            publish_hazard(node_id, 80, 10, 1, 0) # Instant Red Flame

    def update_node_color(self, node_id, T, ppm, flame):
        if node_id not in self.node_hazard_state: return
        self.node_hazard_state[node_id] = {"T": T, "ppm": ppm, "flame": flame}
        
        kind = self.pending_hazards.get(node_id)
        brush_colors = {"fast": "#e53935", "slow": "#fb8c00", "chem": "#8e24aa", "small": "#fdd835"}
        brush_color = brush_colors.get(kind, "#e53935") if kind else "#e53935"
        
        # Determine base color based on hazard
        if flame or T > 47 or ppm > 11.5:
            color = brush_color
            fg_color = "white" if kind != "small" else "black"
        elif T > 30 or ppm > 3:
            color = brush_color
            fg_color = "white" if kind != "small" else "black"
        elif T < 20 and ppm == 0:
            color = "#00acc1"  # teal = safe/cold
            fg_color = "white"
        else:
            color = "#2E7D32" if node_id in self.exits else "#607D8B"
            fg_color = "white"
            
        btn_text = self.base_btn_texts[node_id]
            
        # Highlight if it's on the active path
        if node_id in self.current_path:
            color = "#00FF00" # bright green for path
            fg_color = "black"
            btn_text += "\n[ ➔ ]"

        self.node_buttons[node_id].config(bg=color, fg=fg_color, text=btn_text)

    # ---------------- Simulation Runner ----------------
    def start_simulation(self):
        self.publish_graph_config()
        self.log("Simulation starting in 1 second...")
        threading.Thread(target=self.animate_all, daemon=True).start()
        
    def publish_dashboard_grid(self):
        try:
            html = "<div style='display:flex; flex-direction:column; gap:20px; color:white; font-family:sans-serif;'>"
            for f in range(1, self.floors + 1):
                html += f"<div style='border:1px solid #444; padding:15px; background:#1e1e1e; border-radius:8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>"
                html += f"<h3 style='margin-top:0; margin-bottom:10px; color:#00acc1; text-align:center; text-transform:uppercase; letter-spacing:2px;'>Floor {f}</h3>"
                html += f"<table style='margin: 0 auto; border-spacing: 6px; border-collapse: separate;'><tbody>"
                for r in range(1, self.rows + 1):
                    html += "<tr>"
                    for c in range(1, self.cols + 1):
                        node_id = f"F{f}_N{self.cols*(r-1)+c}"
                        bg = "#333"
                        if node_id in self.exits: bg = "#2e7d32" # Dark green exit
                        if node_id in self.node_hazard_state:
                            state = self.node_hazard_state[node_id]
                            if state['flame'] or state['T'] > 47: bg = "#ff1744" # Bright red flame
                            elif state['ppm'] > 11: bg = "#fb8c00" # Orange smoke
                        if node_id in self.current_path: bg = "#00e676" # Bright green path
                        
                        html += f"<td style='width:35px; height:35px; background:{bg}; border-radius:6px; text-align:center; vertical-align:middle; font-size:10px; font-weight:bold; color:rgba(255,255,255,0.4);' title='{node_id}'>{node_id.split('_')[1]}</td>"
                    html += "</tr>"
                html += "</tbody></table></div>"
            html += "</div>"
            
            self.mqtt_client.publish("fireRouter/honeywell/dashboard_grid", html)
        except Exception as e:
            print("Failed to publish dashboard HTML:", e)

    def animate_all(self):
        time.sleep(1)
        steps = 20
        step_delay = DEMO_DURATION / steps

        scenario_params = {
            "fast": FAST_FLASHOVER, "slow": SLOW_SMOLDER,
            "chem": CHEMICAL_SPILL, "small": SMALL_FIRE
        }

        for i in range(steps + 1):
            progress = i / steps
            for node_id, kind in self.pending_hazards.items():
                params = scenario_params.get(kind, FAST_FLASHOVER)
                T = BASE_T + progress * (params["peak_T"] - BASE_T)
                ppm = BASE_PPM + progress * (params["peak_ppm"] - BASE_PPM)
                flame = 0
                if kind == "fast" and progress > 0.85: flame = 1
                if kind == "small" and progress > 0.5: flame = 1
                
                publish_hazard(node_id, T, ppm, flame, occupancy=2)
                self.root.after(0, self.update_node_color, node_id, T, ppm, flame)
            
            new_hazards = {}
            for h_node, kind in list(self.pending_hazards.items()):
                spread_now = False
                if kind == "fast" and i in [6, 12, 18]: spread_now = True
                elif kind == "chem" and i in [8, 16]: spread_now = True
                elif kind == "slow" and i == 15: spread_now = True
                
                if spread_now:
                    # find neighbors
                    for edge in self.graph["edges"]:
                        neighbor = None
                        if edge["from"] == h_node: neighbor = edge["to"]
                        elif edge["to"] == h_node: neighbor = edge["from"]
                        
                        if neighbor and neighbor not in self.pending_hazards and neighbor not in new_hazards:
                            new_hazards[neighbor] = kind
                            break # only spread to 1 adjacent node per tick per fire to not overwhelm
            
            for n_id, k in new_hazards.items():
                self.pending_hazards[n_id] = k
                self.root.after(0, self.log, f"🔥 FIRE SPREAD PREDICTION: {k.upper()} hazard automatically spread to {n_id}!")

            if i % 5 == 0:
                self.root.after(0, self.log, f"Simulation progress: {i}/{steps}...")
            
            # Update the Node-RED Digital Twin Dashboard
            self.publish_dashboard_grid()
                
            time.sleep(step_delay)

        self.root.after(0, self.log, "Simulation Complete! Evaluating final escape routes...")
        self.root.after(1000, self.print_conclusion)

    def print_conclusion(self):
        self.log("Simulation Complete! Evaluating final escape routes...")
        self.log("================= FINAL CONCLUSIONS =================")
        
        tts_speech = ""
        dialog_text = "Simulation Complete! Final Routes:\\n\\n"
        
        victims = self.graph.get("occupant_starts", [])
        
        for victim in victims:
            path = self.victim_paths.get(victim, [])
            clean_victim = victim.replace("F", "Floor ").replace("_N", " Node ")
            if not path or path[-1] not in self.exits:
                self.log(f"Victim at {victim} failed to find a safe route!")
                tts_speech += f"Victim {clean_victim} is trapped! No possible path. "
                dialog_text += f"❌ Victim at {victim} is trapped!\\n\\n"
            else:
                route_str = " ➔ ".join(path)
                self.log(f"Victim at {victim} safely escapes! Route: {route_str}")
                dialog_text += f"✅ Victim at {victim} safely escapes!\\nRoute: {route_str}\\n\\n"
                
                # Speech directions: natural sounding language
                if len(path) > 1:
                    route_speech = []
                    current_floor = path[0].split('_')[0].replace('F', '')
                    for step in path[1:]:
                        f_idx = step.find('F')
                        n_idx = step.find('_N')
                        floor_num = step[f_idx+1:n_idx]
                        node_num = step[n_idx+2:]
                        
                        if current_floor != floor_num:
                            route_speech.append(f"then proceed to Floor {floor_num} Node {node_num}")
                            current_floor = floor_num
                        else:
                            route_speech.append(f"then Node {node_num}")
                            
                    tts_speech += f"Victim at {clean_victim}, proceed to {', '.join(route_speech).replace('then ', '', 1)}. "
                else:
                    tts_speech += f"Victim {clean_victim} has reached safety! "

        self.log("===================================================")
        
        # Publish final speech string to trigger TTS exactly once!
        import json
        payload = json.dumps({"tts": tts_speech, "dialog": dialog_text})
        self.mqtt_client.publish("fireRouter/honeywell/sim_complete", payload)


if __name__ == "__main__":
    config = prompt_grid_size()
    if config.get("confirmed"):
        root = tk.Tk()
        app = InjectorApp(root, config)
        root.mainloop()