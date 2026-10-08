from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("products", "0007_product_engagement")]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="category",
            field=models.CharField(
                choices=[
                    ("laptops", "Laptops"), ("keyboards", "Keyboards"),
                    ("gaming", "Gaming gear"), ("cpus", "CPUs"),
                    ("gpus", "Graphics cards"), ("ram", "Memory"),
                    ("monitors", "Monitors"), ("pcs", "Gaming PCs"),
                    ("accessories", "Accessories"), ("other", "Other"),
                    ("motherboards", "Motherboards"), ("storage", "Storage"),
                    ("power", "Power supplies"), ("cooling", "Cooling"),
                    ("cases", "PC cases"),
                ], default="other", max_length=20,
            ),
        ),
    ]
