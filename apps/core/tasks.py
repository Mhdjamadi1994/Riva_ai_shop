from celery import shared_task
from django.db import OperationalError
from django.utils import timezone

from apps.core.models import Payment
from apps.core.payments import expire_order_payment
from apps.core.fx_provider import FXRateProviderError, refresh_usd_toman_rate as fetch_usd_toman_rate
from apps.products.models import Order


@shared_task(autoretry_for=(OperationalError,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def expire_stale_order_payments():
    now = timezone.now()
    stale_ids = list(
        Payment.objects.filter(
            status__in=(Payment.Status.CREATED, Payment.Status.PENDING),
            order__status=Order.Status.AWAITING_PAYMENT,
            order__reservation_expires_at__lte=now,
        ).values_list("pk", flat=True)[:500]
    )
    expired = 0
    for payment_id in stale_ids:
        previous = Payment.objects.filter(pk=payment_id).values_list("status", flat=True).first()
        if previous not in (Payment.Status.CREATED, Payment.Status.PENDING):
            continue
        result = expire_order_payment(payment_id)
        expired += result.status == Payment.Status.EXPIRED
    return {"expired_payment_attempts": expired}


@shared_task(
    autoretry_for=(FXRateProviderError, OperationalError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 4},
)
def refresh_usd_toman_rate():
    quote = fetch_usd_toman_rate()
    return {
        "rate": str(quote.rate),
        "source": quote.source,
        "observed_at": quote.observed_at.isoformat(),
    }
