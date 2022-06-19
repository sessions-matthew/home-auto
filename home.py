#!/usr/bin/env python3
import sys
from requests import get
from paho.mqtt import client as paho_client

MQTT_USER = ""
MQTT_PASS = ""

broker = 'localhost'
port = 1883
client_id = f'home'

matrix_enabled = {}

blights = {
    0: {
        'location': 'kitchen',
        'brightness': 0
    },
    1: {
        'location': 'livingroom',
        'brightness': 0
    },
    2: {
        'location': 'downstairs',
        'brightness': 0
    },
    3: {
        'location': 'bedroom',
        'brightness': 0
    }
}

zmotion = {
    3: {
        'location': 'kitchen'
    },
    4: {
        'location': 'bedroom'
    },
    7: {
        'location': 'frontdoor'
    },
    16: {
        'location': 'downstairs'
    },
    17: {
        'location': 'backdoor'
    },
    18: {
        'location': 'master'
    }
}

zswitches = {
    'master': {
        
    }
}

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

def light_nodes_by_location(location):
    nodes = []
    if location == 'kitchen':
        nodes = [1,2]
    elif location == 'bedroom':
        nodes = [0]
    elif location == 'frontdoor':
        nodes = [3]
    elif location == 'downstairs':
        nodes = [3]
    elif location == 'backdoor':
        nodes = [1,2]
    elif location == 'master':
        nodes = [0]
    return nodes

def lights_change(id, up):
    global blights
    blights[id]['brightness'] += 50 if up else -50
    brightness = blights[id]['brightness']
    mqtt_client.publish("/home/ble/hue/set", f"{id}	{brightness}")

    if brightness < -100:
        blights[id]['brightness'] = -100
    if brightness > 300:
        blights[id]['brightness'] = 300

def motion_to_light(mnode, value):
    global blights
    global zmotion
    location = zmotion[mnode]['location']
    increase = bool(value)
    nodes = light_nodes_by_location(location)
    for node in nodes:
        lights_change(node, increase)

def motion_to_matrix(node, value):
    global matrix_enabled
    location = zmotion[node]['location']
    if 'all' in matrix_enabled and matrix_enabled['all'] and value:
        mqtt_client.publish("/home/matrix/send/area", f"all	Motion detected in {location}")
    if 'bedroom' in matrix_enabled and matrix_enabled['bedroom'] and value and location == 'bedroom' :
        mqtt_client.publish("/home/matrix/send/area", f"bedroom	Motion detected in bedroom")
        mqtt_client.publish("/home/camera/take", 'bedroom')

ip = get('https://api.ipify.org').text
    
def on_message(client, userdata, msg):
    global matrix_enabled
    r = msg.payload.decode()
    args = r.split("\t")
    if(msg.topic == '/home/zwave/switch/values'):
        nodes = [0,1,2,3]
        for node in nodes:
            lights_change(id = node,
                          up = bool(int(args[2])))
    elif(msg.topic == '/home/zwave/motion/values'):
        motion_to_light(mnode = int(args[0]),
                        value = int(args[2]))
        motion_to_matrix(node = int(args[0]),
                         value = int(args[2]))
    elif(msg.topic == '/home/ble/hue/values'):
        node = int(args[0])
        power = int(args[1])
        brightness = int(args[2])
        blights[node]['power'] = power
        blights[node]['brightness'] = brightness
    elif(msg.topic == '/home/matrix/notifications'):
        area = args[0]
        enabled = bool(int(args[1]))
        matrix_enabled[area] = enabled
        nstat = 'enabled' if enabled else 'disabled'
        mqtt_client.publish("/home/matrix/send/area", f"{area}	Notifications {nstat}")
    elif(msg.topic == '/startup'):
        sname = r
        mqtt_client.publish('/home/matrix/send/event', f"Process {sname} started.")
        if sname == 'hue':
            for node in [0,1,2,3]:
                mqtt_client.publish('/home/ble/hue/get', f"{node}")
    else:
        print(r)
    sys.stdout.flush()

mqtt_client = connect_mqtt()
mqtt_client.subscribe([
    ("/startup", 0),
    ("/home/matrix/notifications", 0),
    ("/home/ble/hue/values", 0),
    ("/home/zwave/motion/values", 0),
    ("/home/zwave/switch/values", 0),
    ("/home/zwave/node/battery", 0)
])

mqtt_client.publish('/home/matrix/send/event', f"Starting on {ip}")
mqtt_client.on_message = on_message
mqtt_client.loop_forever()
