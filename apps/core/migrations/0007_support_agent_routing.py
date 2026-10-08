from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0006_customersupportticket")]

    operations = [
        migrations.AddField(
            model_name="customersupportticket",
            name="department",
            field=models.CharField(
                choices=[("support", "General support"), ("sales", "Product sales"), ("inventory", "Orders and delivery"), ("accounting", "Payments and billing")],
                default="support", max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="customersupportticket", name="agent_draft",
            field=models.TextField(blank=True, max_length=3000),
        ),
        migrations.AddField(
            model_name="customersupportticket", name="agent_processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customersupportticket", name="auto_response_sent",
            field=models.BooleanField(default=False),
        ),
    ]
