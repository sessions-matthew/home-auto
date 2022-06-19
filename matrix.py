#!/bin/env python3
import os
import sys
import magic
import asyncio
import aiofiles.os
from queue import Queue
from PIL import Image
from paho.mqtt import client as paho_client
from nio import AsyncClient, MatrixRoom, RoomMessageText, UploadResponse

MQTT_USER = ""
MQTT_PASS = ""
broker = 'localhost'
port = 1883
client_id = f'matrix'

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

MATRIX_SERVER = ""
MATRIX_USER = ""
MATRIX_TOKEN = ""

PRIVATE_MATRIX_ROOM = ""
SHARED_MATRIX_ROOM = ""

locations = {
    'all': SHARED_MATRIX_ROOM,
    'bedroom': PRIVATE_MATRIX_ROOM
}
room_to_locations = {
    SHARED_MATRIX_ROOM: 'all',
    PRIVATE_MATRIX_ROOM: 'bedroom'
}
async def main() -> None:
    client = AsyncClient(MATRIX_SERVER, MATRIX_USER)
    mqtt_client = connect_mqtt()
    send_queue = Queue()
    image_queue = Queue()
    received = False

    # Messages from Matrix rooms
    async def message_callback(room: MatrixRoom, event: RoomMessageText) -> None:
        if room.room_id in room_to_locations:
            if event.body.lower() == 'enable':
                mqtt_client.publish('/home/matrix/notifications', f"{room_to_locations[room.room_id]}	1")
                if received:
                    send_queue.put(f"{room.room_id}	Notifications enabled")
            if event.body.lower() == 'disable':
                mqtt_client.publish('/home/matrix/notifications', f"{room_to_locations[room.room_id]}	0")
                if received:
                    send_queue.put(f"{room.room_id}	Notifications disabled")

    client.add_event_callback(message_callback, RoomMessageText)
    client.access_token = MATRIX_TOKEN

    def on_message(client, userdata, msg):
        received = True
        if(msg.topic == '/home/matrix/send'):
            r = msg.payload.decode()
            send_queue.put(r)
        elif(msg.topic == '/home/matrix/send/area'):
            args = msg.payload.decode().split('\t')
            area = args[0]
            msg = args[1]
            send_queue.put(f"{locations[area]}	{msg}")
        elif(msg.topic == '/home/matrix/send/event'):
            r = msg.payload.decode()
            send_queue.put(f"{locations['all']}	{r}")
        elif(msg.topic == '/home/matrix/image'):
            r = msg.payload.decode()
            image_queue.put(r)
        else:
            print(f"Unhandled subject received: {msg.topic}")

    mqtt_client.subscribe([
        ("/home/matrix/send", 0),
        ("/home/matrix/send/area", 0),
        ("/home/matrix/image", 0),
        ("/home/matrix/send/event", 0),
    ])
    mqtt_client.on_message = on_message

    i = 1
    
    task = asyncio.create_task(client.sync(timeout=30000))
    async def do_sync(task):
        done, pending = await asyncio.wait([task], timeout=1)
        if(len(done)):
            task = asyncio.create_task(client.sync(timeout=30000))
        return task

    while True:
        sys.stdout.flush()
        mqtt_client.loop()
        task = await do_sync(task)
        while not send_queue.empty():
            args = send_queue.get().split('\t')
            to = args[0]
            msg = args[1]
            await client.room_send(
                    room_id = to,
                    message_type = 'm.room.message',
                    content = {
                        'msgtype': 'm.text', 
                        'body': msg 
                    }
                )
        while not image_queue.empty():
            args = image_queue.get().split('\t')
            to = locations[args[0]]
            image = args[1]
            mime_type = magic.from_file(image, mime=True)  # e.g. "image/jpeg"
            if not mime_type.startswith("image/"):
                print("Drop message because file does not have an image mime type.")
                return
            
            im = Image.open(image)
            (width, height) = im.size  # im.size returns (width,height) tuple

            # first do an upload of image, then send URI of upload to room
            file_stat = await aiofiles.os.stat(image)
            async with aiofiles.open(image, "r+b") as f:
                resp, maybe_keys = await client.upload(
                    f,
                    content_type=mime_type,  # image/jpeg
                    filename=os.path.basename(image),
                    filesize=file_stat.st_size,
            )

            if isinstance(resp, UploadResponse):
                print("Image was uploaded successfully to server. ")
            else:
                print(f"Failed to upload image. Failure response: {resp}")

            content = {
                "body": os.path.basename(image),  # descriptive title
                "info": {
                    "size": file_stat.st_size,
                    "mimetype": mime_type,
                    "thumbnail_info": None,  # TODO
                    "w": width,  # width in pixel
                    "h": height,  # height in pixel
                    "thumbnail_url": None,  # TODO
                },
                "msgtype": "m.image",
                "url": resp.content_uri,
            }

            await client.room_send(to, message_type="m.room.message", content=content)

asyncio.run(main())
