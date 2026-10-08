import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("products", "0006_expand_product_and_order_prices"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="ProductFavorite",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorites", to="products.product")), ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_favorites", to=settings.AUTH_USER_MODEL))],
            options={"ordering": ["-created_at"], "constraints": [models.UniqueConstraint(fields=("user", "product"), name="unique_product_favorite_per_user")]},
        ),
        migrations.CreateModel(
            name="ProductLike",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="likes", to="products.product")), ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_likes", to=settings.AUTH_USER_MODEL))],
            options={"ordering": ["-created_at"], "constraints": [models.UniqueConstraint(fields=("user", "product"), name="unique_product_like_per_user")]},
        ),
        migrations.CreateModel(
            name="ProductReview",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("rating", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])), ("body", models.TextField(max_length=2000)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="products.product")), ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_reviews", to=settings.AUTH_USER_MODEL))],
            options={"ordering": ["-created_at"], "constraints": [models.UniqueConstraint(fields=("user", "product"), name="one_review_per_user_per_product")]},
        ),
    ]
