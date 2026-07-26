#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <vector>
#include <set>
#include <algorithm>

// ============================================================
// Fire Evacuation Router — Full Node Firmware (dynamic grid)
// ============================================================
// Nothing about the floor grid is hardcoded: node count, edges,
// exits, and occupant start node are all received at runtime via
// MQTT from the injector tool (topic: fireRouter/honeywell/graph/config).
// Only physical wiring constants (LED pin/count, buzzer pin) stay
// fixed, since those correspond to actual wires in diagram.json.
// ============================================================

// ---- Hardware wiring constants (tied to diagram.json, not grid size) ----
#define PIXEL_PIN 4
#define BUZZER_PIN 5

Adafruit_NeoPixel strip(1024, PIXEL_PIN, NEO_GRB + NEO_KHZ800);

// ---- MQTT / WiFi ----
WiFiClient espClient;
PubSubClient mqttClient(espClient);
const char* mqtt_server = "broker.hivemq.com";
const char* topic_hazard_sub = "fireRouter/honeywell/hazard/#";
const char* topic_graph_sub  = "fireRouter/honeywell/graph/live";

// ---- Cost formula constants (calibrated from NIST Room Data — these are
// deliberate calibration values, not grid-size hardcoding) ----
const float Tk = 47.0;
const float Pk = 11.5;
const float alpha = 1.0;
const float beta = 1.0;
const float gamma_flame = 20.0;
const float delta = 0.15;

// ---- Dynamic graph structures — sized entirely at runtime ----
struct Edge { int to; float base_distance; };
struct HazardState {
  float T = 22.0;
  float ppm = 0.0;
  bool flame = false;
  int occupancy = 0;
};

std::vector<String> nodeIds;                 // index -> "N7" style id
std::vector<std::vector<Edge>> adjacency;     // adjacency[i] = list of edges from node i
std::vector<HazardState> hazard;              // hazard[i] = current hazard state of node i
std::vector<int> exitIndices;                 // indices of all exit nodes (supports any number of exits)
std::vector<int> nodePixelIndex; // Maps node index -> physical LED pixel index (0-1023)

int graphMaxRows = 3;
int graphMaxCols = 3;
int globalOffsetX = 0;
int globalOffsetY = 0;
bool graphReady = false;
std::vector<int> currentOccupantNodes; // set once graph is loaded

// ---- Pathfinding results ----
std::vector<int> lastPath;
bool currentPathHasHazard = false;

bool hazardChanged = false;

// ---- Non-blocking animation state ----
unsigned long lastAnimStep = 0;
int chaseIndex = 0;
const unsigned long CHASE_INTERVAL = 150;

unsigned long lastPulseToggle = 0;
bool pulseOn = false;
const unsigned long PULSE_INTERVAL = 400;

unsigned long lastBuzzerToggle = 0;
bool buzzerOn = false;
bool buzzerWasHazard = false;
const unsigned long BUZZER_INTERVAL = 300;

// ------------------------------------------------------------
// Cost function — mirrors cost_formula.py exactly
// ------------------------------------------------------------
float calculateCost(float distance, float T, float ppm, bool flame, int occupancy) {
  float temp_factor = 1 + alpha * exp((T - Tk) / 10.0);
  float smoke_factor = 1 + beta * exp((ppm - Pk) / 5.0);
  float flame_factor = 1 + gamma_flame * (flame ? 1 : 0);
  float occupancy_factor = 1 + delta * occupancy;
  return distance * temp_factor * smoke_factor * flame_factor * occupancy_factor;
}

// ------------------------------------------------------------
// Look up a node's index by its string id ("N7") — no assumption
// about naming scheme beyond exact string match against what the
// graph config actually sent.
// ------------------------------------------------------------
int nodeIdToIndex(const String &id) {
  for (size_t i = 0; i < nodeIds.size(); i++) {
    if (nodeIds[i] == id) return (int)i;
  }
  return -1;
}

// ------------------------------------------------------------
// Build the graph from a received JSON document matching the
// floor_graph.json / generate_graph() format:
// { "total_nodes": N, "exits": ["N1","N16"],
//   "nodes": [{"id":"N1", ...}, ...],
//   "edges": [{"from":"N1","to":"N2","base_distance":10}, ...] }
// ------------------------------------------------------------
bool buildGraphFromJson(JsonDocument &doc) {
  JsonArray nodesArr = doc["nodes"];
  JsonArray edgesArr = doc["edges"];
  JsonArray exitsArr = doc["exits"];

  if (nodesArr.isNull() || edgesArr.isNull() || exitsArr.isNull()) {
    Serial.println("Graph config missing required fields, ignoring.");
    return false;
  }
  
  graphMaxRows = doc["max_rows"] | 3;
  graphMaxCols = doc["max_cols"] | 3;

  int n = nodesArr.size();
  nodeIds.clear();
  nodeIds.resize(n);
  adjacency.clear();
  adjacency.resize(n);
  hazard.clear();
  hazard.resize(n);
  exitIndices.clear();
  nodePixelIndex.clear();
  nodePixelIndex.resize(n, -1);

  int idx = 0;
  for (JsonObject node : nodesArr) {
    nodeIds[idx] = node["id"].as<String>();
    
    // Map the 3D floor layout to the 2D Wokwi 20x20 NeoPixel Matrix!
    int floor = node["floor"] | 1;
    int row = node["row"] | 0;
    int col = node["col"] | 0;
    
    // Center the building on a 16x16 / 16x32 matrix
    int totalHeight = (doc["max_floors"] | 1) * (graphMaxRows + 1);
    globalOffsetY = (16 - totalHeight) / 2;
    if (globalOffsetY < 0) globalOffsetY = 0;
    
    globalOffsetX = (16 - graphMaxCols) / 2;
    if (globalOffsetX < 0) globalOffsetX = 0;

    int matrixY = globalOffsetY + (floor - 1) * (graphMaxRows + 1) + row;
    int matrixX = globalOffsetX + col;
    
    // Wokwi 16x16 or 16x32 daisy-chained matrix is wired sequentially (row by row, 16 pixels wide)
    if (matrixY < 32 && matrixX < 16) {
      nodePixelIndex[idx] = (matrixY * 16) + matrixX;
    }
    
    idx++;
  }

  for (JsonObject edge : edgesArr) {
    String fromId = edge["from"].as<String>();
    String toId = edge["to"].as<String>();
    float dist = edge["base_distance"] | 10.0;

    int a = nodeIdToIndex(fromId);
    int b = nodeIdToIndex(toId);
    if (a == -1 || b == -1) continue; // skip malformed edges (fail-safe)

    adjacency[a].push_back({b, dist});
    adjacency[b].push_back({a, dist});
  }

  for (JsonVariant ex : exitsArr) {
    int exIdx = nodeIdToIndex(ex.as<String>());
    if (exIdx != -1) exitIndices.push_back(exIdx);
  }

  if (exitIndices.empty()) {
    Serial.println("Graph config has no valid exits, ignoring.");
    return false;
  }

  // check if occupant starts are provided
  currentOccupantNodes.clear();
  if (doc.containsKey("occupant_starts")) {
    JsonArray startsArr = doc["occupant_starts"];
    for (JsonVariant v : startsArr) {
      int idx = nodeIdToIndex(v.as<String>());
      if (idx != -1) currentOccupantNodes.push_back(idx);
    }
  }
  strip.clear();
  strip.show();

  // pick a sensible default occupant node if not provided or invalid: first non-exit node
  if (currentOccupantNodes.empty()) {
    for (int i = 0; i < n; i++) {
      bool isExit = false;
      for (int e : exitIndices) if (e == i) isExit = true;
      if (!isExit) { currentOccupantNodes.push_back(i); break; }
    }
  }
  if (currentOccupantNodes.empty()) currentOccupantNodes.push_back(0); // fallback

  return true;
}

// ------------------------------------------------------------
// Dijkstra — runs from `start` to whichever exit is cheapest.
// Supports any number of exits (not hardcoded to 2).
// ------------------------------------------------------------
// ------------------------------------------------------------
std::vector<int> computeDijkstraPath(int start, const std::vector<int>& routeCongestion) {
  int n = adjacency.size();
  std::vector<int> path;
  if (n == 0 || start < 0 || start >= n) return path;

  std::vector<float> dist(n, 999999.0);
  std::vector<int> prev(n, -1);
  std::vector<bool> visited(n, false);
  dist[start] = 0;

  for (int count = 0; count < n; count++) {
    int u = -1;
    float best = 999999.0;
    for (int i = 0; i < n; i++) {
      if (!visited[i] && dist[i] < best) { best = dist[i]; u = i; }
    }
    if (u == -1) break;
    visited[u] = true;

    for (auto &e : adjacency[u]) {
      if (visited[e.to]) continue;
      HazardState &h = hazard[e.to];
      float cost = calculateCost(e.base_distance, h.T, h.ppm, h.flame, h.occupancy + routeCongestion[e.to]);
      float newDist = dist[u] + cost;
      if (newDist < dist[e.to]) {
        dist[e.to] = newDist;
        prev[e.to] = u;
      }
    }
  }

  // pick the cheapest reachable exit, among however many exist
  int bestExit = -1;
  float bestCost = 999999.0;
  for (int ex : exitIndices) {
    if (dist[ex] < bestCost) { bestCost = dist[ex]; bestExit = ex; }
  }
  if (bestExit == -1) return path; // no exit reachable

  int node = bestExit;
  while (node != -1) { path.push_back(node); node = prev[node]; }
  std::reverse(path.begin(), path.end());
  return path;
}

void updateRouting() {
  if (currentOccupantNodes.empty()) return;
  currentPathHasHazard = false;
  lastPath.clear(); // Clear previous paths
  
  // Publish individual paths for each victim so UI can log exact routes
  DynamicJsonDocument doc(8192);
  JsonObject victim_paths = doc.createNestedObject("victim_paths");

  unsigned long totalStart = micros();
  std::vector<int> routeCongestion(adjacency.size(), 0);
  
  for (size_t i = 0; i < currentOccupantNodes.size(); i++) {
    unsigned long stepStart = micros();
    std::vector<int> p = computeDijkstraPath(currentOccupantNodes[i], routeCongestion);
    unsigned long stepEnd = micros();
    
    // Increment congestion for all nodes in this victim's path (except their starting node)
    for (size_t j = 1; j < p.size(); j++) {
      routeCongestion[p[j]] += 1; 
    }

    Serial.print("  -> Victim ");
    Serial.print(nodeIds[currentOccupantNodes[i]]);
    Serial.print(" latency: ");
    Serial.print((stepEnd - stepStart) / 1000.0, 3);
    Serial.println(" ms");

    // Add this victim's path to the LED animation array
    lastPath.insert(lastPath.end(), p.begin(), p.end());
    
    JsonArray arr = victim_paths.createNestedArray(nodeIds[currentOccupantNodes[i]]);
    for (int node : p) {
      arr.add(nodeIds[node]);
      if (hazard[node].flame || hazard[node].T > Tk || hazard[node].ppm > Pk) {
        currentPathHasHazard = true;
      }
    }
  }
  unsigned long totalEnd = micros();
  Serial.print("TOTAL Routing Latency: ");
  Serial.print((totalEnd - totalStart) / 1000.0, 3);
  Serial.println(" ms");

  String output;
  serializeJson(doc, output);
  mqttClient.publish("fireRouter/honeywell/path", output.c_str());
}

// ------------------------------------------------------------
void updateHazard(int nodeIndex, float T, float ppm, bool flame, int occupancy) {
  if (nodeIndex < 0 || nodeIndex >= (int)hazard.size()) return;
  hazard[nodeIndex].T = T;
  hazard[nodeIndex].ppm = ppm;
  hazard[nodeIndex].flame = flame;
  hazard[nodeIndex].occupancy = occupancy;
  hazardChanged = true;
}

// ------------------------------------------------------------
void printPath() {
  Serial.print("First victim's path: ");
  for (size_t i = 0; i < lastPath.size(); i++) {
    Serial.print(nodeIds[lastPath[i]]);
    if (i < lastPath.size() - 1) Serial.print(" -> ");
  }
  Serial.println();
  Serial.print("Path hazard status: ");
  Serial.println(currentPathHasHazard ? "HAZARD ON PATH" : "clear");
}

// ------------------------------------------------------------
// Non-blocking LED animation
// ------------------------------------------------------------
void updateLEDs() {
  if (!graphReady) return;
  
  std::set<int> pathNodes;
  for (int n : lastPath) {
    pathNodes.insert(n);
  }

  // 1. Draw Background and Floor Boundaries
  for (int i = 0; i < 512; i++) {
    int y = i / 16;
    int x = i % 16;
    
    // Adjust x and y to logical grid coordinates using the offsets
    int logicalY = y - globalOffsetY;
    int logicalX = x - globalOffsetX;

    // Draw grey boundary rows
    if (logicalY >= 0 && logicalX >= 0 && logicalY % (graphMaxRows + 1) == 0) {
      // Only draw grey if it's within the actual building width (for aesthetics)
      if (logicalX < graphMaxCols && logicalY < (graphMaxRows + 1) * 10) {
        strip.setPixelColor(i, strip.Color(20, 20, 20)); // Dim Grey
      } else {
        strip.setPixelColor(i, strip.Color(0, 0, 0));
      }
    } else {
      strip.setPixelColor(i, strip.Color(0, 0, 0)); // Black
    }
  }

  // 2. Overlay actual nodes based on their physical mappings
  for (int i = 0; i < (int)hazard.size(); i++) {
    int p = nodePixelIndex[i];
    if (p < 0 || p >= 1024) continue;
    
    if (hazard[i].flame) {
      strip.setPixelColor(p, strip.Color(255, 0, 0)); // RED for Fire
    } else if (hazard[i].T > 47.0 || hazard[i].ppm > 11.5) {
      strip.setPixelColor(p, strip.Color(255, 140, 0)); // ORANGE for Danger/Smoke
    } else if (pathNodes.count(i)) {
      strip.setPixelColor(p, strip.Color(0, 255, 0)); // GREEN for Safe Path
    } else {
      // Unaffected node (Dim white/blue to indicate the building layout)
      strip.setPixelColor(p, strip.Color(0, 0, 10)); 
    }
  }
  
  strip.show();
}

// ------------------------------------------------------------
// Non-blocking buzzer — single 500ms beep per hazard detection
// ------------------------------------------------------------
void updateBuzzer() {
  if (!graphReady) return;

  if (currentPathHasHazard && !buzzerWasHazard) {
    tone(BUZZER_PIN, 1000, 500); // Beep exactly once for 500ms, then auto-silence
    buzzerWasHazard = true;
  } else if (!currentPathHasHazard) {
    buzzerWasHazard = false;
  }
}

// ------------------------------------------------------------
// WiFi / MQTT
// ------------------------------------------------------------
void connectWiFi() {
  WiFi.begin("Wokwi-GUEST", "", 6);
  while (WiFi.status() != WL_CONNECTED) {
    delay(100);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr(topic);

  if (topicStr == topic_graph_sub) {
    Serial.println("Received graph configuration.");
    DynamicJsonDocument doc(65536); // Massive 64KB buffer for gigantic 100+ node skyscraper grids
    DeserializationError err = deserializeJson(doc, payload, length);
    if (err) {
      Serial.print("Graph JSON parse failed: ");
      Serial.println(err.c_str());
      return;
    }
    if (buildGraphFromJson(doc)) {
      graphReady = true;
      Serial.print("Graph loaded: ");
      Serial.print(nodeIds.size());
      Serial.println(" nodes.");
      updateRouting();
      Serial.println("Initial path computed.");
      printPath();
    }
    return;
  }

  // otherwise, treat as a hazard update: fireRouter/honeywell/hazard/<node_id>
  Serial.print("MQTT received on ");
  Serial.print(topic);
  Serial.println(" (hazard update)");

  if (!graphReady) {
    Serial.println("Graph not loaded yet, ignoring hazard update.");
    return;
  }

  DynamicJsonDocument doc(512);
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.print("Hazard payload JSON parse failed: ");
    Serial.println(err.c_str());
    return; // fail-safe: ignore corrupted payloads rather than crash
  }
  if (!doc.containsKey("node_id")) {
    Serial.println("Hazard payload missing node_id, ignoring.");
    return;
  }

  String nodeIdStr = doc["node_id"].as<String>();
  int nodeIndex = nodeIdToIndex(nodeIdStr);
  if (nodeIndex == -1) {
    Serial.print("Hazard payload has unrecognized node_id: ");
    Serial.println(nodeIdStr);
    return;
  }

  float T = doc["T"] | 22.0;
  float ppm = doc["ppm"] | 0.0;
  bool flame = (doc["flame"] | 0) == 1;
  int occupancy = doc["occupancy"] | 0;

  updateHazard(nodeIndex, T, ppm, flame, occupancy);
}

void connectMQTT() {
  mqttClient.setServer(mqtt_server, 1883);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(32768); // 32KB buffer fits in uint16_t without overflow!
  while (!mqttClient.connected()) {
    String clientId = "esp32-honeywell-" + String(random(0xffff), HEX);
    if (mqttClient.connect(clientId.c_str())) {
      mqttClient.subscribe(topic_hazard_sub);
      mqttClient.subscribe(topic_graph_sub);
      Serial.println("MQTT connected and subscribed (hazard + graph config topics)");
    } else {
      delay(500);
    }
  }
}

// ------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  connectWiFi();
  connectMQTT();

  strip.begin();
  strip.show();
  pinMode(BUZZER_PIN, OUTPUT);

  Serial.println("Waiting for graph configuration via MQTT (fireRouter/honeywell/graph/live)...");
  // No grid is assumed here — firmware stays idle until the injector
  // tool publishes a graph config, at which point graphReady becomes true.
}

void loop() {
  mqttClient.loop();

  static unsigned long lastHeartbeat = 0;
  if (millis() - lastHeartbeat >= 1000) {
    lastHeartbeat = millis();
    if (mqttClient.connected()) {
      DynamicJsonDocument doc(128);
      doc["status"] = "ONLINE";
      doc["uptime"] = millis();
      String output;
      serializeJson(doc, output);
      mqttClient.publish("fireRouter/honeywell/health", output.c_str());
    }
  }

  // non-blocking serial injection parser (still supported alongside MQTT)
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    if (line.startsWith("N,") && graphReady) {
      int idx1 = line.indexOf(',', 2);
      int idx2 = line.indexOf(',', idx1 + 1);
      int idx3 = line.indexOf(',', idx2 + 1);
      int idx4 = line.indexOf(',', idx3 + 1);

      int nodeIndex = line.substring(2, idx1).toInt();
      float T = line.substring(idx1 + 1, idx2).toFloat();
      float ppm = line.substring(idx2 + 1, idx3).toFloat();
      bool flame = line.substring(idx3 + 1, idx4).toInt() == 1;
      int occupancy = line.substring(idx4 + 1).toInt();

      updateHazard(nodeIndex, T, ppm, flame, occupancy);
    }
  }

  if (hazardChanged && graphReady) {
    updateRouting();
    hazardChanged = false;
    printPath();
  }

  updateLEDs();
  updateBuzzer();
  delay(10); // yield to background RTOS to prevent task watchdog timeouts
}