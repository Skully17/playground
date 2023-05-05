import asyncio

from autobahn.asyncio.component import Component, run
from autobahn.wamp import types
from autobahn.wamp.protocol import ApplicationSession


def print_message(message):
    print(f"Received message ({message})")


host = "localhost"
port = 1338
transports = [{
    "type": "websocket",
    "url": f"ws://{host}:{port}/ws",
    "endpoint": {
        "type": "tcp",
        "host": host,
        "port": port,
    }
}]
realm = "realm1"

component = Component(transports=transports, realm=realm)


@component.on_join
async def on_join(session: ApplicationSession, details):
    session.subscribe(print_message, "com.remote.sub1")
    session.subscribe(print_message, "com.remote.sub2")
    session.register(print_message, "com.remote.reg1")
    session.register(print_message, "com.remote.reg2")
    while True:
        # session.publish("com.local.sub1", "remote publish", options=types.PublishOptions(exclude_me=False))
        # session.publish("com.local.sub2", "remote publish", options=types.PublishOptions(exclude_me=False))
        # session.publish("com.remote.sub1", "remote publish", options=types.PublishOptions(exclude_me=False))
        # session.publish("com.remote.sub2", "remote publish", options=types.PublishOptions(exclude_me=False))
        session.call("com.local.reg1", "remote call")
        # session.call("com.local.reg2", "remote call")
        session.call("com.remote.reg1", "remote call")
        # session.call("com.remote.reg2", "remote call")
        await asyncio.sleep(10)


run([component])
