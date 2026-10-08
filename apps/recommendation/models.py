import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class RecommendationRun(models.Model):
    class SearchMode(models.TextChoices):
        KEYWORD = "keyword", "Keyword fallback"
        VECTOR = "vector", "Vector search"
        CATEGORY = "category", "Category match"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="recommendation_runs")
    query_sha256 = models.CharField(max_length=64, db_index=True)
    requested_categories = models.JSONField(default=list, blank=True)
    budget_usd = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    candidate_product_ids = models.JSONField(default=list, blank=True)
    candidate_count = models.PositiveSmallIntegerField(default=0)
    matched_product_count = models.PositiveIntegerField(default=0)
    in_stock_count = models.PositiveIntegerField(default=0)
    within_budget_count = models.PositiveIntegerField(null=True, blank=True)
    empty_result = models.BooleanField(default=False)
    empty_reason = models.CharField(max_length=16, blank=True)
    search_mode = models.CharField(max_length=12, choices=SearchMode.choices)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("-created_at", "search_mode"))]

    def __str__(self):
        return f"Recommendation {self.pk} ({self.candidate_count} candidates)"


class RecommendationInteraction(models.Model):
    class Kind(models.TextChoices):
        CLICK = "click", "Product click"
        PURCHASE = "purchase", "Paid order"
        IRRELEVANT = "irrelevant", "Marked as irrelevant"

    recommendation_run = models.ForeignKey(RecommendationRun, on_delete=models.CASCADE, related_name="interactions")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="recommendation_interactions")
    order_item = models.OneToOneField("products.OrderItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="recommendation_interaction")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("recommendation_run", "kind", "created_at"))]
        constraints = [models.UniqueConstraint(
            fields=("recommendation_run", "product"), condition=Q(kind="irrelevant"),
            name="unique_irrelevant_feedback_per_product_run",
        )]

    def __str__(self):
        return f"{self.kind}: recommendation {self.recommendation_run_id}, product {self.product_id}"
