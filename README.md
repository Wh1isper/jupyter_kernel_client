# jupyter_kernel_client

Code execution client based on jupyter server websocket

## How to use

### 1. Start Jupyter Server(or Lab)

Enter the following command to start

```bash
jupyter server
```

By default, you'll get output like below, and you can get your server host is `localhost`, port is `8888`, token
is `fa42b5d1f787df44f5ca70a88c4fa6f2d42fdb4a1838c59b`

```
...
[C 2022-12-12 17:37:40.953 ServerApp]
        http://localhost:8888/?token=fa42b5d1f787df44f5ca70a88c4fa6f2d42fdb4a1838c59b
     or http://127.0.0.1:8888/?token=fa42b5d1f787df44f5ca70a88c4fa6f2d42fdb4a1838c59b
```

### 2. Start a kernel

Using Jupyter Server REST API to start a kernel

see: [POST /api/kernels](https://jupyter-server.readthedocs.io/en/latest/developers/rest-api.html#post--api-kernels)

TODO: Start kernel by client

### 3. Connect to kernel and execute code

You can get the `kernel_id` in the request to start the kernel

```python
from jupyter_kernel_client.client import KernelWebsocketClient

client = KernelWebsocketClient(
    kernel_id=kernel_id,  # you can get it in 2. Start a kernel
    port='8888',  # you can get port in 1. Start Jupyter Server(or Lab)
    host='localhost',  # you can get host in 1. Start Jupyter Server(or Lab)
    token=token,  # you can get token in 1. Start Jupyter Server(or Lab)
)

code = """
print('hello world')
"""

import asyncio

result = asyncio.run(client.execute(code))
print(result)
```

You will get

```bash
{'outputs': [{'output_type': 'stream', 'name': 'stdout', 'text': 'hello world\n'}], 'execution_count': 1}
```
