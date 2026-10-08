import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.models import Payment, PaymentWebhookEvent
from apps.products.models import InventoryMovement, Order, Product


class PaymentGatewayError(Exception):
    pass


def create_checkout_session(payment, *, request=None):
    provider = settings.PAYMENT_PROVIDER
    if provider == "mock":
        if not settings.ALLOW_MOCK_PAYMENTS or (not settings.DEBUG and not settings.DEMO_MODE):
            raise PaymentGatewayError("The mock payment provider is available only in local development or explicit demo mode.")
        url = request.build_absolute_uri(f"/payments/mock/{payment.checkout_token}/") if request else ""
        parsed = urlsplit(url)
        allowed_local_host = parsed.hostname in {"127.0.0.1", "localhost", "::1", "testserver"}
        if not (parsed.scheme == "https" or (parsed.scheme == "http" and allowed_local_host)):
            raise PaymentGatewayError("The local payment simulator requires a local or HTTPS host.")
        payment.checkout_url = url
        payment.status = Payment.Status.PENDING
        payment.save(update_fields=("checkout_url", "status", "updated_at"))
        return url
    if provider != "stripe" or not settings.STRIPE_SECRET_KEY:
        raise PaymentGatewayError("A hosted payment provider is not configured.")
    if not 30 <= settings.PAYMENT_RESERVATION_MINUTES <= 1440:
        raise PaymentGatewayError("Stripe checkout reservations must be between 30 minutes and 24 hours.")

    cents = int((payment.amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if cents < 50:
        raise PaymentGatewayError("The converted payment amount is below the gateway minimum.")
    payload = {
        "mode": "payment",
        "success_url": f"{settings.PUBLIC_SITE_URL}/account/?section=orders&payment=processing&order_id={payment.order_id}" if settings.PUBLIC_SITE_URL else "",
        "cancel_url": f"{settings.PUBLIC_SITE_URL}/cart/?payment=cancelled&order_id={payment.order_id}" if settings.PUBLIC_SITE_URL else "",
        "client_reference_id": str(payment.order_id),
        "metadata[order_id]": str(payment.order_id),
        "metadata[payment_id]": str(payment.pk),
        "payment_intent_data[metadata][order_id]": str(payment.order_id),
        "payment_intent_data[metadata][payment_id]": str(payment.pk),
        "line_items[0][price_data][currency]": payment.currency.lower(),
        "line_items[0][price_data][unit_amount]": str(cents),
        "line_items[0][price_data][product_data][name]": f"Riva order {payment.order_id}",
        "line_items[0][quantity]": "1",
        "expires_at": str(int(payment.order.reservation_expires_at.timestamp())),
    }
    if not payload["success_url"] or not payload["cancel_url"]:
        raise PaymentGatewayError("PUBLIC_SITE_URL must be set to an HTTPS origin before enabling Stripe.")
    if not settings.PUBLIC_SITE_URL.startswith("https://"):
        raise PaymentGatewayError("Stripe checkout requires PUBLIC_SITE_URL to use HTTPS.")
    try:
        response = httpx.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=payload,
            auth=(settings.STRIPE_SECRET_KEY, ""),
            # Retries for one reserved order reuse Stripe's idempotency record and parameters.
            headers={"Idempotency-Key": f"riva-order-{payment.order_id}-checkout-v1"},
            timeout=settings.PAYMENT_GATEWAY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        session_id, checkout_url = data.get("id"), data.get("url")
        if not session_id or not checkout_url or not checkout_url.startswith("https://checkout.stripe.com/"):
            raise PaymentGatewayError("The hosted provider returned an invalid checkout session.")
    except (httpx.HTTPError, ValueError) as exc:
        raise PaymentGatewayError("The hosted provider could not create a checkout session.") from exc
    payment.provider_reference = session_id
    payment.checkout_url = checkout_url
    payment.status = Payment.Status.PENDING
    payment.save(update_fields=("provider_reference", "checkout_url", "status", "updated_at"))
    return checkout_url


def _release_reserved_stock(order, *, actor=None, note):
    movements = InventoryMovement.objects.filter(
        order=order, kind=InventoryMovement.Kind.SALE
    ).select_related("product").order_by("product_id", "pk")
    for movement in movements:
        product = Product.objects.select_for_update().filter(pk=movement.product_id).first()
        if not product or product.stock is None:
            continue
        product.stock += movement.quantity
        product.save(update_fields=("stock",))
        InventoryMovement.objects.create(
            product=product, order=order, kind=InventoryMovement.Kind.RETURN,
            quantity=movement.quantity, reference=f"order:{order.pk}", note=note,
            created_by=actor,
        )


@transaction.atomic
def complete_payment(payment_id, *, provider_reference=None):
    payment = Payment.objects.select_for_update(of=("self",)).select_related("order").get(pk=payment_id)
    if provider_reference and payment.provider_reference != provider_reference:
        raise PaymentGatewayError("Payment reference does not match the stored checkout session.")
    if payment.status == Payment.Status.PAID:
        return payment
    if payment.status not in (Payment.Status.CREATED, Payment.Status.PENDING):
        raise PaymentGatewayError("This payment is no longer payable.")
    payment.status = Payment.Status.PAID
    payment.paid_at = timezone.now()
    payment.save(update_fields=("status", "paid_at", "updated_at"))
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status == Order.Status.AWAITING_PAYMENT:
        order.status = Order.Status.PENDING
        order.save(update_fields=("status", "updated_at"))
    from apps.recommendation.models import RecommendationInteraction
    for item in order.items.select_related("recommendation_run", "product").filter(recommendation_run__isnull=False):
        if item.product_id:
            RecommendationInteraction.objects.get_or_create(
                order_item=item,
                defaults={
                    "recommendation_run": item.recommendation_run,
                    "product_id": item.product_id,
                    "user_id": order.user_id,
                    "kind": RecommendationInteraction.Kind.PURCHASE,
                },
            )
    return payment


@transaction.atomic
def expire_order_payment(payment_id, *, status=Payment.Status.EXPIRED):
    payment = Payment.objects.select_for_update(of=("self",)).select_related("order").get(pk=payment_id)
    if payment.status in (Payment.Status.PAID, Payment.Status.REFUNDED):
        return payment
    if payment.status in (Payment.Status.EXPIRED, Payment.Status.FAILED):
        return payment
    payment.status = status
    payment.save(update_fields=("status", "updated_at"))
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status == Order.Status.AWAITING_PAYMENT:
        _release_reserved_stock(order, note="Stock released after payment did not complete.")
        order.status = Order.Status.CANCELLED
        order.save(update_fields=("status", "updated_at"))
    return payment


def verify_stripe_signature(payload, signature_header, *, now=None):
    if not settings.PAYMENT_WEBHOOK_SECRET:
        return False
    timestamp = None
    signatures = []
    for part in (signature_header or "").split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        return False
    current_time = int(time.time() if now is None else now)
    if abs(current_time - timestamp_int) > settings.PAYMENT_WEBHOOK_TOLERANCE_SECONDS:
        return False
    signed = str(timestamp_int).encode() + b"." + payload
    expected = hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, item) for item in signatures)


def process_stripe_event(payload):
    try:
        event = json.loads(payload)
        event_id = event["id"]
        event_type = event["type"]
        obj = event["data"]["object"]
    except (ValueError, KeyError, TypeError) as exc:
        raise PaymentGatewayError("Malformed payment event.") from exc
    if not isinstance(event_id, str) or not isinstance(event_type, str) or not isinstance(obj, dict):
        raise PaymentGatewayError("Malformed payment event.")
    digest = hashlib.sha256(payload).hexdigest()
    try:
        with transaction.atomic():
            record, _ = PaymentWebhookEvent.objects.get_or_create(
                provider="stripe", event_id=event_id,
                defaults={"event_type": event_type, "payload_sha256": digest},
            )
            record = PaymentWebhookEvent.objects.select_for_update().get(pk=record.pk)
            if record.payload_sha256 != digest:
                raise PaymentGatewayError("A Stripe event ID was reused with a different payload.")
            if record.processed_at:
                return False
            payment_id = int(obj.get("metadata", {}).get("payment_id", ""))
            payment = Payment.objects.select_for_update().get(pk=payment_id, provider=Payment.Provider.CARD)
            if obj.get("id") != payment.provider_reference:
                raise PaymentGatewayError("Payment event session reference did not match.")
            if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
                paid_cents = int(obj.get("amount_total") or 0)
                expected_cents = int((payment.amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                if obj.get("payment_status") != "paid" or paid_cents != expected_cents or obj.get("currency", "").upper() != payment.currency:
                    raise PaymentGatewayError("Paid event amount or currency does not match the order.")
                complete_payment(payment.pk, provider_reference=obj["id"])
            elif event_type in ("checkout.session.expired", "checkout.session.async_payment_failed"):
                expire_order_payment(payment.pk, status=Payment.Status.EXPIRED if event_type.endswith("expired") else Payment.Status.FAILED)
            record.processed_at = timezone.now()
            record.processing_error = ""
            record.save(update_fields=("processed_at", "processing_error"))
    except Exception as exc:
        # The failed business transaction must roll back, while a sanitized audit
        # record must survive so Stripe's retry can safely try the same event again.
        record, created = PaymentWebhookEvent.objects.get_or_create(
            provider="stripe",
            event_id=event_id,
            defaults={
                "event_type": event_type,
                "payload_sha256": digest,
                "processing_error": f"processing_error:{type(exc).__name__}"[:240],
            },
        )
        if not created and record.payload_sha256 == digest and not record.processed_at:
            PaymentWebhookEvent.objects.filter(pk=record.pk).update(
                processing_error=f"processing_error:{type(exc).__name__}"[:240]
            )
        raise
    return True
