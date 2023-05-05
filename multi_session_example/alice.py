import asyncio

from autobahn.asyncio.component import Component, run
from autobahn.wamp.protocol import ApplicationSession


class SessionHandler:
    def __init__(self):
        self.__sessions = []

    @property
    def sessions(self):
        return self.__sessions

    def add(self, session):
        self.__sessions.append(session)

    def remove(self, session):
        self.__sessions.remove(session)

    def call(self, topic, *args, **kwargs):
        for session in self.sessions:
            session.call(topic, *args, **kwargs)

    def publish(self, topic, *args, **kwargs):
        for session in self.sessions:
            session.publish(topic, *args, **kwargs)


def speak(message):
    print(f"{message}")


def shout(message):
    print(f"{message}!".upper())


hello = "Hello from Alice"
session_handler = SessionHandler()

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
    local_hello = f"{details.transport.peer}: {hello}"
    session_handler.add(session)
    # session.subscribe(print_message, "com.local.sub1")
    # session.subscribe(print_message, "com.local.sub2")
    session.register(speak, "com.alice.speak")
    session.register(shout, "com.alice.shout")
    # while True:
    #     session.call("com.alice.speak", local_hello)
    #     session.call("com.alice.shout", local_hello)
    #     session.call("com.bob.speak", local_hello)
    #     session.call("com.charlie.speak", local_hello)
    #     await asyncio.sleep(10)


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

component2 = Component(transports=transports, realm=realm)


@component2.on_join
async def on_join(session: ApplicationSession, details):
    print("joined")
    local_hello = f"{details.transport.peer}: {hello}"
    session_handler.add(session)
    # session.subscribe(print_message, "com.local.sub1")
    # session.subscribe(print_message, "com.local.sub2")
    session.register(speak, "com.alice.speak")
    session.register(shout, "com.alice.shout")
    while True:
        # session.call("com.alice.speak", local_hello)
        # # session.call("com.alice.shout", local_hello)
        # session.call("com.bob.speak", local_hello)
        # session.call("com.charlie.speak", local_hello)

        # demonstrating making single call which goes to all connected Crossbar Router
        session_handler.call("com.alice.speak", f"{local_hello} to myself")
        session_handler.call("com.bob.speak", f"{local_hello} to bob")
        session_handler.call("com.charlie.speak", f"{local_hello} to charlie")
        session_handler.publish("com.everyone.speak", f"{local_hello} to everyone")
        await asyncio.sleep(10)


run([component, component2])
