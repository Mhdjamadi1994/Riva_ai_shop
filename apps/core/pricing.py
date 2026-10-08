from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import ExchangeRate


class ExchangeRateUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class ExchangeQuote:
    rate: Decimal
    source: str
    observed_at: object
    stale: bool = False
    configured: bool = True


def get_usd_toman_quote(*, require_fresh=False):
    latest = ExchangeRate.objects.filter(
        base_currency="USD", quote_currency="TOMAN"
    ).first()
    now = timezone.now()
    max_age = timedelta(hours=settings.FX_RATE_MAX_AGE_HOURS)
    if latest:
        stale = now - latest.observed_at > max_age
        if require_fresh and stale:
            raise ExchangeRateUnavailable(
                "The USD/TOMAN exchange rate is stale. Update the rate before checkout."
            )
        return ExchangeQuote(latest.rate, latest.source, latest.observed_at, stale, True)
    if require_fresh and not settings.ALLOW_UNAUDITED_FX_FALLBACK:
        raise ExchangeRateUnavailable(
            "No audited USD/TOMAN exchange rate is configured. Update the rate before checkout."
        )
    return ExchangeQuote(
        Decimal(settings.TOMAN_PER_USD),
        "local configuration" if settings.DEBUG else "configuration fallback",
        now,
        False,
        settings.DEBUG,
    )
