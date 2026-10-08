from django.core.management.base import BaseCommand, CommandError

from apps.core.fx_provider import FXRateProviderError, refresh_usd_toman_rate


class Command(BaseCommand):
    help = "Fetch and record the latest quote from the configured USD/TOMAN provider."

    def handle(self, *args, **options):
        try:
            quote = refresh_usd_toman_rate()
        except FXRateProviderError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"Recorded USD/TOMAN {quote.rate} from {quote.source} at {quote.observed_at.isoformat()}."
        ))
