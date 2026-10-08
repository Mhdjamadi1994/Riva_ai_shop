from django.contrib import admin

from .models import ChatMessage, Conversation, ModelInvocation, SecurityEvent


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("role", "content", "created_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "telegram_chat_id", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("user__username", "telegram_chat_id")
    inlines = (ChatMessageInline,)


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "rule", "user", "created_at")
    list_filter = ("source", "rule", "created_at")
    readonly_fields = ("user", "source", "rule", "content_sha256", "created_at")
    search_fields = ("content_sha256", "rule")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ModelInvocation)
class ModelInvocationAdmin(admin.ModelAdmin):
    list_display = ("id", "purpose", "model", "duration_ms", "succeeded", "error_code", "created_at")
    list_filter = ("purpose", "succeeded", "created_at")
    readonly_fields = ("purpose", "model", "duration_ms", "succeeded", "error_code", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
