from django.urls import path
from .consumers import LabTerminalConsumer

websocket_urlpatterns = [
    path("ws/lab/<str:name>/", LabTerminalConsumer.as_asgi()),
]
