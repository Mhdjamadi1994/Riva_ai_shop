import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    display_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(max_length=1200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.get_username()}"


class CustomerSupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    class Department(models.TextChoices):
        SUPPORT = "support", "General support"
        SALES = "sales", "Product sales"
        INVENTORY = "inventory", "Orders and delivery"
        ACCOUNTING = "accounting", "Payments and billing"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets")
    subject = models.CharField(max_length=140)
    message = models.TextField(max_length=5000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    staff_reply = models.TextField(max_length=5000, blank=True)
    department = models.CharField(max_length=16, choices=Department.choices, default=Department.SUPPORT)
    agent_draft = models.TextField(max_length=3000, blank=True)
    agent_processed_at = models.DateTimeField(null=True, blank=True)
    auto_response_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Ticket #{self.pk}: {self.subject}"


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shop_wallet")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=12, default="USDT")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.user.get_username()}"


class WalletTransaction(models.Model):
    class Kind(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"
        PURCHASE = "purchase", "Purchase"
        REFUND = "refund", "Refund"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        POSTED = "posted", "Posted"
        FAILED = "failed", "Failed"

    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="transactions")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=12, default="USDT")
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    description = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} {self.amount} {self.currency} ({self.status})"


class Payment(models.Model):
    class Provider(models.TextChoices):
        CARD = "card", "Hosted card gateway"
        CRYPTO = "crypto", "Crypto payment provider"
        WALLET = "wallet", "Wallet"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shop_payments")
    order = models.ForeignKey("products.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    wallet_transaction = models.OneToOneField(WalletTransaction, null=True, blank=True, on_delete=models.PROTECT, related_name="payment")
    provider = models.CharField(max_length=12, choices=Provider.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=12, default="TOMAN")
    provider_reference = models.CharField(max_length=160, null=True, blank=True, unique=True)
    # Nullable for legacy payments; checkout creation always assigns a token.
    checkout_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    checkout_url = models.URLField(max_length=1000, blank=True)
    checkout_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.pk} ({self.status})"


class ExchangeRate(models.Model):
    base_currency = models.CharField(max_length=3, default="USD")
    quote_currency = models.CharField(max_length=8, default="TOMAN")
    rate = models.DecimalField(max_digits=20, decimal_places=6, validators=[MinValueValidator(Decimal("0.000001"))])
    source = models.CharField(max_length=100)
    observed_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-observed_at", "-pk")
        indexes = [models.Index(fields=("base_currency", "quote_currency", "-observed_at"))]
        constraints = [models.UniqueConstraint(
            fields=("base_currency", "quote_currency", "source", "observed_at"),
            name="unique_exchange_rate_source_observation",
        )]

    def __str__(self):
        return f"{self.base_currency}/{self.quote_currency} {self.rate} ({self.source})"


class PaymentWebhookEvent(models.Model):
    provider = models.CharField(max_length=24, default="stripe")
    event_id = models.CharField(max_length=160)
    event_type = models.CharField(max_length=100)
    payload_sha256 = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.CharField(max_length=240, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("provider", "event_id"), name="unique_payment_webhook_event")]
        ordering = ("-received_at",)

    def __str__(self):
        return f"{self.provider} {self.event_type} ({self.event_id})"
