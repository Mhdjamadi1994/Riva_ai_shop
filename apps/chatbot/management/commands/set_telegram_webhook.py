from urllib.parse import urlsplit

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Register the public HTTPS URL for the Telegram bot webhook."

    def add_arguments(self, parser):
        parser.add_argument("url", help="Full public HTTPS URL ending in /api/chat/telegram/webhook/")

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        secret = settings.TELEGRAM_WEBHOOK_SECRET
        if not token or not secret:
            raise CommandError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET first.")
        if not 1 <= len(secret) <= 256 or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in secret):
            raise CommandError("TELEGRAM_WEBHOOK_SECRET must use 1-256 letters, digits, underscores, or hyphens.")

        url = options["url"]
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise CommandError("Webhook URL must be a public HTTPS URL without embedded credentials.")
        if parsed.query or parsed.fragment or not parsed.path.rstrip("/").endswith("/api/chat/telegram/webhook"):
            raise CommandError("Webhook URL must end with /api/chat/telegram/webhook/ and have no query or fragment.")

        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={"url": url, "secret_token": secret},
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CommandError(f"Telegram webhook registration failed ({type(exc).__name__}).") from None

        if not isinstance(result, dict) or result.get("ok") is not True:
            raise CommandError("Telegram rejected webhook registration.")
        self.stdout.write(self.style.SUCCESS("Telegram webhook registered."))
