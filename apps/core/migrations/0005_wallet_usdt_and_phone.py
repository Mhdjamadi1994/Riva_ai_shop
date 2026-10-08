from django.db import migrations, models


def move_zero_wallets_to_usdt(apps, schema_editor):
    Wallet = apps.get_model("core", "Wallet")
    Wallet.objects.filter(currency="TOMAN", balance=0).update(currency="USDT")


def restore_zero_wallets_to_toman(apps, schema_editor):
    Wallet = apps.get_model("core", "Wallet")
    Wallet.objects.filter(currency="USDT", balance=0).update(currency="TOMAN")


class Migration(migrations.Migration):
    dependencies = [("core", "0004_customerprofile_ip_location_and_more")]
    operations = [
        migrations.AlterField(model_name="wallet", name="currency", field=models.CharField(default="USDT", max_length=12)),
        migrations.AlterField(model_name="wallettransaction", name="currency", field=models.CharField(default="USDT", max_length=12)),
        migrations.AlterField(model_name="customerprofile", name="phone", field=models.CharField(blank=True, max_length=20)),
        migrations.RunPython(move_zero_wallets_to_usdt, restore_zero_wallets_to_toman),
    ]
