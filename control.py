#!/usr/bin/env python3
from paho.mqtt import client as paho_client

MQTT_USER = ""
MQTT_PASS = ""

broker = 'localhost'
port = 1883
client_id = f'control'

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)
    # Set Connecting Client ID
    client = paho_client.Client(client_id)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

def publish(client, topic, msg):
    result = client.publish(topic, msg)
    status = result[0]
    if status == 0:
        print(f"Send `{msg}` to topic `{topic}`")
    else:
        print(f"Failed to send message to topic {topic}")


mqtt_client = connect_mqtt()

def input_loop():
    while True:
        mqtt_client.loop()
        task = input(">")
        if task == 'inclusion':
            dsk = input("enter full dsk:")
            publish(mqtt_client, '/home/zwave/inclusion', dsk)
        elif task == 'remove failed':
            nid = input("enter node id:")
            publish(mqtt_client, '/home/zwave/removefailed', nid)
        elif task == 'exclusion':
            publish(mqtt_client, '/home/zwave/exclusion', True)
        elif task == 'matrix enable':
            en = input("1 || 0: ")
            publish(mqtt_client, '/home/matrix', en)
        elif task == 'matrix send':
            en = input("=>")
            publish(mqtt_client, '/home/matrix/send', en)
        elif task == 'cam':
            publish(mqtt_client, '/home/camera/take', 'bedroom')
        else:
            break

input_loop()
