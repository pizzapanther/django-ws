from django.conf import settings
from django.core.asgi import get_asgi_application
from django.urls import resolve
from django.urls.exceptions import Resolver404


def get_websocket_application(http_app=None):
  if http_app is None:
    http_app = get_asgi_application()

  async def app(scope, receive, send):
    default_root_conf = settings.ROOT_URLCONF.replace('.urls', '.ws_urls')
    root_conf = getattr(settings, 'ROOT_WS_URLCONF', default_root_conf)

    if scope["type"] == "websocket":
      try:
        rmatch = resolve(scope['path'], urlconf=root_conf)

      except Resolver404:
        return await http_app(scope, receive, send)

      else:
        request = WebSocketRequest(scope, None)
        ws = rmatch.func(request, receive, send, *rmatch.args, **rmatch.kwargs)
        return await ws.run_loop()

    return await http_app(scope, receive, send)

  return app
