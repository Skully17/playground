import os
import signal
import asyncio
from typing import Optional
from unittest import IsolatedAsyncioTestCase, skip
from autobahn.asyncio import component, ApplicationSession
from autobahn.wamp.types import PublishOptions


class TestCrossbarBase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.func1_called = False
        self.local_session: Optional[ApplicationSession] = None
        self.host = "localhost"
        local_port = 56789
        local_transports = basic_config(self.host, local_port)
        self.local_client = component.Component(transports=local_transports, realm="realm1")
        self.local_router = None

    def func1(self, message):
        out = f"func1: {message}"
        print(out)
        self.func1_called = True
        return out


class TestCrossbarRlinkBase(TestCrossbarBase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.remote_session: Optional[ApplicationSession] = None
        self.remote_router = None
        remote_port = 56790
        remote_transports = basic_config(self.host, remote_port)
        self.remote_client = component.Component(transports=remote_transports, realm="realm1")
        self.remote_client.on_join(self.on_join_remote)
        self.local_client.on_join(self.on_join_local)

    def func2(self, message):
        print(f"func2: {message}")
        self.func2_called = True

    async def wait_for_join(self, local=True, remote=True):
        attempt = 0
        while True:
            if (self.local_session or not local) and (self.remote_session or not remote) or not attempt < 60:
                break
            attempt += 1
            await asyncio.sleep(1)

    async def on_join_local(self, session: ApplicationSession, details):
        print("local client joined router")
        self.local_session = session

    async def on_join_remote(self, session: ApplicationSession, details):
        print("remote client joined router")
        self.remote_session = session

    async def on_join_local_reg_sub(self, session: ApplicationSession, details):
        self.local_registration = await session.register(self.func1, "com.local.1")
        self.local_subscription = await session.subscribe(self.func2, "com.local.2")

    async def on_join_remote_reg_sub(self, session: ApplicationSession, details):
        self.remote_registration = await session.register(self.func1, "com.remote.1")
        self.remote_subscription = await session.subscribe(self.func2, "com.remote.2")


class TestWAMPFunctionality(TestCrossbarBase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.local_router = await start_router()

    def tearDown(self) -> None:
        stop_router(self.local_router)

    async def test_rpc(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("client joined router")
            test_uri = "com.test_rpc.1"
            session.register(self.func1, test_uri)
            await session.call(test_uri, "local call")
            session.leave()

        loop = asyncio.get_event_loop()
        await self.local_client.start(loop)

        self.assertTrue(self.func1_called)

    async def test_pub_sub(self):
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("client joined router")
            test_uri = "com.test_pub_sub.1"
            session.subscribe(self.func1, test_uri)
            publish(session, test_uri, "local publish")
            session.leave()

        loop = asyncio.get_event_loop()
        await self.local_client.start(loop)

        self.assertTrue(self.func1_called)


class TestRLinkWAMPFunctionality(TestCrossbarRlinkBase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.local_router = await start_router(config="rlink")
        self.remote_router = await start_router(
            log_dir="/tmp/crossbar_remote", cbdir="../.crossbar_remote", config="rlink")

    def tearDown(self) -> None:
        stop_router(self.local_router)
        stop_router(self.remote_router)

    async def test_local_to_local_rpc(self):  # todo: make 2 tests to register and call after and before the rlink connection
        @self.local_client.on_join
        async def _(session: ApplicationSession, details):
            print("local client joined router")
            self.local_session = session
            test_uri = "com.local.1"
            session.register(self.func1, test_uri)
            await session.call(test_uri, "local call")

        loop = asyncio.get_event_loop()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await self.wait_for_join()

        self.assertTrue(self.func1_called)

    async def test_remote_to_remote_rpc(self):
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

        loop = asyncio.get_event_loop()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await self.wait_for_join()

        await self.remote_session.call("com.local.1", "remote call")

        self.assertTrue(self.func1_called)


class TestRLinkForwardingFunctionality(TestCrossbarRlinkBase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.func2_called = False

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

        delete_log()
        delete_log(log_dir="/tmp/crossbar_remote")

    async def start_routers_and_clients(self):
        loop = asyncio.get_event_loop()
        self.local_router = await start_router(config="rlink")
        self.remote_router = await start_router(
            log_dir="/tmp/crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        await wait_for_rlink_connection()
        self.local_client.start(loop)
        self.remote_client.start(loop)
        await self.wait_for_join()

    async def start_routers_and_clients_late_local_start(self):
        loop = asyncio.get_event_loop()
        self.remote_router = await start_router(
            log_dir="/tmp/crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        self.remote_client.start(loop)
        await self.wait_for_join(local=False)
        self.local_router = await start_router(config="rlink")
        await wait_for_rlink_connection()
        self.local_client.start(loop)
        await self.wait_for_join()

    async def start_routers_and_clients_late_remote_start(self):
        loop = asyncio.get_event_loop()
        self.local_router = await start_router(config="rlink")
        self.local_client.start(loop)
        await self.wait_for_join(remote=False)
        self.remote_router = await start_router(
            log_dir="/tmp/crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        await wait_for_rlink_connection()
        self.remote_client.start(loop)
        await self.wait_for_join()

    async def local_call_and_publish_test(self):
        print("calling")
        await self.local_session.call("com.remote.1", "local call")
        print("publishing")
        publish(self.local_session, "com.remote.2", "local publish")
        await asyncio.sleep(1)

        self.assertTrue(self.func1_called)
        self.assertTrue(self.func2_called)

    async def remote_call_and_publish_test(self):
        print("calling")
        await self.remote_session.call("com.local.1", "remote call")
        print("publishing")
        publish(self.remote_session, "com.local.2", "remote publish")
        await asyncio.sleep(1)

        self.assertTrue(self.func1_called)
        self.assertTrue(self.func2_called)

    async def restart_local_client(self):
        loop = asyncio.get_event_loop()
        self.local_client.stop()
        self.local_session = None
        await asyncio.sleep(1)
        self.local_client.start(loop)
        await self.wait_for_join()

    async def restart_remote_client(self):
        loop = asyncio.get_event_loop()
        self.remote_client.stop()
        self.remote_session = None
        await asyncio.sleep(1)
        self.remote_client.start(loop)
        await self.wait_for_join()

    async def restart_local_router(self):
        stop_router(self.local_router)
        self.local_session = None
        self.local_router = await start_router(config="rlink")
        await wait_for_rlink_connection()
        await self.wait_for_join()

    async def restart_remote_router(self):
        stop_router(self.remote_router)
        self.remote_session = None
        self.remote_router = await start_router(log_dir="/tmp/crossbar_remote", cbdir="../.crossbar_remote", config="rlink")
        await wait_for_rlink_connection()
        await self.wait_for_join()

    async def test_local_to_remote_late_remote_connect(self):
        self.remote_client.on_join(self.on_join_remote_reg_sub)

        await self.start_routers_and_clients_late_remote_start()

        await self.local_call_and_publish_test()

    async def test_remote_to_local_late_remote_connect(self):
        self.local_client.on_join(self.on_join_local_reg_sub)

        await self.start_routers_and_clients_late_remote_start()

        await self.remote_call_and_publish_test()

    async def test_local_to_remote_late_local_connect(self):
        self.remote_client.on_join(self.on_join_remote_reg_sub)

        await self.start_routers_and_clients_late_local_start()

        await self.local_call_and_publish_test()

    async def test_remote_to_local_late_local_connect(self):
        self.local_client.on_join(self.on_join_local_reg_sub)

        await self.start_routers_and_clients_late_local_start()

        await self.remote_call_and_publish_test()

    async def test_local_to_remote_restart_local_router(self):
        self.remote_client.on_join(self.on_join_remote_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_local_router()

        await self.local_call_and_publish_test()

    async def test_remote_to_local_restart_local_router(self):
        self.local_client.on_join(self.on_join_local_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_local_router()

        await self.remote_call_and_publish_test()

    async def test_local_to_remote_restart_remote_router(self):
        self.remote_client.on_join(self.on_join_remote_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_remote_router()

        await self.local_call_and_publish_test()

    async def test_remote_to_local_restart_remote_router(self):
        self.local_client.on_join(self.on_join_local_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_remote_router()

        await self.remote_call_and_publish_test()

    async def test_multi_directional_restart_remote_router(self):
        self.local_client.on_join(self.on_join_local_reg_sub)
        self.remote_client.on_join(self.on_join_remote_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_remote_router()

        await self.local_call_and_publish_test()
        await self.remote_call_and_publish_test()

    async def test_local_to_remote_restart_local_client(self):
        self.remote_client.on_join(self.on_join_remote_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_local_client()

        await self.local_call_and_publish_test()

    async def test_remote_to_local_restart_local_client(self):
        self.local_client.on_join(self.on_join_local_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_local_client()

        await self.remote_call_and_publish_test()

    async def test_local_to_remote_restart_remote_client(self):
        self.remote_client.on_join(self.on_join_remote_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_remote_client()

        await self.local_call_and_publish_test()

    async def test_remote_to_local_restart_remote_client(self):
        self.local_client.on_join(self.on_join_local_reg_sub)
        await self.start_routers_and_clients()

        await self.restart_remote_client()

        await self.remote_call_and_publish_test()

    @skip("WIP: Testing re-registering as it doesn't seem to work properly")
    async def test_unregister_restart_remote_router(self):
        self.local_client.on_join(self.on_join_local_reg_sub)
        self.remote_client.on_join(self.on_join_remote_reg_sub)
        await self.start_routers_and_clients()
        await self.restart_remote_router()

        await self.local_session.call("com.remote.1", "local call")
        await self.remote_session.call("com.remote.1", "remote call")
        await self.local_registration.unregister()
        await asyncio.sleep(1)
        try:
            await self.local_session.call("com.local.1", "local call")
        except:
            assert True
        else:
            assert False
        try:
            responce = await self.remote_session.call("com.local.1", "remote call")
            print(f"yay 2: {responce}")
        except:
            assert True
        else:
            assert True
        await self.local_session.register("com.local.1", self.func2)
        await self.local_session.call("com.local.1", "local call")
        await self.remote_session.call("com.local.1", "remote call")

        await self.remote_registration.unregister()
        try:
            await self.local_session.call("com.remote.1", "local call")
            print("yay 3")
        except:
            assert True
        else:
            assert False
        try:
            await self.remote_session.call("com.remote.1", "remote call")
            print("yay 4")
        except:
            assert True
        else:
            assert False


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


async def wait_for_rlink_connection(log_dir="/tmp/crossbar_local"):
    success = "RLinkRemoteSession.onJoin()"
    rlink_not_connected = True
    tries = 0
    while rlink_not_connected and tries < 10:
        with open(f"{log_dir}/node.log", "r") as fp:
            for line_no, line in enumerate(fp):
                if success in line:
                    print(f"rlink connected")
                    rlink_not_connected = False
                    break
        await asyncio.sleep(1)
        tries += 1


async def start_router(log_dir="/tmp/crossbar_local", cbdir="../.crossbar_local", config="config", event_listener=False):
    """Starts Crossbar Router and waits for it to finish the initial setup"""
    # empty log files so there is no contamination with previously run routers
    delete_log()
    delete_log(log_dir="/tmp/crossbar_remote")

    router = await asyncio.create_subprocess_shell(
        f"crossbar start --logdir={log_dir} --logtofile --cbdir={cbdir} --config={config}.json",
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


def delete_log(log_dir="/tmp/crossbar_local"):
    # todo: These try/excepts are an attempt to fix the error on first run when the log file doesn't exist but did not work
    try:
        with open(f"{log_dir}/node.log", "r+") as fp:
            # print(fp.read())  # for debugging
            fp.truncate(0)
    except:
        pass
