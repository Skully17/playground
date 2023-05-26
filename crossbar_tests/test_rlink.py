import os
import signal
import asyncio
from unittest import IsolatedAsyncioTestCase
from autobahn.asyncio import component, ApplicationSession
from autobahn.wamp.types import PublishOptions


class TestBasicWAMPFunctionality(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
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
        self.router = await start_router()

    def tearDown(self) -> None:
        stop_router(self.router)

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

        loop = asyncio.get_event_loop()
        await self.client.start(loop)

        self.assertTrue(self.func1_called)


class TestRLinkFunctionality(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.func1_called = False
        host = "localhost"
        local_port = 8080
        local_transports = [{
            "type": "websocket",
            "url": f"ws://{host}:{local_port}/ws",
            "endpoint": {
                "type": "tcp",
                "host": host,
                "port": int(local_port)
            }
        }]
        local_port = 8081
        remote_transports = [{
            "type": "websocket",
            "url": f"ws://{host}:{local_port}/ws",
            "endpoint": {
                "type": "tcp",
                "host": host,
                "port": int(local_port)
            }
        }]
        self.local_client = component.Component(transports=local_transports, realm="realm1")
        self.remote_client = component.Component(transports=remote_transports, realm="realm1")
        self.local_router = await start_router(log_dir="crossbar_local", config="rlink")
        self.remote_router = await start_router(log_dir="crossbar_remote", cbdir="../.crossbar_remote", config="rlink")

    def tearDown(self) -> None:
        stop_router(self.local_router)
        stop_router(self.remote_router)

    def func1(self, message):
        print(f"func1: {message}")
        self.func1_called = True

    async def test_local_to_local_rpc(self):  # todo: make 2 tests to register and call after and before the rlink connection
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            test_uri = "com.local.1"
            session.register(self.func1, test_uri)
            await session.call(test_uri, "local call")

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")

        loop = asyncio.get_event_loop()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await asyncio.sleep(1)  # todo: make this more sofisticated, a "wait_for_rlink_connection" method

        self.assertTrue(self.func1_called)

    async def test_remote_to_remote_rpc(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")
            self.local_session = session
            test_uri = "com.remote.1"
            session.register(self.func1, test_uri)
            await self.local_session.call(test_uri, "remote call")

        loop = asyncio.get_event_loop()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await asyncio.sleep(1)  # todo: make this more sofisticated, a "wait_for_rlink_connection" method

        self.assertTrue(self.func1_called)

    async def test_local_to_remote_rpc(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            self.local_session = session

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")
            self.remote_session = session
            test_uri = "com.remote.1"
            session.register(self.func1, test_uri)

        loop = asyncio.get_event_loop()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await asyncio.sleep(1)  # todo: make this more sofisticated, a "wait_for_rlink_connection" method

        await self.local_session.call("com.remote.1", "local call")

        self.assertTrue(self.func1_called)

    async def test_remote_to_local_rpc(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            self.local_session = session
            test_uri = "com.local.1"
            session.register(self.func1, test_uri)

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")
            self.remote_session = session

        loop = asyncio.get_event_loop()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await asyncio.sleep(10)  # todo: make this more sofisticated, a "wait_for_rlink_connection" method

        await self.remote_session.call("com.local.1", "remote call")

        self.assertTrue(self.func1_called)


async def start_router(log_dir="crossbar_tests", cbdir="../.crossbar_local", config="config"):
    """Starts Crossbar Router and waits for it to finish the initial setup"""
    router = await asyncio.create_subprocess_shell(
        f"crossbar start --logdir=/tmp/{log_dir} --logtofile --cbdir={cbdir} --config={config}.json",
        preexec_fn=os.setsid
    )
    attempt = 0
    router_started = False
    while attempt < 10 and not router_started:
        await asyncio.sleep(1)
        # todo: this does not work properly. how do we reliably know the router has finished booting?
        # with open(f"/tmp/{log_dir}/node.log", "r+") as fp:
        #     for line_no, line in enumerate(fp):
        #         if "NODE_BOOT_COMPLETE" in line:
        #             print(f"Router With '{cbdir}/{config}.json' Config Started")
        #             router_started = True
        #             fp.truncate(0)
        #             break
        attempt += 1
    return router


def stop_router(router):
    """
    This kills all the processes in the router's Process Group. This is necessary as "router.kill" only kills the
    subprocess, not the Crossbar that is called in the subprocess
    """
    if router:
        os.killpg(os.getpgid(router.pid), signal.SIGTERM)
