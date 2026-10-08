import logging
from typing import Any, Dict, Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.chatbot.models import ChatMessage, Conversation

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatService:
    def __init__(self, orchestrator: Any = None):
        if orchestrator is None:
            from apps.agents.services import AgentOrchestrator
            orchestrator = AgentOrchestrator()
        self.orchestrator = orchestrator

    def process_message(
        self,
        user_id: Optional[int],
        telegram_chat_id: Optional[str],
        message_text: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Legacy-compatible entry point.
        Returns: (bot_reply_text, metadata)
        """
        user = None
        if user_id is not None:
            user = User.objects.filter(pk=user_id).first()

        with transaction.atomic():
            if telegram_chat_id:
                conversation, _ = Conversation.objects.get_or_create(
                    telegram_chat_id=str(telegram_chat_id),
                    defaults={"user": user},
                )
            elif user is not None:
                conversation, _ = Conversation.objects.get_or_create(
                    user=user,
                )
            else:
                conversation = Conversation.objects.create(user=None)

            if user is not None and conversation.user_id is None:
                conversation.user = user
                conversation.save(update_fields=["user", "updated_at"])

            assistant_message, metadata = self._process_conversation(
                conversation=conversation,
                message_text=message_text,
            )
            return assistant_message.content, metadata

    def process_user_message(
        self,
        conversation: Conversation,
        message_text: str,
    ) -> Tuple[ChatMessage, Dict[str, Any]]:
        """
        Entry point used by ChatAPIView / TelegramWebhookAPIView.
        Returns: (assistant_message_object, metadata)
        """
        with transaction.atomic():
            return self._process_conversation(
                conversation=conversation,
                message_text=message_text,
            )

    def _process_conversation(
        self,
        conversation: Conversation,
        message_text: str,
    ) -> Tuple[ChatMessage, Dict[str, Any]]:
        ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.USER,
            content=message_text,
        )

        agent_result = self.orchestrator.process_query(
            query=message_text,
            session_id=str(conversation.id),
        )

        bot_reply = agent_result.get(
            "response",
            "I am processing your request.",
        )
        metadata = agent_result.get("metadata", {})

        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.ASSISTANT,
            content=bot_reply,
        )

        return assistant_message, metadata


def get_or_create_telegram_conversation(
    telegram_chat_id: str,
) -> Conversation:
    conversation, _ = Conversation.objects.get_or_create(
        telegram_chat_id=str(telegram_chat_id),
    )
    return conversation


def reply_to_text(
    text: str,
    conversation: Conversation,
    user: Any = None,
    source: str = "telegram",
) -> Dict[str, Any]:
    """
    Compatibility wrapper for integration callers.
    """
    service = ChatService()
    bot_message, metadata = service.process_user_message(
        conversation=conversation,
        message_text=text,
    )
    return {
        "reply": bot_message.content,
        "conversation_id": conversation.id,
        "metadata": metadata,
    }
