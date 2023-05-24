import asyncio
from unittest import IsolatedAsyncioTestCase
from autobahn.asyncio import component, ApplicationSession
from autobahn.wamp.types import PublishOptions


class TestBasicWAMPFunctionality(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.func1_called = False
        host = "localhost"
        port = 8080
        transports = [{
            "type": "websocket",
            "url": f"ws://{host}:{port}/ws",
            "endpoint": {
                "type": "tcp",
                "host": host,
                "port": int(port)
            }
        }]
        self.client = component.Component(transports=transports, realm="realm1")

    def func1(self, message):
        print(f"func1: {message}")
        self.func1_called = True

    async def test_rpc(self):
        @self.client.on_join
        async def _(session: ApplicationSession, details):
            print("client joined router")
            test_uri = "com.test_rpc.1"
            session.register(self.func1, test_uri)
            await session.call(test_uri, "local call")
            session.leave()

        await start_router()
        loop = asyncio.get_event_loop()
        await self.client.start(loop)

        self.assertTrue(self.func1_called)

    async def test_pub_sub(self):
        @self.client.on_join
        async def _(session: ApplicationSession, details):
            print("client joined router")
            test_uri = "com.test_pub_sub.1"
            session.subscribe(self.func1, test_uri)
            session.publish(test_uri, "local publish", options=PublishOptions(exclude_me=False))
            session.leave()

        await start_router()
        loop = asyncio.get_event_loop()
        await self.client.start(loop)

        self.assertTrue(self.func1_called)


async def start_router():
    """Starts Crossbar Router and waits for it to finish the initial setup"""
    await asyncio.create_subprocess_shell(
        "crossbar start --logdir=/tmp/crossbar_tests --logtofile --cbdir=../.crossbar"
    )
    attempt = 0
    router_started = False
    while attempt < 10 and not router_started:
        await asyncio.sleep(1)
        with open("/tmp/crossbar_tests/node.log", "r+") as fp:
            for line_no, line in enumerate(fp):
                if "NODE_BOOT_COMPLETE" in line:
                    print("Router Started")
                    router_started = True
                    fp.truncate(0)
                    break
        attempt += 1
    return router_started
