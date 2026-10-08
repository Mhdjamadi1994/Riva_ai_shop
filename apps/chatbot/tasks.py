from celery import shared_task
from django.conf import settings

from apps.products.models import Product

from .models import SecurityEvent
from .security import PromptInjectionDetected, fingerprint
from .vector_store import delete_product as remove_product_vector
from .vector_store import index_product as upsert_product_vector


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def index_product(product_id):
    if not settings.SEMANTIC_SEARCH_ENABLED:
        return {"indexed": False, "reason": "semantic_search_not_configured"}
    product = Product.objects.get(pk=product_id)
    if product.is_available:
        try:
            upsert_product_vector(product)
        except PromptInjectionDetected as exc:
            SecurityEvent.objects.create(
                source=SecurityEvent.Source.CATALOG,
                rule=exc.rule,
                content_sha256=fingerprint(f"{product.name}\n{product.description}"),
            )
    else:
        remove_product_vector(product_id)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def delete_product(product_id):
    remove_product_vector(product_id)
