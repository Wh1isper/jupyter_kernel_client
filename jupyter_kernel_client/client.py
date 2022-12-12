import inspect
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp
import nbformat
from yarl import URL


async def ensure_async(obj):
    # Copyright (c) Jupyter Development Team.
    # Distributed under the terms of the Modified BSD License.

    """Convert a non-awaitable object to a coroutine if needed,
    and await it if it was not already awaited.
    """
    if inspect.isawaitable(obj):
        try:
            result = await obj
        except RuntimeError as e:
            if str(e) == "cannot reuse already awaited coroutine":
                # obj is already the coroutine's result
                return obj
            raise
        return result
    # obj doesn't need to be awaited
    return obj


class KernelWebsocketClient:
    """
    Client connect to kernel channel, execute code and get response

    Example:
        > client = KernelWebsocketClient(
            kernel_id=kernel_id,
            port=jp_http_port,
            base_url=jp_base_url,
            auth_header=jp_auth_header,
            encoded=True,
        )
        > result = await client.execute("print('hello world')")
        > assert result == {
             'execution_count': 1,
             'outputs': [{'output_type': 'stream', 'name': 'stdout', 'text': 'hello world\n'}]
         }

    see execute for more information

    """

    def __init__(
        self,
        kernel_id: str,
        proto: str = "ws",
        host: str = "localhost",
        port: str or int = "8888",
        base_url: str = "/",
        token: Optional[str] = None,
        auth_header: Optional[Dict] = None,
        encoded: bool = False,
        verify_ssl: bool = True,
    ):
        self.kernel_id = kernel_id
        self.proto = proto
        self.host = host
        self.port = port
        base_url = base_url.strip("/")
        self.base_url = "/" + base_url if base_url else ""

        self.url = f"{proto}://{host}:{port}"
        self.session_id = str(uuid4())
        if not auth_header:
            auth_header = {"Authorization": f"token {token}"} if token else dict()
        self.auth_header = auth_header
        self.param = {"session_id": self.session_id}
        self.url_path = f"{self.base_url}/api/kernels/{self.kernel_id}/channels"
        if encoded:
            self.url_path = URL(self.url_path, encoded=True)
        self.verify_ssl = verify_ssl

        self.outputs: List[nbformat.NotebookNode] = []
        self.execution_count: Optional[int] = None
        self.callbacks: callable = []

    async def execute(self, code, wait_for_idle=False) -> Dict[str, Any]:
        """
        :param code(str): code to execute
        :param wait_for_idle(bool): whether send kernel_info_request and wait for idle
        :return:
            {
               "outputs": [nbformat.NotebookNode]
               "execution_count": int or None
            }
        """

        async with aiohttp.ClientSession(
            base_url=self.url,
            headers=self.auth_header,
        ) as session:
            async with session.ws_connect(
                self.url_path,
                params=self.param,
                verify_ssl=self.verify_ssl,
            ) as ws:
                if wait_for_idle:
                    await self.wait_for_idle(ws)
                message_id = await self.execute_code(ws, code)
                return await self.process_until_idle(ws, message_id)

    async def wait_for_idle(self, ws) -> None:
        request_info_msg = self.create_msg("shell", "kernel_info_request")

        await ws.send_json(request_info_msg)
        while True:
            response = await ws.receive_json()
            if (
                response["channel"] == "iopub"
                and response["parent_header"]["msg_id"] == request_info_msg["header"]["msg_id"]
            ):
                content = response.get("content", dict())
                status = content.get("execution_state")
                if status == "idle":
                    return

    async def execute_code(self, ws, code) -> str:
        shell_content = self.shell_content(code)
        msg = self.create_msg("shell", "execute_request", content=shell_content)
        await ws.send_json(msg)
        return msg["header"]["msg_id"]

    async def process_until_idle(self, ws, message_id) -> Dict[str, Any]:
        while True:
            response = await ws.receive_json()
            if response["parent_header"]["msg_id"] == message_id:
                if await self.process_msg(response):
                    return self.get_result()

    def create_msg(
        self,
        channel: str,
        msg_type: Optional[str] = None,
        header: Optional[Dict] = None,
        content: Optional[Dict] = None,
        buffers: Optional[List] = None,
        metadata: Optional[Dict] = None,
        parent_header: Optional[Dict] = None,
    ):
        if not header:
            header = dict()
        header.setdefault("msg_id", str(uuid4()))
        header.setdefault("session", self.session_id)
        header.setdefault("version", "5.2")
        header.setdefault("date", datetime.utcnow().isoformat() + "Z")
        if msg_type:
            header["msg_type"] = msg_type
        if not header.get("msg_type"):
            raise KeyError("message's header need msg_type")

        return {
            "buffers": buffers or [],
            "channel": channel,
            "header": header,
            "content": content or {},
            "metadata": metadata or {},
            "parent_header": parent_header or {},
        }

    def shell_content(self, code):
        return {
            "silent": False,
            "store_history": True,
            "user_expressions": {},
            "allow_stdin": True,
            "stop_on_error": True,
            "code": code,
        }

    async def process_msg(self, msg):
        idled = False
        channel = msg["channel"]
        if channel == "iopub":
            idled = self.on_iopub(msg)
        # notify changes
        await self.notify()

        return idled

    def on_iopub(self, msg) -> bool:
        # iopub will tell execution is idled or not
        content = msg.get("content", dict())
        status = content.get("execution_state")
        msg_type = msg.get("msg_type")
        if status == "idle":
            return True
        if msg_type in ["execute_result", "stream", "display_data", "error"]:
            self.outputs.append(nbformat.v4.output_from_msg(msg))
        execution_count = content.get("execution_count")
        if execution_count:
            self.execution_count = int(execution_count)
        return False

    def get_result(self) -> Dict[str, Any]:
        return {"outputs": self.outputs, "execution_count": self.execution_count}

    def register_callback(self, callback):
        self.callbacks.append(callback)

    async def notify(self):
        for callback in self.callbacks:
            await ensure_async(callback())
