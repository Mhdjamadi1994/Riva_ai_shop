from django.urls import path

from .views import (
    CustomerAccountAPIView,
    CustomerProfileAPIView,
    CustomerSupportTicketAPIView,
    ProductEngagementAPIView,
    ProductReviewAPIView,
    OrderListCreateAPIView,
    PaymentWebhookAPIView,
    PublicProductListAPIView,
    PublicExchangeRateAPIView,
    RegistrationAPIView,
)

urlpatterns = [
    path("products/", PublicProductListAPIView.as_view(), name="public-products"),
    path("exchange-rate/", PublicExchangeRateAPIView.as_view(), name="exchange-rate"),
    path("products/<int:pk>/engagement/", ProductEngagementAPIView.as_view(), name="product-engagement"),
    path("products/<int:pk>/reviews/", ProductReviewAPIView.as_view(), name="product-reviews"),
    path("register/", RegistrationAPIView.as_view(), name="register"),
    path("account/", CustomerAccountAPIView.as_view(), name="account"),
    path("account/profile/", CustomerProfileAPIView.as_view(), name="account-profile"),
    path("account/tickets/", CustomerSupportTicketAPIView.as_view(), name="account-tickets"),
    path("orders/", OrderListCreateAPIView.as_view(), name="orders"),
    path("payments/webhook/", PaymentWebhookAPIView.as_view(), name="payment-webhook"),
]
