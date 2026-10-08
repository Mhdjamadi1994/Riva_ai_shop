from django.urls import path

from .views import ProductDetailPageView, StorefrontHomeView, SupportCenterView, mock_payment_checkout

urlpatterns = [
    path("", StorefrontHomeView.as_view(), name="storefront-home"),
    path("account/", StorefrontHomeView.as_view(), name="storefront-account"),
    path("cart/", StorefrontHomeView.as_view(), name="storefront-cart"),
    path("support/", SupportCenterView.as_view(), name="support-center"),
    path("payments/mock/<uuid:checkout_token>/", mock_payment_checkout, name="mock-payment-checkout"),
    path("products/<int:pk>/", ProductDetailPageView.as_view(), name="product-detail"),
]
