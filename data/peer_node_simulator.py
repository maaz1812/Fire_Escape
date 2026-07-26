"""
Peer Node Simulator — simulates 2 additional mesh nodes (besides the Wokwi ESP32)
publishing hazard state over MQTT, so the multi-node communication logic can be
demonstrated without running multiple full hardware simulations.

Install first:
    pip install paho-mqtt

Run:
    python peer_node_simulator.py
"""

import paho.mqtt.client as mqtt
import json
import time
import random

BROKER = "broker.hivemq.com"  # free public test broker
PORT = 1883
TOPIC_PREFIX = "fireRouter/honeywell/hazard"  # matches ESP32 firmware topic

PEER_NODES = ["N10", "N14"]  # simulated peer nodes (pick any 2 not used by your main test)


def make_payload(node_id, T, ppm, flame, occupancy):
    return json.dumps({
        "node_id": node_id,
        "T": T,
        "ppm": ppm,
        "flame": flame,
        "occupancy": occupancy,
        "timestamp": int(time.time())
    })


def on_connect(client, userdata, flags, rc):
    print(f"Connected to broker with result code {rc}")


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    print("Publishing simulated peer node hazard data every 3 seconds. Ctrl+C to stop.")
    try:
        while True:
            for node in PEER_NODES:
                # random mild fluctuation for realism, occasionally spikes
                T = round(random.uniform(20, 26), 1)
                ppm = round(random.uniform(0, 3), 1)
                flame = 0
                occupancy = random.randint(0, 3)

                payload = make_payload(node, T, ppm, flame, occupancy)
                topic = f"{TOPIC_PREFIX}/{node}"
                client.publish(topic, payload)
                print(f"Published to {topic}: {payload}")

            time.sleep(3)
    except KeyboardInterrupt:
        print("Stopping peer node simulator.")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()