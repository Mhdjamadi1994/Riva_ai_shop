from django.conf import settings
from django.db import models


class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shop_conversations",
    )
    telegram_chat_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=12, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class SecurityEvent(models.Model):
    class Source(models.TextChoices):
        API = "api", "API"
        TELEGRAM = "telegram", "Telegram"
        CATALOG = "catalog", "Product catalog"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_events",
    )
    source = models.CharField(max_length=12, choices=Source.choices)
    rule = models.CharField(max_length=80)
    content_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ModelInvocation(models.Model):
    class Purpose(models.TextChoices):
        CHAT = "chat", "Chat response"
        EMBEDDING = "embedding", "Embedding"
        REPORT = "report", "Admin report"

    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    model = models.CharField(max_length=120, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    succeeded = models.BooleanField(default=False)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
