"""Fetch and audit a configured USD/TOMAN quote from an approved provider."""
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import ExchangeRate


class FXRateProviderError(ValueError):
    """A provider response is unavailable, malformed, or outside policy."""


def refresh_usd_toman_rate():
    url = settings.FX_RATE_PROVIDER_URL
    if not url:
        raise FXRateProviderError("FX_RATE_PROVIDER_URL is not configured.")
    if urlsplit(url).scheme != "https":
        raise FXRateProviderError("The exchange-rate provider must use HTTPS.")

    headers = {}
    if settings.FX_RATE_PROVIDER_TOKEN:
        headers["Authorization"] = f"Bearer {settings.FX_RATE_PROVIDER_TOKEN}"
    try:
        response = httpx.get(url, headers=headers, timeout=5.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise FXRateProviderError("The configured exchange-rate provider could not be read.") from exc
    if not isinstance(payload, dict):
        raise FXRateProviderError("The provider response must be a JSON object.")

    try:
        rate = Decimal(str(payload["rate"]))
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise FXRateProviderError("The provider must return a positive TOMAN-per-USD 'rate'.") from exc
    if not rate.is_finite() or rate <= 0:
        raise FXRateProviderError("The provider must return a positive TOMAN-per-USD 'rate'.")

    observed_raw = payload.get("observed_at")
    observed_at = parse_datetime(observed_raw) if isinstance(observed_raw, str) else None
    if not observed_at or not timezone.is_aware(observed_at):
        raise FXRateProviderError("The provider must return an ISO-8601 timezone-aware 'observed_at'.")
    now = timezone.now()
    if observed_at > now + timedelta(minutes=5):
        raise FXRateProviderError("The provider timestamp is in the future.")
    if now - observed_at > timedelta(hours=settings.FX_RATE_MAX_AGE_HOURS):
        raise FXRateProviderError("The provider returned an exchange rate outside the freshness window.")

    source = settings.FX_RATE_PROVIDER_SOURCE or str(payload.get("source", "")).strip()
    if not source:
        raise FXRateProviderError("Set FX_RATE_PROVIDER_SOURCE to a stable provider name.")
    source = source[:100]
    quote, _ = ExchangeRate.objects.get_or_create(
        base_currency="USD",
        quote_currency="TOMAN",
        source=source,
        observed_at=observed_at,
        defaults={"rate": rate},
    )
    if quote.rate != rate:
        raise FXRateProviderError("The provider changed a quote for an already recorded observation.")
    return quote
