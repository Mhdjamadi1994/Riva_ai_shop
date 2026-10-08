from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.throttling import ScopedRateThrottle
from apps.storefront.views import RegistrationAPIView


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"


urlpatterns = [
    path("", include("apps.storefront.urls")),
    path("api/storefront/", include("apps.storefront.api_urls")),
    path("api/register/", RegistrationAPIView.as_view(), name="register"),

    path("admin/", admin.site.urls),

    path("api/health/", include("apps.core.urls")),
    path("api/products/", include("apps.products.urls")),
    path("api/chat/", include("apps.chatbot.urls")),
    path("api/recommendations/", include("apps.recommendation.urls")),
    path("api/admin/reports/", include("apps.agents.urls")),

    path("api/token/",ThrottledTokenObtainPairView.as_view(),name="token_obtain_pair",),
    path( "api/token/refresh/",ThrottledTokenRefreshView.as_view(),name="token_refresh",),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/",SpectacularSwaggerView.as_view(url_name="schema"),name="swagger-ui",),
    path("api/redoc/",SpectacularRedocView.as_view(url_name="schema"),name="redoc",),
]
