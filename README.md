# django-ws

Helpers for using WebSockets in Django

## Installation

`pip install django-ws`

## Setup

### asgi.py

- Remove line: `from django.core.asgi import get_asgi_application`
- Remove line: `application = get_asgi_application()`

Add to the end:

```python
from django_ws import get_websocket_application

application = get_websocket_application()
```

### ws_urls.py

Next to your root `urls.py` create a `ws_urls.py` like the example below that uses your websocket.

```python
from django.urls import path

import myapp.ws

urlpatterns = [
  path('ws', myapp.ws.MySocket),
]
```

### Write a WebSocket

```python
from django_ws import WebSocketHandler

class MySocket(WebSocketHandler):
  async def on_open(self):
    do_something_on_open()

  async def on_message(self, data):
    do_something_on_msg()

    # send json data
    self.send({"reply": "sending data back"})

  async def on_close(self):
    do_something_on_close()
```

## More Features

### start_ping method

*coming soon*

### start_task method

*coming soon*

### sleep_loop method

*coming soon*
