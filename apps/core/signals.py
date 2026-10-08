from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import CustomerProfile, Wallet


@receiver(post_save, sender=get_user_model())
def ensure_customer_account_records(sender, instance, created, **kwargs):
    CustomerProfile.objects.get_or_create(user=instance)
    Wallet.objects.get_or_create(user=instance, defaults={"currency": "USDT"})


@receiver(post_migrate)
def ensure_existing_users_have_account_records(sender, **kwargs):
    if sender.name != "apps.core":
        return
    User = get_user_model()
    for user in User.objects.only("pk").iterator():
        CustomerProfile.objects.get_or_create(user_id=user.pk)
        Wallet.objects.get_or_create(user_id=user.pk, defaults={"currency": "USDT"})
