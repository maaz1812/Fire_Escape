import paho.mqtt.client as mqtt
import time
import json

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("fireRouter/honeywell/#")

def on_message(client, userdata, msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg.topic}: {msg.payload.decode('utf-8')}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("broker.hivemq.com", 1883, 60)
client.loop_forever()
