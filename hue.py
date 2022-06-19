#!/usr/bin/env python3
import os
import sys
import time
import random
import asyncio

from queue import Queue
from threading import Thread
from paho.mqtt import client as paho_client
from bleak import BleakScanner, BleakClient

MQTT_USER = ""
MQTT_PASS = ""

PHILIPS_POWER_UUID = "932c32bd-0002-47a2-835a-a8d455b859dd"
PHILIPS_LEVEL_UUID = "932c32bd-0003-47a2-835a-a8d455b859dd"

client_id = f'python-bleak-client-{random.randint(0, 100)}'
broker = 'localhost'
port = 1883

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

# 1. Factory reset the bulb
# 2. Pair the bulb from bluetoothctl
# 3. Add device to this list
devices = {
#    0: { 'mac': "FF:FF:FF:FF:FF:FF" },
}

async def check_connected(client):
    try:
        if not client.is_connected:
            print("Not connected, reconnecting")
            await client.connect()
        return True
    except:
        return False

async def hue_write(id, brightness):
    address = devices.get(id)['mac']
    client = devices.get(id)['client']

    if not await check_connected(client):
        return False

    if brightness < 0x10:
        await client.write_gatt_char(PHILIPS_POWER_UUID, int(0).to_bytes(1, 'big'))
        return False
    elif brightness >= 0x10 and brightness <= 0x10 + 50:
        await client.write_gatt_char(PHILIPS_POWER_UUID, int(1).to_bytes(1, 'big'))
    elif brightness >= 0xFE:
        brightness = 0xFE

    await client.write_gatt_char(PHILIPS_LEVEL_UUID, brightness.to_bytes(1, 'big'))
    return False

async def hue_read(id):
    address = devices.get(id)['mac']
    client = devices.get(id)['client']

    if not await check_connected(client):
        return False

    power = int.from_bytes(await client.read_gatt_char(PHILIPS_POWER_UUID), 'big')
    brightness = int.from_bytes(await client.read_gatt_char(PHILIPS_LEVEL_UUID), 'big')
    return [power, brightness]

async def hue_power(id, on):
    address = devices.get(id)['mac']
    client = devices.get(id)['client']

    if not await check_connected(client):
        return False
    
    await client.write_gatt_char(PHILIPS_POWER_UUID,
                                 int(on).to_bytes(1, 'big'))
    return False

sending = False
queued_messages = Queue()
queued_power = Queue()
queued_read = Queue()
        
def on_message(client, userdata, msg):
    global queued_messages
    if msg.topic == '/home/ble/hue/set':
        r = msg.payload.decode()
        queued_messages.put(r)
    if msg.topic == '/home/ble/hue/power':
        r = msg.payload.decode()
        queued_power.put(r)
    if msg.topic == '/home/ble/hue/get':
        r = msg.payload.decode()
        queued_read.put(r)

async def main():
    global queued_messages
    for i, device in devices.items():
        device['client'] = BleakClient(device['mac'], timeout=2.0)
    mqtt_client = connect_mqtt();
    mqtt_client.subscribe([("/home/ble/hue/set", 0),
                           ("/home/ble/hue/power", 0),
                           ("/home/ble/hue/get", 0)])
    mqtt_client.on_message = on_message
    mqtt_client.publish("/startup", 'hue')

    # bluetooth needs to be on
    os.system('bluetoothctl power on')
    while True:
        sys.stdout.flush()
        mqtt_client.loop()

        while not queued_messages.empty():
            r = queued_messages.get()
            args = r.split("\t")
            try:
                await hue_write(int(args[0]), int(args[1]))
            except Exception as e:
                print(f"Hue write errored: {e}")
                queued_messages.put(r)
        while not queued_power.empty():
            r = queued_power.get()
            args = r.split("\t")
            await hue_power(int(args[0]), int(args[1]))
        while not queued_read.empty():
            r = queued_read.get()
            id = int(r)
            reading = await hue_read(id)
            if reading:
                power, brightness = reading
                mqtt_client.publish("/home/ble/hue/values", f"{id}	{power}	{brightness}")

asyncio.run(main())
