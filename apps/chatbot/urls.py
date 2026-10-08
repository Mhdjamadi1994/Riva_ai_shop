from django.urls import path
from .views import ChatAPIView, TelegramWebhookAPIView

urlpatterns = [
    path("", ChatAPIView.as_view(), name="chat_root"),
    path("message/", ChatAPIView.as_view(), name="chat_message"),
    path("telegram/webhook/", TelegramWebhookAPIView.as_view(), name="telegram_webhook"),
]
