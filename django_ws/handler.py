import asyncio
import datetime
import importlib
import logging
import json
import traceback

from django.conf import settings
from django.utils.module_loading import import_string

from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

logger = logging.getLogger(__name__)

from django.utils import timezone

TASK_DUPLICATE_STARTED = "task-duplicate-started"
TASK_WS_CLOSED = "task-websocket-closed"


class WebSocketHandler:
  LOOP_SLEEP_TIME = 0.3
  PROCESS_CANCEL_ERRORS = False

  def __new__(cls, *args, **kwargs):
    if not hasattr(cls, '_middleware'):
      cls._middleware = []
      cls._msg_middleware = []

      if hasattr(settings, 'WS_MIDDLEWARE'):
        for middleware_path in reversed(settings.WS_MIDDLEWARE):
          middleware = import_string(middleware_path)
          cls._middleware.append(middleware)

    return super().__new__(cls)

  def __init__(self, request, receive, send):
    self.request = request
    self._receive = receive
    self._send_coro = send

    self.connected = False
    self.closed = False
    self.tasks = {}

  async def sleep_loop(self, coroutine, cadence, *args, **kwargs):
    last_called = timezone.now()

    while 1:
      now = timezone.now()
      diff = (now - last_called).total_seconds()
      if diff >= cadence:
        await coroutine(*args, **kwargs)
        last_called = now

      await asyncio.sleep(self.LOOP_SLEEP_TIME)

  async def _ping(self):
    await self.send({'ping': timezone.now().isoformat()})

  async def ping(self):
    await self.sleep_loop(self._ping, 59)

  def start_ping(self):
    self.start_task('ping', self.ping)

  def start_task(self, task_id, coroutine, callback=None, args=None, kwargs=None):
    if args is None:
      args = []

    if kwargs is None:
      kwargs = {}

    if task_id in self.tasks and not self.tasks[task_id].done():
      self.tasks[task_id].cancel(msg=TASK_DUPLICATE_STARTED)

    task = asyncio.create_task(coroutine(*args, **kwargs))
    if callback:
      task.add_done_callback(callback)

    task.add_done_callback(self.process_task_exception)
    self.tasks[task_id] = task

  def process_task_exception(self, task):
    try:
      error = task.exception()

    except asyncio.CancelledError as ecancel:
      if self.PROCESS_CANCEL_ERRORS:
        self.on_task_error(ecancel)

    else:
      if error:
        self.on_task_error(error)

  def on_task_error(self, error):
    logger.error("".join(traceback.format_exception(error)))

  def cancel_tasks(self):
    for task_id, task in self.tasks.items():
      if not task.done():
        task.cancel(msg=TASK_WS_CLOSED)

  async def on_open(self):
    pass

  async def on_message(self, message):
    pass

  async def on_close(self):
    pass

  async def on_error(self, error):
    pass

  async def accept_connection(self):
    await self._send({'type': 'websocket.accept'})

  async def _send(self, data):
    try:
      await self._send_coro(data)

    except ConnectionClosedOK:
      self.closed = True

    except ConnectionClosedError:
      self.closed = True

  async def send(self, data):
    await self._send({'type': 'websocket.send', 'text': json.dumps(data)})

  async def process_message(self, msg):
    data = self.load_data(msg)
    await self.on_message(data)

  def load_data(self, msg):
    if 'text' in msg and msg['text']:
      return json.loads(msg['text'])

  async def close(self, code=1000):
    self.closed = True
    await self._send({'type': 'websocket.close', 'code': code})

  @staticmethod
  async def run_loop(ws):
    func = ws._run_loop
    for m in ws._middleware:
      func = m(func)

    return await func(ws)

  @staticmethod
  async def _run_loop(ws):
    try:
      while 1:
        msg = await ws._receive()

        if msg['type'] == 'websocket.connect':
          await ws.accept_connection()
          ws.connected = True
          await ws.on_open()

        elif msg['type'] == 'websocket.disconnect':
          ws.closed = True

        elif msg['type'] == 'websocket.receive':
          await ws.process_message(msg)

        else:
          raise Exception('Unknown websocket event type: ' + msg['type'])

        if ws.closed:
          break

    except Exception as error:
      await ws.on_error(error)
      raise

    ws.cancel_tasks()
    await ws.on_close()
