from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
import uuid


class Product(models.Model):
    class Category(models.TextChoices):
        LAPTOPS = "laptops", "Laptops"
        KEYBOARDS = "keyboards", "Keyboards"
        GAMING = "gaming", "Gaming gear"
        CPUS = "cpus", "CPUs"
        GPUS = "gpus", "Graphics cards"
        RAM = "ram", "Memory"
        MONITORS = "monitors", "Monitors"
        PCS = "pcs", "Gaming PCs"
        ACCESSORIES = "accessories", "Accessories"
        OTHER = "other", "Other"
        MOTHERBOARDS = "motherboards", "Motherboards"
        STORAGE = "storage", "Storage"
        POWER_SUPPLIES = "power", "Power supplies"
        COOLING = "cooling", "Cooling"
        CASES = "cases", "PC cases"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    is_available = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class InventoryMovement(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "receipt", "Inbound receipt"
        ISSUE = "issue", "Manual outbound"
        SALE = "sale", "Order reservation"
        RETURN = "return", "Returned to stock"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="inventory_movements")
    order = models.ForeignKey("Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_movements")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reference = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.product} × {self.quantity}"


class Order(models.Model):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shop_orders")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32)
    address = models.TextField(max_length=1200)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    idempotency_key = models.UUIDField(null=True, blank=True, unique=True)
    request_fingerprint = models.CharField(max_length=64, blank=True)
    fx_rate_toman_per_usd = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    fx_rate_source = models.CharField(max_length=100, blank=True)
    fx_rate_observed_at = models.DateTimeField(null=True, blank=True)
    quoted_total_usd = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.pk} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="order_items")
    recommendation_run = models.ForeignKey("recommendation.RecommendationRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="order_items")
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["pk"]

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class ProductLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_likes")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "product"), name="unique_product_like_per_user")]
        ordering = ["-created_at"]


class ProductFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_favorites")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="favorites")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "product"), name="unique_product_favorite_per_user")]
        ordering = ["-created_at"]


class ProductReview(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_reviews")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "product"), name="one_review_per_user_per_product")]
        ordering = ["-created_at"]
