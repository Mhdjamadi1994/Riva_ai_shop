from django.urls import path

from .views import ProductRecommendationAPIView, RecommendationInteractionAPIView

urlpatterns = [
    path("", ProductRecommendationAPIView.as_view(), name="product-recommendations"),
    path("events/", RecommendationInteractionAPIView.as_view(), name="recommendation-events"),
]
