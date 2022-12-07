import asyncio
import json

import pytest

from jupyter_kernel_client.client import KernelWebsocketClient


async def test_websocket_client(jp_fetch, jp_ws_fetch, jp_auth_header, jp_http_port, jp_base_url):
    kernel_response = await jp_fetch(
        "api",
        "kernels",
        method="POST",
        body=json.dumps({"name": "python3", "path": "Untitled.ipynb"}),
    )
    kernel_id = json.loads(kernel_response.body)["id"]

    client = KernelWebsocketClient(
        kernel_id=kernel_id,
        port=jp_http_port,
        base_url=jp_base_url,
        auth_header=jp_auth_header,
        encoded=True,
    )

    code = """
print('hello world')
"""

    result = await client.execute(code)
    assert result == {
        "execution_count": 1,
        "outputs": [{"output_type": "stream", "name": "stdout", "text": "hello world\n"}],
    }


async def test_callback(jp_fetch, jp_ws_fetch, jp_auth_header, jp_http_port, jp_base_url):
    kernel_response = await jp_fetch(
        "api",
        "kernels",
        method="POST",
        body=json.dumps({"name": "python3", "path": "Untitled.ipynb"}),
    )
    kernel_id = json.loads(kernel_response.body)["id"]

    client = KernelWebsocketClient(
        kernel_id=kernel_id,
        port=jp_http_port,
        base_url=jp_base_url,
        auth_header=jp_auth_header,
        encoded=True,
    )

    code = """
print('hello world')
"""

    class _:
        count = 0

        @classmethod
        def callback(cls):
            cls.count = cls.count + 1

    client.register_callback(_.callback)
    result = await client.execute(code)
    assert result == {
        "execution_count": 1,
        "outputs": [{"output_type": "stream", "name": "stdout", "text": "hello world\n"}],
    }
    assert _.count > 0


if __name__ == "__main__":
    pytest.main()
