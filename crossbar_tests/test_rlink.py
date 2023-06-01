import os
import signal
import asyncio
from unittest import IsolatedAsyncioTestCase
from autobahn.asyncio import component, ApplicationSession
from autobahn.wamp.types import PublishOptions


def basic_config(host, port):
    return [{
        "type": "websocket",
        "url": f"ws://{host}:{port}/ws",
        "endpoint": {
            "type": "tcp",
            "host": host,
            "port": int(port)
        }
    }]


class TestBasicWAMPFunctionality(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.func1_called = False
        host = "localhost"
        port = 56789
        transports = basic_config(host, port)
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
            publish(session, test_uri, "local publish")
            session.leave()

        loop = asyncio.get_event_loop()
        await self.client.start(loop)

        self.assertTrue(self.func1_called)


class TestRLinkWAMPFunctionality(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.local_session = None
        self.remote_session = None
        self.func1_called = False
        host = "localhost"
        local_port = 56789
        remote_port = 56790
        local_transports = basic_config(host, local_port)
        remote_transports = basic_config(host, remote_port)
        self.local_client = component.Component(transports=local_transports, realm="realm1")
        self.remote_client = component.Component(transports=remote_transports, realm="realm1")
        self.local_router = await start_router(log_dir="crossbar_local", config="rlink")
        self.remote_router = await start_router(log_dir="crossbar_remote", cbdir="../.crossbar_remote", config="rlink")

    def tearDown(self) -> None:
        stop_router(self.local_router)
        stop_router(self.remote_router)

    async def wait_for_join(self):
        attempt = 0
        while True:
            if self.local_session and self.remote_session or not attempt < 60:
                break
            attempt += 1
            await asyncio.sleep(1)

    def func1(self, message):
        print(f"func1: {message}")
        self.func1_called = True

    async def test_local_to_local_rpc(self):  # todo: make 2 tests to register and call after and before the rlink connection
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            self.local_session = session
            test_uri = "com.local.1"
            session.register(self.func1, test_uri)
            await session.call(test_uri, "local call")

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")
            self.remote_session = session

        loop = asyncio.get_event_loop()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await self.wait_for_join()

        self.assertTrue(self.func1_called)

    async def test_remote_to_remote_rpc(self):
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
            await session.call(test_uri, "remote call")

        loop = asyncio.get_event_loop()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await self.wait_for_join()

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
        await self.wait_for_join()

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
        await self.wait_for_join()

        await self.remote_session.call("com.local.1", "remote call")

        self.assertTrue(self.func1_called)


class TestRLinkForwardingFunctionality(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.local_session = None
        self.remote_session = None
        self.func1_called = False
        self.func2_called = False
        host = "localhost"
        local_port = 56789
        remote_port = 56790
        local_transports = basic_config(host, local_port)
        remote_transports = basic_config(host, remote_port)
        self.local_client = component.Component(transports=local_transports, realm="realm1")
        self.remote_client = component.Component(transports=remote_transports, realm="realm1")
        self.local_router = None
        self.remote_router = None

    def tearDown(self) -> None:
        print("tearDown Called")
        if self.local_client:
            self.local_client.stop()
        if self.remote_client:
            self.remote_client.stop()
        if self.local_router:
            stop_router(self.local_router)
        if self.remote_router:
            stop_router(self.remote_router)

    async def wait_for_join(self, local=True, remote=True):
        attempt = 0
        while True:
            if (self.local_session or not local) and (self.remote_session or not remote) or not attempt < 60:
                break
            await asyncio.sleep(1)
            attempt += 1

    def func1(self, message):
        print(f"func1: {message}")
        self.func1_called = True

    def func2(self, message):
        print(f"func2: {message}")
        self.func2_called = True

    async def test_local_to_remote_late_connect(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            self.local_session = session

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")
            self.remote_session = session
            session.register(self.func1, "com.remote.1")
            session.subscribe(self.func2, "com.remote.2")

        loop = asyncio.get_event_loop()
        self.local_router = await start_router(log_dir="crossbar_local", config="rlink")
        self.local_client.start(loop)
        await self.wait_for_join(remote=False)
        self.remote_router = await start_router(log_dir="crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        await wait_for_rlink_connection()
        self.remote_client.start(loop)
        await self.wait_for_join()

        print("calling")
        await self.local_session.call("com.remote.1", "local call")
        print("publishing")
        publish(self.local_session, "com.remote.2", "local publish")
        await asyncio.sleep(1)

        self.assertTrue(self.func1_called)
        self.assertTrue(self.func2_called)

    async def test_remote_to_local_late_connect(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            self.local_session = session
            session.register(self.func1, "com.local.1")
            session.subscribe(self.func2, "com.local.2")

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")
            self.remote_session = session

        loop = asyncio.get_event_loop()
        self.local_router = await start_router(log_dir="crossbar_local", config="rlink")
        self.local_client.start(loop)
        await self.wait_for_join(remote=False)
        self.remote_router = await start_router(log_dir="crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        await wait_for_rlink_connection()
        self.remote_client.start(loop)
        await self.wait_for_join()

        await self.remote_session.call("com.local.1", "remote call")
        publish(self.remote_session, "com.local.2", "remote publish")
        await asyncio.sleep(1)

        self.assertTrue(self.func1_called)
        self.assertTrue(self.func2_called)

    async def test_local_to_remote_restart_remote(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            self.local_session = session

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")
            self.remote_session = session
            session.register(self.func1, "com.remote.1")
            session.subscribe(self.func2, "com.remote.2")

        loop = asyncio.get_event_loop()
        self.local_router = await start_router(log_dir="crossbar_local", config="rlink")
        self.remote_router = await start_router(log_dir="crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        await wait_for_rlink_connection()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await self.wait_for_join()

        # The remote router is "restarted"
        stop_router(self.remote_router)
        self.remote_session = None
        self.remote_router = await start_router(log_dir="crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        await wait_for_rlink_connection()
        await self.wait_for_join(local=False)

        print("calling")
        await self.local_session.call("com.remote.1", "local call")
        print("publishing")
        publish(self.local_session, "com.remote.2", "local publish")
        await asyncio.sleep(1)

        self.assertTrue(self.func1_called)
        self.assertTrue(self.func2_called)

    async def test_remote_to_local_restart_remote(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            self.local_session = session
            session.register(self.func1, "com.local.1")
            session.subscribe(self.func2, "com.local.2")

        @self.remote_client.on_join
        async def _(session: ApplicationSession, details):
            print("remote client joined router")
            self.remote_session = session

        loop = asyncio.get_event_loop()
        self.local_router = await start_router(log_dir="crossbar_local", config="rlink")
        self.local_client.start(loop)
        await self.wait_for_join(remote=False)
        self.remote_router = await start_router(log_dir="crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        self.remote_client.start(loop)
        await self.wait_for_join()

        await self.remote_session.call("com.local.1", "remote call")
        publish(self.remote_session, "com.local.2", "remote publish")
        await asyncio.sleep(1)

        self.assertTrue(self.func1_called)
        self.assertTrue(self.func2_called)


async def wait_for_rlink_connection(log_dir="/tmp/crossbar_local"):
    old_success = "Ok, router-to-router rlink started"
    success = "RLinkRemoteSession.onJoin()"
    rlink_not_connected = True
    tries = 0
    while rlink_not_connected or tries > 10:
        with open(f"{log_dir}/node.log", "r+") as fp:
            for line_no, line in enumerate(fp):
                if success in line:
                    print(f"rlink connected")
                    rlink_not_connected = False
                    break
        await asyncio.sleep(1)
        tries += 1

async def start_router(log_dir="crossbar_tests", cbdir="../.crossbar_local", config="config", event_listener=False):
    """Starts Crossbar Router and waits for it to finish the initial setup"""
    # empty log files so there is no contamination with previously run routers
    with open(f"/tmp/crossbar_local/node.log", "w") as fp:
        fp.truncate(0)
    with open(f"/tmp/crossbar_remote/node.log", "w") as fp:
        fp.truncate(0)

    router = await asyncio.create_subprocess_shell(
        f"crossbar start --logdir=/tmp/{log_dir} --logtofile --cbdir={cbdir} --config={config}.json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=os.setsid
    )
    if event_listener:
        asyncio.create_task(error_listener(router))
    print(f"Router With '{cbdir}/{config}.json' Config Started")
    return router


def stop_router(router):
    """
    This kills all the processes in the router's Process Group. This is necessary as "router.kill" only kills the
    subprocess, not the Crossbar that is called in the subprocess
    """
    if router and router.returncode is None:
        # router.terminate()
        os.killpg(os.getpgid(router.pid), signal.SIGTERM)


def publish(session: ApplicationSession, topic, *args, **kwargs):
    """
    This is just so we don't have to pass 'exclude_me' and 'acknowledge' options every time we call publish.
    See more: https://autobahn.readthedocs.io/en/latest/reference/autobahn.wamp.html#autobahn.wamp.types.PublishOptions
    """
    return session.publish(topic, *args, options=PublishOptions(acknowledge=True, exclude_me=False), **kwargs)


async def error_listener(process):
    out, error = await process.communicate()
    if error:
        # stop_router(process)
        # raise Exception(error)
        print(error)
    print(out)
