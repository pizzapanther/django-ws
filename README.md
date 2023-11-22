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

**Usage:** `self.start_ping()`

Sends a ping `{'ping': timezone.now().isoformat()}` every 59 seconds to keep the websocket alive. Sometimes this is needed with certain deployment environments.

### start_task method

**Usage:** `self.start_task(<task_id>, <coroutine>)`

**Example:** `self.start_task('send_weather', self.send_weather)`

Creates an [asyncio background task](https://docs.python.org/3/library/asyncio-task.html#creating-tasks). `django-ws` handles tracking duplicate tasks by ID and cancelling tasks during interruptions such as disconnects. Note: you still need to be careful about long running processing. Even if you `await` a long running function, it will block the socket from closing. So do things in small chunks that can be interrupted.

### sleep_loop method

**Usage:** `await self.sleep_loop(<coroutine>, <seconds:int>)`

**Example:** `await self.sleep_loop(self._send_weather, 60 * 3)`

Does an infinite loop and sleeps for the given seconds after each sleep. Uses an async sleep so that it does not block other tasks.

## Middleware

Websockets in general follow a different lifecycle then HTTP requests.

![websocket sequence](https://raw.githubusercontent.com/pizzapanther/django-ws/main/websocket-sequence.png)

This means websockets in Django do not have a pre-established middleware mechanism. However, middleware is still helpful with websockets.

## Websocket Middleware

The websocket middleware functions much like the standard Django request/response middleware; however, since websockets open a long lived connection and messages are received and sent asynchronously it works slightly different.

This middleware is good for authenticating the initial websocket connections, and performing setup and tear down.

Websocket middleware setup in `settings.py`:

```python
WS_MIDDLEWARE = [
    'myproject.middleware.AuthAsyncMiddleware',
]
```

Example middleware:

```python
from importlib import import_module

from asgiref.sync import sync_to_async

from django.contrib import auth
from django.conf import settings


class AuthAsyncMiddleware:
    def __init__(self, func):
        self.func = func

    async def __call__(self, ws):
        print('Pre Run Loop')

        if not hasattr(ws.request, 'user'):
            engine = import_module(settings.SESSION_ENGINE)
            SessionStore = engine.SessionStore
            session_key = ws.request.COOKIES.get(settings.SESSION_COOKIE_NAME)
            ws.request.session = SessionStore(session_key)
            ws.request.user = await sync_to_async(auth.get_user)(ws.request)

        print('USER:', ws.request.user)

        ret = await self.func(ws)

        print('POST Run Loop')

        return ret
```

