# Fire Commander — Engineering Flowcharts

These 6 flowcharts cover the entire logic of the Fire Commander system. You can copy the code blocks below and paste them into [mermaid.live](https://mermaid.live/) to generate high-quality images for your PPT and report.

---

## 1. Complete System Architecture

```mermaid
flowchart TB
    subgraph SIMULATION["Simulation Layer - Python"]
        A["Grid Setup Dialog\nFloors x Rows x Cols"] --> B["Graph Generator\nNodes + Edges + Stairs"]
        B --> C["floor_graph.json"]
        C --> D["Injector Tool GUI\nTkinter"]
        D --> E{"User Selects\nHazard Brush"}
        E -->|Fast Flashover| F["NIST Curve: 0.070 C/step"]
        E -->|Slow Smolder| G["NIST Curve: 0.0015 C/step"]
        E -->|Chemical Spill| H["NIST Curve: 0 temp, 0.05 PPM/step"]
        E -->|Small Fire| I["NIST Curve: 0.01 C/step"]
        F & G & H & I --> J["20-Step Fire Simulation\n+ Auto Fire Spread"]
    end

    subgraph MQTT_CLOUD["MQTT Cloud Broker - HiveMQ"]
        T1[/"graph/config"/]
        T2[/"hazard/node_id"/]
        T3[/"path"/]
        T4[/"health"/]
        T5[/"dashboard_grid"/]
    end

    subgraph ESP32["ESP32 Edge Processor - Wokwi"]
        K["Receive Graph Config\nbuildGraphFromJson"] --> L["Build Adjacency List\n+ Map Nodes to LEDs"]
        L --> M["Receive Hazard Update\nupdateHazard"]
        M --> N["Sensor Fusion\nCost Formula"]
        N --> O["Dijkstra Algorithm\ncomputeDijkstraPath"]
        O --> P["Multi-Victim\nCongestion Routing"]
        P --> Q["Publish Paths\nvia MQTT"]
        P --> R["Update LED Matrix\nupdateLEDs"]
        P --> S["Trigger Buzzer\nupdateBuzzer"]
    end

    subgraph DASHBOARD["Node-RED Dashboard"]
        U["System Health Monitor"]
        V["2D Digital Twin Grid"]
        W["Live Escape Routes"]
        X["Hazard Analytics\nCharts + Gauges"]
        Y["HVAC O2 Starvation Mode"]
        Z["TTS Voice Alerts"]
    end

    C -->|Publish| T1
    J -->|Publish Hazard| T2
    T1 -->|Subscribe| K
    T2 -->|Subscribe| M
    Q -->|Publish| T3
    ESP32 -->|Heartbeat 1s| T4

    T3 -->|Subscribe| W
    T4 -->|Subscribe| U
    T2 -->|Subscribe| X
    D -->|Publish HTML| T5
    T5 -->|Subscribe| V

    style SIMULATION fill:#1a237e,color:#fff,stroke:#5c6bc0
    style MQTT_CLOUD fill:#4a148c,color:#fff,stroke:#ce93d8
    style ESP32 fill:#b71c1c,color:#fff,stroke:#ef9a9a
    style DASHBOARD fill:#1b5e20,color:#fff,stroke:#a5d6a7
```

---

## 2. Sensor Fusion Cost Formula (⭐ KEY ENGINEERING DIAGRAM)

```mermaid
flowchart TD
    START(["Hazard Update Received\nfor Node N"]) --> INPUT

    subgraph INPUT["Raw Sensor Inputs"]
        I1["Temperature T in C"]
        I2["Smoke Density PPM"]
        I3["Flame Detected 0 or 1"]
        I4["Occupancy Count"]
        I5["Base Distance d meters"]
    end

    I1 --> TF
    I2 --> SF
    I3 --> FF
    I4 --> OF
    I5 --> FINAL

    subgraph FACTORS["Exponential Weight Factors"]
        TF["Temp Factor\n1 + alpha x e to the power of T minus 47 over 10\n22C = 1.08 safe\n40C = 1.49 warm\n47C = 2.00 DANGER\n55C = 3.23 LETHAL"]
        SF["Smoke Factor\n1 + beta x e to the power of PPM minus 11.5 over 5\n0 PPM = 1.10 clear\n6 PPM = 1.33 hazy\n11.5 PPM = 2.00 DANGER\n15 PPM = 3.01 BLIND"]
        FF["Flame Factor\n1 + gamma x flame\nNo Flame = 1.0x\nFlame = 21.0x"]
        OF["Occupancy Factor\n1 + delta x occupancy\n0 people = 1.0x\n5 people = 1.75x"]
    end

    TF & SF & FF & OF --> FINAL

    FINAL["FINAL EDGE COST\nC = d x TempFactor x SmokeFactor\nx FlameFactor x OccupancyFactor"]

    FINAL --> COMPARE{{"Cost Comparison"}}

    COMPARE -->|"Safe: ~12.6"| SAFE["Green LED\nInclude in path"]
    COMPARE -->|"Moderate: ~16"| WARN["Yellow\nPassable but penalized"]
    COMPARE -->|"Danger: ~3460+"| BLOCK["Red LED\nDijkstra avoids"]

    SAFE --> DIJKSTRA["Dijkstra selects\nLOWEST total cost path"]
    WARN --> DIJKSTRA
    BLOCK --> DIJKSTRA

    DIJKSTRA --> ROUTE(["Safest Escape Route\nPublished to MQTT"])

    style INPUT fill:#0d47a1,color:#fff,stroke:#42a5f5
    style FACTORS fill:#e65100,color:#fff,stroke:#ffb74d
    style FINAL fill:#880e4f,color:#fff,stroke:#f48fb1
    style SAFE fill:#2e7d32,color:#fff
    style WARN fill:#f9a825,color:#000
    style BLOCK fill:#c62828,color:#fff
```

---

## 3. ESP32 Main Loop

```mermaid
flowchart TD
    BOOT["ESP32 Boot"] --> WIFI["Connect WiFi\nWokwi-GUEST"]
    WIFI --> MQTT_CONN["Connect MQTT\nbroker.hivemq.com"]
    MQTT_CONN --> SUB["Subscribe to\nhazard/# + graph/config"]
    SUB --> WAIT["Wait for Graph Config\ngraphReady = false"]

    WAIT -->|"Graph JSON received"| BUILD["buildGraphFromJson\nParse nodes, edges, exits"]
    BUILD --> INIT_PATH["Initial Dijkstra\ncomputeDijkstraPath"]
    INIT_PATH --> LOOP

    LOOP["loop start"] --> MQTT_LOOP["mqttClient.loop\nProcess incoming messages"]
    MQTT_LOOP --> HEARTBEAT{"1 second\nelapsed?"}
    HEARTBEAT -->|Yes| PUB_HEALTH["Publish health heartbeat\nstatus ONLINE uptime"]
    HEARTBEAT -->|No| SERIAL_CHECK
    PUB_HEALTH --> SERIAL_CHECK

    SERIAL_CHECK{"Serial data\navailable?"}
    SERIAL_CHECK -->|"Yes: N,idx,T,ppm,F,O"| SERIAL_PARSE["Parse serial injection\nupdateHazard"]
    SERIAL_CHECK -->|No| HAZARD_CHECK
    SERIAL_PARSE --> HAZARD_CHECK

    HAZARD_CHECK{"hazardChanged\n== true?"}
    HAZARD_CHECK -->|Yes| REROUTE["updateRouting\nRe-run Dijkstra for ALL victims\nPublish new paths via MQTT"]
    HAZARD_CHECK -->|No| LED
    REROUTE --> LED

    LED["updateLEDs\nDraw floor boundaries\nColor nodes by hazard state\nOverlay green path"]
    LED --> BUZZER["updateBuzzer\nSingle beep if hazard on path"]
    BUZZER --> DELAY["delay 10ms\nYield to RTOS"]
    DELAY --> LOOP

    style BOOT fill:#1565c0,color:#fff
    style LOOP fill:#6a1b9a,color:#fff
    style REROUTE fill:#c62828,color:#fff
    style LED fill:#2e7d32,color:#fff
    style BUZZER fill:#e65100,color:#fff
```

---

## 4. Fire Spread Prediction

```mermaid
flowchart TD
    START["Simulation Begins\n20 Steps x 1 second each"] --> STEP["Step i = 0"]

    STEP --> ESCALATE["Escalate ALL active hazards\nT += progress x peak_T minus 22\nPPM += progress x peak_PPM"]

    ESCALATE --> PUBLISH["Publish hazard update\nto MQTT for each node"]

    PUBLISH --> SPREAD_CHECK{"Should fire\nspread at\nthis step?"}

    SPREAD_CHECK -->|"Fast Fire: step 6, 12, 18"| FIND_NEIGHBOR
    SPREAD_CHECK -->|"Chem Spill: step 8, 16"| FIND_NEIGHBOR
    SPREAD_CHECK -->|"Slow Smolder: step 15"| FIND_NEIGHBOR
    SPREAD_CHECK -->|"No spread this step"| DASHBOARD_UPDATE

    FIND_NEIGHBOR["Walk graph edges\nFind 1 adjacent room\nNOT already on fire"] --> NEW_FIRE["Stage new hazard\non neighbor node"]
    NEW_FIRE --> LOG["Log: FIRE SPREAD\nto new room"]
    LOG --> DASHBOARD_UPDATE

    DASHBOARD_UPDATE["Publish HTML Digital Twin\nto Node-RED Dashboard"]

    DASHBOARD_UPDATE --> NEXT{"i less than 20?"}
    NEXT -->|Yes| INCREMENT["i++"] --> STEP
    NEXT -->|No| CONCLUDE["Simulation Complete\nEvaluate final escape routes"]

    CONCLUDE --> VICTIMS["For each victim"]
    VICTIMS --> CHECK_PATH{"Path reaches\nan exit?"}
    CHECK_PATH -->|Yes| SAFE["Victim safely escapes\nAnnounce route via TTS"]
    CHECK_PATH -->|No| TRAPPED["Victim is TRAPPED\nNo possible escape path"]

    style START fill:#1565c0,color:#fff
    style FIND_NEIGHBOR fill:#e65100,color:#fff
    style NEW_FIRE fill:#c62828,color:#fff
    style SAFE fill:#2e7d32,color:#fff
    style TRAPPED fill:#b71c1c,color:#fff
```

---

## 5. Fail-Safe Mechanisms

```mermaid
flowchart TD
    subgraph HEARTBEAT["Heartbeat Monitor"]
        H1["ESP32 publishes\nstatus ONLINE\nevery 1 second"] --> H2{"Node-RED:\nHeartbeat received\nwithin 5 seconds?"}
        H2 -->|Yes| H3["Status: ONLINE\nGreen indicator"]
        H2 -->|No| H4["Status: OFFLINE\nSignal Lost warning"]
    end

    subgraph CORRUPT["Corrupted Payload Handling"]
        C1["MQTT message\narrives on ESP32"] --> C2{"JSON parse\nsuccessful?"}
        C2 -->|No| C3["Log warning\nSilently reject\nSystem continues"]
        C2 -->|Yes| C4{"Contains\nnode_id field?"}
        C4 -->|No| C5["Log: missing node_id\nSilently reject"]
        C4 -->|Yes| C6{"node_id exists\nin graph?"}
        C6 -->|No| C7["Log: unrecognized\nnode_id - reject"]
        C6 -->|Yes| C8["Process\nhazard update"]
    end

    subgraph TRAPPED_DETECT["Trapped Victim Detection"]
        T1["Dijkstra runs\nfor victim node"] --> T2{"Any exit\nreachable?"}
        T2 -->|Yes| T3["Return path\nUpdate LEDs green"]
        T2 -->|No| T4["Return empty path\nVictim declared TRAPPED"]
    end

    subgraph BUZZER_SAFE["Non-Blocking Buzzer"]
        B1{"Hazard detected\non path?"}
        B1 -->|"Yes first time"| B2["Single 500ms beep\ntone 1000Hz 500ms"]
        B1 -->|"Yes already beeped"| B3["Silent - no repeat"]
        B1 -->|"No path clear"| B4["Reset buzzer state"]
    end

    style HEARTBEAT fill:#1b5e20,color:#fff,stroke:#a5d6a7
    style CORRUPT fill:#0d47a1,color:#fff,stroke:#42a5f5
    style TRAPPED_DETECT fill:#b71c1c,color:#fff,stroke:#ef9a9a
    style BUZZER_SAFE fill:#e65100,color:#fff,stroke:#ffb74d
```

---

## 6. Multi-Victim Congestion Routing

```mermaid
flowchart TD
    START["updateRouting called"] --> INIT["Initialize congestion vector\nrouteCongestion all nodes = 0"]

    INIT --> V1["Victim 1\nRun Dijkstra with\ncurrent congestion weights"]
    V1 --> P1["Path 1 found\ne.g. F2_N2 to F1_N2 to F1_N1"]
    P1 --> C1["Increment congestion\nfor all nodes in Path 1"]

    C1 --> V2["Victim 2\nRun Dijkstra with\nUPDATED congestion weights"]
    V2 --> P2["Path 2 found\nAvoids crowded nodes from Path 1\ne.g. F2_N8 to F2_N9 to F1_N9"]
    P2 --> C2["Increment congestion\nfor all nodes in Path 2"]

    C2 --> VN["Victim N...\nEach successive victim sees\naccumulated congestion"]

    VN --> PUBLISH["Publish ALL victim paths\nas JSON to MQTT"]
    PUBLISH --> LED["First victim path\ndisplayed on LED matrix"]

    style START fill:#6a1b9a,color:#fff
    style V1 fill:#1565c0,color:#fff
    style V2 fill:#00838f,color:#fff
    style VN fill:#2e7d32,color:#fff
    style PUBLISH fill:#c62828,color:#fff
```
