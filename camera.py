#!/bin/env python3
import sys
import asyncio
import imageio as iio
from queue import Queue
from datetime import datetime
from paho.mqtt import client as paho_client

MQTT_USER = ""
MQTT_PASS = ""
MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_CLIENTID = f'camera'

CAPTURE_PATH = ''

async def main() -> None:
    take_queue = Queue()
    mqtt_client = paho_client.Client(MQTT_CLIENTID)
    
    def get_image(src):
        camera = iio.get_reader("<video0>")
        screenshot = camera.get_data(0)
        camera.close()
        tstr = datetime.now().strftime("%y%m%d_%H%M%S")
        fname = f"{CAPTURE_PATH}/{tstr}.png"
        iio.imwrite(fname, screenshot)
        mqtt_client.publish('/home/matrix/image', f"{src}	{fname}")
    def mqtt_connect(c, u, f, r):
        print("Connected to MQTT")
    def mqtt_message(c, d, msg):
        if msg.topic == '/home/camera/take':
            src = msg.payload.decode()
            take_queue.put(src)
        
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.on_connect = mqtt_connect
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)

    mqtt_client.subscribe([
        ("/home/camera/take", 0)
    ])
    mqtt_client.on_message = mqtt_message

    while True:
        sys.stdout.flush()
        mqtt_client.loop()
        while not take_queue.empty():
            src = take_queue.get()
            get_image(src)
    
asyncio.run(main())
