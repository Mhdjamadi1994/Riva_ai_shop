import logging
import secrets

import httpx
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.chatbot.chat_service import reply_to_text
from apps.chatbot.llm import LLMUnavailable
from apps.chatbot.api_serializers import (
    APIErrorSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer,
    TelegramUpdateSerializer,
    TelegramWebhookResponseSerializer,
)
from apps.chatbot.models import Conversation, SecurityEvent
from apps.chatbot.security import PromptInjectionDetected
from apps.products.models import Product

logger = logging.getLogger(__name__)

TELEGRAM_BLOCKED_MESSAGE = "This message was blocked by the security policy."


class ChatAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "llm"

    @extend_schema(
        request=ChatRequestSerializer,
        responses={200: ChatResponseSerializer, 400: APIErrorSerializer, 404: APIErrorSerializer, 503: APIErrorSerializer},
    )
    def post(self, request, *args, **kwargs):
        message_text = request.data.get("message", "")
        if not isinstance(message_text, str) or not message_text.strip():
            return Response(
                {"error": "The 'message' field is required and must be a non-empty string."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation_id = request.data.get("conversation_id")
        if conversation_id:
            try:
                conversation = Conversation.objects.get(pk=conversation_id, user=request.user)
            except (Conversation.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            conversation = Conversation.objects.create(user=request.user)

        try:
            chat_result = reply_to_text(
                message_text.strip(),
                conversation,
                user=request.user,
                source=SecurityEvent.Source.API,
                include_metadata=True,
            )
            if isinstance(chat_result, tuple):
                reply_text, chat_metadata = chat_result
            else:  # Keep custom/legacy chat providers compatible.
                reply_text, chat_metadata = chat_result, {}
        except PromptInjectionDetected:
            return Response(
                {"error": "Message blocked by security policy."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LLMUnavailable:
            logger.warning("Chat request could not reach the configured AI provider.")
            return Response({"error": "The shopping assistant is temporarily unavailable."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("Chat processing error")
            return Response({"error": "Failed to process chat message."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                "conversation_id": conversation.pk,
                "reply": reply_text,
                "metadata": chat_metadata,
            },
            status=status.HTTP_200_OK,
        )


class ConversationHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id, *args, **kwargs):
        try:
            conversation = Conversation.objects.get(pk=conversation_id, user=request.user)
        except (Conversation.DoesNotExist, ValueError, TypeError):
            return Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        messages = conversation.messages.order_by("created_at", "pk")
        return Response(
            {
                "conversation_id": conversation.pk,
                "messages": [
                    {
                        "id": message.pk,
                        "role": message.role,
                        "content": message.content,
                        "created_at": message.created_at,
                    }
                    for message in messages
                ],
            },
            status=status.HTTP_200_OK,
        )


class TelegramWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "telegram"

    @extend_schema(
        request=TelegramUpdateSerializer,
        responses={200: TelegramWebhookResponseSerializer, 403: APIErrorSerializer},
    )
    def post(self, request, *args, **kwargs):
        webhook_secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

        if not webhook_secret or not secrets.compare_digest(str(header_secret), str(webhook_secret)):
            return Response({"error": "Invalid webhook secret token."}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data
        if not isinstance(payload, dict):
            return Response({"ok": True}, status=status.HTTP_200_OK)

        message = payload.get("message") or payload.get("edited_message")
        if not isinstance(message, dict):
            return Response({"ok": True}, status=status.HTTP_200_OK)

        sender = message.get("from") or {}
        if not isinstance(sender, dict) or sender.get("is_bot", False):
            return Response({"ok": True}, status=status.HTTP_200_OK)

        chat = message.get("chat") or {}
        if not isinstance(chat, dict):
            return Response({"ok": True}, status=status.HTTP_200_OK)

        chat_id = chat.get("id")
        text = message.get("text")
        if chat_id is None or not isinstance(text, str) or not text.strip():
            return Response({"ok": True}, status=status.HTTP_200_OK)

        text = text.strip()
        command = text.split(maxsplit=1)[0].lower().split("@", 1)[0]

        if command in {"/start", "/help"}:
            reply_text = (
                "Hello! Welcome to the AI Shop Assistant.\n"
                "You can ask about any product or search our catalog."
            )
        elif command == "/products":
            products = Product.objects.filter(is_available=True)[:5]
            if products:
                items = []
                base_url = getattr(settings, "PUBLIC_SITE_URL", "")
                for product in products:
                    usd_price = product.price / settings.TOMAN_PER_USD
                    link = f" {base_url}/products/{product.pk}/" if base_url else ""
                    items.append(f"- {product.name}: ${usd_price:.2f}{link}")
                reply_text = "Available Products:\n" + "\n".join(items)
            else:
                reply_text = "No products currently available."
        else:
            conversation, _ = Conversation.objects.get_or_create(telegram_chat_id=str(chat_id))
            try:
                reply_text, metadata = reply_to_text(
                    text,
                    conversation,
                    source=SecurityEvent.Source.TELEGRAM,
                    include_metadata=True,
                )
                base_url = getattr(settings, "PUBLIC_SITE_URL", "")
                recommendations = metadata.get("products", [])
                if base_url and recommendations:
                    links = [f"- {item['name']}: {base_url}{item['url']}" for item in recommendations[:3]]
                    reply_text += "\n\nProduct pages:\n" + "\n".join(links)
            except PromptInjectionDetected:
                reply_text = TELEGRAM_BLOCKED_MESSAGE
            except ValueError:
                reply_text = "Invalid message."
            except Exception:
                logger.exception("Telegram chat processing error")
                reply_text = "An error occurred while processing your message."

        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        if token:
            try:
                response = httpx.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": reply_text},
                    timeout=10.0,
                )
                response.raise_for_status()
            except Exception:
                logger.exception("Failed to dispatch Telegram message")

        return Response({"ok": True}, status=status.HTTP_200_OK)
