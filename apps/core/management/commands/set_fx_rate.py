from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.models import ExchangeRate


class Command(BaseCommand):
    help = "Record an audited USD/TOMAN exchange-rate quote."

    def add_arguments(self, parser):
        parser.add_argument("rate", help="Toman per one US dollar")
        parser.add_argument("--source", required=True, help="Rate provider or operator/source label")
        parser.add_argument("--username", help="Admin username to associate with this rate")

    def handle(self, *args, **options):
        try:
            rate = Decimal(options["rate"])
        except InvalidOperation as exc:
            raise CommandError("Rate must be a positive decimal.") from exc
        if not rate.is_finite() or rate <= 0:
            raise CommandError("Rate must be a positive decimal.")
        source = options["source"].strip()[:100]
        if not source:
            raise CommandError("Provide a source label for audit history.")
        user = None
        if options.get("username"):
            user = get_user_model().objects.filter(username=options["username"]).first()
            if not user:
                raise CommandError("The requested user does not exist.")
        quote = ExchangeRate.objects.create(
            base_currency="USD", quote_currency="TOMAN", rate=rate,
            source=source, observed_at=timezone.now(), created_by=user,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Recorded USD/TOMAN {quote.rate} from {quote.source} at {quote.observed_at.isoformat()}."
        ))
