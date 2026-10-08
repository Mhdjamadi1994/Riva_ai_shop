

import logging
from django.core.management.base import BaseCommand, CommandError
from apps.products.models import Product
from apps.chatbot.vector_store import index_product, _client, _ensure_collection
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-indexes all available products into the Qdrant vector database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Index all products, including unavailable ones (default is only available).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of products to process in batches.",
        )

    def handle(self, *args, **options):
        if not settings.SEMANTIC_SEARCH_ENABLED:
            raise CommandError("Set EMBEDDING_MODEL, LLM_BASE_URL, and LLM_API_KEY before re-indexing semantic search.")
        self.stdout.write(self.style.NOTICE("Initializing vector collection check..."))
        client = _client()
        _ensure_collection(client)

        include_all = options["all"]
        queryset = Product.objects.all() if include_all else Product.objects.filter(is_available=True)
        total_count = queryset.count()

        if total_count == 0:
            self.stdout.write(self.style.WARNING("No products found to index."))
            return

        self.stdout.write(
            self.style.SUCCESS(f"Found {total_count} products. Starting re-indexing to collection '{settings.QDRANT_COLLECTION}'...")
        )

        success_count = 0
        error_count = 0

        for product in queryset.iterator(chunk_size=options["batch_size"]):
            try:
                index_product(product)
                success_count += 1
                self.stdout.write(f"  [OK] Product #{product.pk}: {product.name[:40]}")
            except Exception as exc:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"  [FAIL] Product #{product.pk}: {exc}"))

        self.stdout.write(self.style.SUCCESS(f"\nFinished: {success_count} indexed successfully, {error_count} failed."))
