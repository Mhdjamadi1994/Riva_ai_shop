from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("products", "0005_alter_product_category")]

    operations = [
        migrations.AlterField(model_name="product", name="price", field=models.DecimalField(decimal_places=2, max_digits=12)),
        migrations.AlterField(model_name="orderitem", name="unit_price", field=models.DecimalField(decimal_places=2, max_digits=12)),
    ]
