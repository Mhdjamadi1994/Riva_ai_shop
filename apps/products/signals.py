import logging
from functools import partial

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.chatbot.tasks import delete_product as delete_product_task
from apps.chatbot.tasks import index_product as index_product_task

from .models import Product

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def product_saved_handler(sender, instance, **kwargs):
    """Queue semantic indexing after the product transaction commits."""
    update_fields = kwargs.get("update_fields")
    if update_fields and set(update_fields).issubset({"stock"}):
        return
    if not settings.SEMANTIC_SEARCH_ENABLED:
        return
    try:
        transaction.on_commit(partial(index_product_task.delay, instance.pk), robust=True)
    except Exception:
        logger.exception("Could not enqueue product %s for semantic indexing.", instance.pk)


@receiver(post_delete, sender=Product)
def product_deleted_handler(sender, instance, **kwargs):
    """Remove deleted products from Qdrant after the database transaction commits."""
    try:
        transaction.on_commit(partial(delete_product_task.delay, instance.pk), robust=True)
    except Exception:
        logger.exception("Could not enqueue deletion of product %s from the semantic index.", instance.pk)
