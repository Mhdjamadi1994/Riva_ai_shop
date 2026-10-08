from django.contrib import admin
from django.db.models import Count, Q

from .models import RecommendationInteraction, RecommendationRun


@admin.register(RecommendationInteraction)
class RecommendationInteractionAdmin(admin.ModelAdmin):
    list_display = ("kind", "recommendation_run", "product", "user", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("recommendation_run__query_sha256", "product__name", "user__username")
    readonly_fields = tuple(field.name for field in RecommendationInteraction._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RecommendationRun)
class RecommendationRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "search_mode", "candidate_count", "matched_product_count", "in_stock_count", "within_budget_count", "clicks", "purchases", "irrelevant_feedback", "empty_result", "empty_reason", "duration_ms")
    list_filter = ("search_mode", "empty_result", "empty_reason", "created_at")
    search_fields = ("query_sha256", "user__username")
    readonly_fields = tuple(field.name for field in RecommendationRun._meta.fields)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            click_total=Count("interactions", filter=Q(interactions__kind="click")),
            purchase_total=Count("interactions", filter=Q(interactions__kind="purchase")),
            irrelevant_total=Count("interactions", filter=Q(interactions__kind="irrelevant")),
        )

    @admin.display(description="Clicks", ordering="click_total")
    def clicks(self, obj):
        return obj.click_total

    @admin.display(description="Paid orders", ordering="purchase_total")
    def purchases(self, obj):
        return obj.purchase_total

    @admin.display(description="Irrelevant flags", ordering="irrelevant_total")
    def irrelevant_feedback(self, obj):
        return obj.irrelevant_total

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
