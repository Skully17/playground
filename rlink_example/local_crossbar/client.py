import asyncio

from autobahn.asyncio.component import Component, run
from autobahn.wamp.protocol import ApplicationSession


def print_message(message):
    print(f"Received message ({message})")


host = "localhost"
port = 1337
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
    print("joined")
    session.subscribe(print_message, "com.local.sub1")
    session.subscribe(print_message, "com.local.sub2")
    session.register(print_message, "com.local.reg1")
    session.register(print_message, "com.local.reg2")
    while True:
        # session.publish("com.local.sub1", "local publish", options=types.PublishOptions(exclude_me=False))
        # session.publish("com.local.sub2", "local publish", options=types.PublishOptions(exclude_me=False))
        # session.publish("com.remote.sub1", "local publish", options=types.PublishOptions(exclude_me=False))
        # session.publish("com.remote.sub2", "local publish", options=types.PublishOptions(exclude_me=False))
        session.call("com.local.reg1", "local call")
        # session.call("com.local.reg2", "local call")
        session.call("com.remote.reg1", "local call")
        # session.call("com.remote.reg2", "local call")
        await asyncio.sleep(10)


run([component])
