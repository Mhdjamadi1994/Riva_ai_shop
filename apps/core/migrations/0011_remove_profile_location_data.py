from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_exchangerate_unique_exchange_rate_source_observation"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="customerprofile",
            name="ip_location",
        ),
        migrations.RemoveField(
            model_name="customerprofile",
            name="location_updated_at",
        ),
    ]
