from django.contrib import admin
from django.contrib import messages
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail

from .models import CustomerProfile, CustomerSupportTicket, ExchangeRate, Payment, PaymentWebhookEvent, Wallet, WalletTransaction


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "phone", "updated_at")
    search_fields = ("user__username", "user__email", "display_name", "phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CustomerSupportTicket)
class CustomerSupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "user", "department", "status", "auto_response_sent", "created_at", "updated_at")
    list_filter = ("department", "status", "auto_response_sent", "created_at", "updated_at")
    search_fields = ("subject", "message", "user__username", "user__email")
    readonly_fields = ("user", "subject", "message", "agent_draft", "agent_processed_at", "auto_response_sent", "created_at", "updated_at")
    fields = readonly_fields + ("department", "status", "staff_reply")
    actions = ("send_approved_replies",)

    @admin.action(description="Send approved staff replies to customers by email")
    def send_approved_replies(self, request, queryset):
        sent = 0
        skipped = 0
        failed = 0
        for ticket in queryset.select_related("user"):
            recipient = (ticket.user.email or "").strip()
            if ticket.auto_response_sent or not recipient or not ticket.staff_reply.strip():
                skipped += 1
                continue
            try:
                delivered = send_mail(
                    subject=f"Re: {ticket.subject}",
                    message=ticket.staff_reply,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False,
                )
            except Exception:
                failed += 1
                continue
            if delivered:
                ticket.auto_response_sent = True
                ticket.save(update_fields=("auto_response_sent", "updated_at"))
                sent += 1
            else:
                failed += 1
        if sent:
            self.message_user(request, f"Sent {sent} approved reply email(s).", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} ticket(s) without an unsent reply and recipient email.", messages.WARNING)
        if failed:
            self.message_user(request, f"Could not send {failed} email(s). Check the configured email service.", messages.ERROR)


class WalletTransactionInline(admin.TabularInline):
    model = WalletTransaction
    extra = 0
    can_delete = False
    readonly_fields = ("kind", "status", "amount", "currency", "reference", "description", "created_at")
    fields = readonly_fields


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "currency", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "balance", "currency", "updated_at")
    inlines = (WalletTransactionInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "order", "provider", "status", "amount", "currency", "created_at")
    list_filter = ("provider", "status", "currency", "created_at")
    search_fields = ("user__username", "provider_reference", "order__id")
    readonly_fields = tuple(field.name for field in Payment._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("base_currency", "quote_currency", "rate", "source", "observed_at", "created_by")
    list_filter = ("base_currency", "quote_currency", "source", "observed_at")
    search_fields = ("source",)
    readonly_fields = ("created_at", "created_by")
    ordering = ("-observed_at",)

    def save_model(self, request, obj, form, change):
        if change:
            raise ValidationError("Exchange-rate history is immutable; record a new quote instead.")
        obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_type", "event_id", "received_at", "processed_at")
    list_filter = ("provider", "event_type", "received_at", "processed_at")
    search_fields = ("event_id", "event_type", "payload_sha256")
    readonly_fields = tuple(field.name for field in PaymentWebhookEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
