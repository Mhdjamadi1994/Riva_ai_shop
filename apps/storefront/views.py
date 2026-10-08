from django.conf import settings
import logging
import re
from datetime import timedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import Http404
from django.views.generic import DetailView, TemplateView
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg, Count
from django.db import IntegrityError, transaction
from rest_framework import filters, generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from apps.chatbot.api_serializers import APIErrorSerializer

from apps.products.models import Order, Product, ProductFavorite, ProductLike, ProductReview
from apps.products.serializers import ProductSerializer
from apps.core.models import CustomerProfile, CustomerSupportTicket, Payment, Wallet
from apps.core.pricing import ExchangeRateUnavailable, get_usd_toman_quote
from apps.core.payments import (
    PaymentGatewayError,
    complete_payment,
    create_checkout_session,
    process_stripe_event,
    verify_stripe_signature,
)

from .serializers import (
    OrderCreateSerializer,
    OrderReadSerializer,
    PublicProductPagination,
    RegistrationSerializer,
    CustomerProfileSerializer,
    PaymentSerializer,
    WalletTransactionSerializer,
    ProductReviewSerializer,
    StorefrontProductSerializer,
    CustomerSupportTicketSerializer,
    CustomerAccountSerializer,
    ProductEngagementResponseSerializer,
    ProductEngagementUpdateSerializer,
    ProductReviewListResponseSerializer,
    ProductReviewSerializer as StorefrontReviewSerializer,
    product_category_image_url,
)

logger = logging.getLogger(__name__)


def telegram_support_context():
    username = settings.TELEGRAM_BOT_USERNAME
    configured = bool(
        re.fullmatch(r"[A-Za-z0-9_]{5,32}", username)
        and settings.TELEGRAM_BOT_TOKEN
        and settings.TELEGRAM_WEBHOOK_SECRET
    )
    return {
        "telegram_available": configured,
        "telegram_url": f"https://t.me/{username}" if configured else "",
    }


class PublicProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(method="filter_categories")
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    min_rating = django_filters.NumberFilter(field_name="average_rating", lookup_expr="gte")

    class Meta:
        model = Product
        fields = ["category"]

    def filter_categories(self, queryset, name, value):
        categories = [item.strip() for item in value.split(",") if item.strip()]
        valid = {choice for choice, _label in Product.Category.choices}
        if not categories or any(category not in valid for category in categories):
            return queryset.none()
        return queryset.filter(category__in=categories)


class StorefrontHomeView(TemplateView):
    template_name = "storefront/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quote = get_usd_toman_quote()
        context["shop_currency"] = settings.SHOP_CURRENCY
        context["toman_per_usd"] = quote.rate
        context["fx_source"] = quote.source
        context["fx_observed_at"] = quote.observed_at
        context["fx_stale"] = quote.stale
        context["fx_configured"] = quote.configured
        context["open_account"] = self.request.path == "/account/"
        context["open_cart"] = self.request.path == "/cart/"
        context["account_section"] = self.request.GET.get("section", "profile")
        context.update(telegram_support_context())
        return context


class SupportCenterView(TemplateView):
    template_name = "storefront/support_center.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["shop_currency"] = settings.SHOP_CURRENCY
        context["toman_per_usd"] = get_usd_toman_quote().rate
        context.update(telegram_support_context())
        return context


class ProductDetailPageView(DetailView):
    template_name = "storefront/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.filter(is_available=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        context["shop_currency"] = settings.SHOP_CURRENCY
        context["toman_per_usd"] = get_usd_toman_quote().rate
        context["product_price_usd"] = product.price / context["toman_per_usd"]
        context["product_in_stock"] = bool(product.is_available and product.stock is not None and product.stock > 0)
        context["product_image_url"] = product_category_image_url(product.category)
        context["review_count"] = product.reviews.count()
        context["average_rating"] = product.reviews.aggregate(value=Avg("rating"))["value"]
        context.update(telegram_support_context())
        return context


class PublicProductListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "storefront"
    serializer_class = StorefrontProductSerializer
    pagination_class = PublicProductPagination
    queryset = Product.objects.filter(is_available=True).annotate(
        like_count=Count("likes", distinct=True),
        favorite_count=Count("favorites", distinct=True),
        review_count=Count("reviews", distinct=True),
        average_rating=Avg("reviews__rating"),
    )
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PublicProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at", "name", "average_rating"]
    ordering = ["-created_at"]


class PublicExchangeRateAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        quote = get_usd_toman_quote()
        return Response({
            "base_currency": "USD",
            "quote_currency": "TOMAN",
            "rate": str(quote.rate),
            "source": quote.source,
            "observed_at": quote.observed_at,
            "stale": quote.stale,
            "configured_for_checkout": quote.configured and not quote.stale,
        })


class RegistrationAPIView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration"
    serializer_class = RegistrationSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"id": user.pk, "username": user.get_username()}, status=status.HTTP_201_CREATED)


class CustomerProfileAPIView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CustomerProfileSerializer

    def get_object(self):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        return profile


class CustomerAccountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CustomerAccountSerializer})
    def get(self, request):
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        wallet, _ = Wallet.objects.get_or_create(user=request.user, defaults={"currency": "USDT"})
        orders = (
            Order.objects.filter(user=request.user)
            .prefetch_related("items", "payments")[:50]
        )
        payments = Payment.objects.filter(user=request.user).order_by("-created_at")[:50]
        transactions = wallet.transactions.order_by("-created_at")[:50]
        return Response({
            "profile": CustomerProfileSerializer(profile, context={"request": request}).data,
            "wallet": {"balance": wallet.balance, "currency": wallet.currency},
            "transactions": WalletTransactionSerializer(transactions, many=True).data,
            "payments": PaymentSerializer(payments, many=True).data,
            "orders": OrderReadSerializer(orders, many=True).data,
            "liked_products": ProductSerializer(Product.objects.filter(likes__user=request.user, is_available=True), many=True).data,
            "saved_products": ProductSerializer(Product.objects.filter(favorites__user=request.user, is_available=True), many=True).data,
            "support_tickets": CustomerSupportTicketSerializer(
                CustomerSupportTicket.objects.filter(user=request.user), many=True
            ).data,
        })


class CustomerSupportTicketAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CustomerSupportTicketSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CustomerSupportTicket.objects.none()
        return CustomerSupportTicket.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        ticket = serializer.save(user=self.request.user)

        def enqueue_support_draft():
            from apps.agents.services import SupportDraftAgent
            from apps.agents.tasks import process_support_ticket

            try:
                process_support_ticket.delay(ticket.pk)
            except Exception:
                logger.exception("Could not enqueue support draft for ticket %s", ticket.pk)
                SupportDraftAgent().process(ticket.pk)

        transaction.on_commit(enqueue_support_draft)


class ProductEngagementAPIView(APIView):
    permission_classes = [AllowAny]

    def get_product(self, pk):
        return get_object_or_404(Product, pk=pk, is_available=True)

    @extend_schema(responses={200: ProductEngagementResponseSerializer})
    def get(self, request, pk):
        product = self.get_product(pk)
        user = request.user
        return Response({
            "likes": product.likes.count(),
            "saves": product.favorites.count(),
            "liked": bool(user.is_authenticated and product.likes.filter(user=user).exists()),
            "saved": bool(user.is_authenticated and product.favorites.filter(user=user).exists()),
        })

    @extend_schema(
        request=ProductEngagementUpdateSerializer,
        responses={200: ProductEngagementResponseSerializer, 400: APIErrorSerializer, 401: APIErrorSerializer},
    )
    def patch(self, request, pk):
        if not request.user.is_authenticated:
            return Response({"detail": "Sign in to like or save products."}, status=status.HTTP_401_UNAUTHORIZED)
        product = self.get_product(pk)
        changes = {}
        for field, model in (("liked", ProductLike), ("saved", ProductFavorite)):
            if field in request.data:
                value = request.data[field]
                if not isinstance(value, bool):
                    return Response({field: "Expected true or false."}, status=status.HTTP_400_BAD_REQUEST)
                if value:
                    model.objects.get_or_create(user=request.user, product=product)
                else:
                    model.objects.filter(user=request.user, product=product).delete()
                changes[field] = value
        return self.get(request, pk)


class ProductReviewAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: ProductReviewListResponseSerializer})
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, is_available=True)
        reviews = product.reviews.select_related("user")[:100]
        return Response({
            "count": product.reviews.count(),
            "average": product.reviews.aggregate(value=Avg("rating"))["value"],
            "results": ProductReviewSerializer(reviews, many=True).data,
        })

    @extend_schema(
        request=StorefrontReviewSerializer,
        responses={200: StorefrontReviewSerializer, 400: APIErrorSerializer, 401: APIErrorSerializer},
    )
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return Response({"detail": "Sign in to leave a review."}, status=status.HTTP_401_UNAUTHORIZED)
        product = get_object_or_404(Product, pk=pk, is_available=True)
        serializer = ProductReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review, _ = ProductReview.objects.update_or_create(
            user=request.user, product=product,
            defaults=serializer.validated_data,
        )
        return Response(ProductReviewSerializer(review).data, status=status.HTTP_200_OK)


class OrderListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        queryset = Order.objects.prefetch_related("items", "payments")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        return OrderCreateSerializer if self.request.method == "POST" else OrderReadSerializer

    def create(self, request, *args, **kwargs):
        from decimal import Decimal
        import hashlib
        import json
        import uuid

        mock_enabled = settings.ALLOW_MOCK_PAYMENTS and (settings.DEBUG or settings.DEMO_MODE)
        if settings.PAYMENT_PROVIDER not in {"mock", "stripe"} or (settings.PAYMENT_PROVIDER == "mock" and not mock_enabled):
            return Response({"detail": "Hosted checkout is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if settings.PAYMENT_PROVIDER == "stripe" and (
            not settings.STRIPE_SECRET_KEY or not settings.PAYMENT_WEBHOOK_SECRET
            or not settings.PUBLIC_SITE_URL.startswith("https://")
        ):
            return Response({"detail": "Stripe credentials, webhook secret, and HTTPS PUBLIC_SITE_URL are required."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_header = request.headers.get("Idempotency-Key", "")
        try:
            idempotency_key = uuid.UUID(idempotency_header)
        except (ValueError, TypeError, AttributeError):
            return Response({"detail": "A valid UUID Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        validated = serializer.validated_data
        fingerprint_payload = {
            "user_id": request.user.pk,
            "full_name": validated["full_name"],
            "phone": validated["phone"],
            "address": validated["address"],
            "items": sorted([
                (line["product_id"], line["quantity"], str(line.get("recommendation_run_id", "")))
                for line in validated["items"]
            ]),
        }
        request_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        def response_for(order, response_status=status.HTTP_200_OK):
            payment = order.payments.order_by("-created_at").first()
            checkout_url = payment.checkout_url if payment else ""
            if payment and payment.status == Payment.Status.PAID:
                checkout_url = f"/account/?section=orders&order_id={order.pk}&payment=complete"
            return Response({
                **OrderReadSerializer(order).data,
                "payment": PaymentSerializer(payment).data if payment else None,
                "checkout_url": checkout_url,
                "idempotent_replay": response_status == status.HTTP_200_OK,
                "checkout_in_progress": response_status == status.HTTP_202_ACCEPTED,
            }, status=response_status)

        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.user_id != request.user.pk or existing.request_fingerprint != request_fingerprint:
                return Response({"detail": "This Idempotency-Key is already associated with a different request."}, status=status.HTTP_409_CONFLICT)
            payment = existing.payments.order_by("-created_at").first()
            if payment and payment.checkout_url:
                return response_for(existing)
            if existing.status != Order.Status.AWAITING_PAYMENT or (
                existing.reservation_expires_at and existing.reservation_expires_at <= timezone.now()
            ):
                return Response({"detail": "This order's payment window has expired. Start a new checkout."}, status=status.HTTP_409_CONFLICT)
            order = existing
        else:
            try:
                quote = get_usd_toman_quote(require_fresh=True)
            except ExchangeRateUnavailable as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            try:
                order = serializer.save(
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_fingerprint,
                    exchange_quote=quote,
                )
            except (IntegrityError, ValidationError):
                existing = Order.objects.filter(idempotency_key=idempotency_key).first()
                if not existing:
                    raise
                if existing.user_id != request.user.pk or existing.request_fingerprint != request_fingerprint:
                    return Response({"detail": "This Idempotency-Key is already associated with a different request."}, status=status.HTTP_409_CONFLICT)
                order = existing

        if order.status != Order.Status.AWAITING_PAYMENT:
            return Response({**OrderReadSerializer(order).data, "checkout_url": "", "idempotent_replay": True})

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if order.status != Order.Status.AWAITING_PAYMENT:
                return Response({**OrderReadSerializer(order).data, "checkout_url": "", "idempotent_replay": True})
            if order.reservation_expires_at and order.reservation_expires_at <= timezone.now():
                return Response({"detail": "This order's payment window has expired. Start a new checkout."}, status=status.HTTP_409_CONFLICT)
            payment = order.payments.select_for_update().order_by("-created_at").first()
            if payment and payment.checkout_url:
                return response_for(order)
            if payment and payment.checkout_started_at and payment.checkout_started_at > timezone.now() - timedelta(minutes=2):
                return response_for(order, status.HTTP_202_ACCEPTED)
            amount_usd = order.quoted_total_usd
            if not amount_usd or amount_usd <= Decimal("0"):
                return Response({"detail": "The quoted payment amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)
            if payment:
                # Reuse the payment ID and stable Stripe idempotency parameters after stale/failed attempts.
                payment.status = Payment.Status.CREATED
                payment.provider_reference = None
                payment.checkout_url = ""
                payment.checkout_started_at = timezone.now()
                payment.save(update_fields=("status", "provider_reference", "checkout_url", "checkout_started_at", "updated_at"))
            else:
                payment = Payment.objects.create(
                    user=request.user,
                    order=order,
                    provider=Payment.Provider.CARD,
                    status=Payment.Status.CREATED,
                    amount=amount_usd,
                    currency="USD",
                    checkout_token=uuid.uuid4(),
                    checkout_started_at=timezone.now(),
                )
        try:
            create_checkout_session(payment, request=request)
        except PaymentGatewayError as exc:
            payment.status = Payment.Status.FAILED
            payment.checkout_started_at = None
            payment.save(update_fields=("status", "checkout_started_at", "updated_at"))
            logger.warning("Checkout session creation failed for payment %s: %s", payment.pk, exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        from apps.core.tasks import expire_stale_order_payments
        try:
            expire_stale_order_payments.apply_async(countdown=settings.PAYMENT_RESERVATION_MINUTES * 60)
        except Exception:
            logger.warning("Could not enqueue order payment expiry sweep; the periodic expiry task will recover it.")
        return response_for(order, status.HTTP_201_CREATED)


class PaymentWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(request=OpenApiTypes.BINARY, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        if settings.PAYMENT_PROVIDER != "stripe":
            return Response({"detail": "Stripe webhook is not enabled."}, status=status.HTTP_404_NOT_FOUND)
        if not verify_stripe_signature(
            request.body,
            request.headers.get("Stripe-Signature", ""),
        ):
            return Response({"detail": "Invalid payment webhook signature."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            process_stripe_event(request.body)
        except PaymentGatewayError as exc:
            logger.warning("Rejected Stripe webhook: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Stripe webhook processing failed")
            return Response({"detail": "Webhook processing failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"received": True}, status=status.HTTP_200_OK)


def mock_payment_checkout(request, checkout_token):
    if settings.PAYMENT_PROVIDER != "mock" or not settings.ALLOW_MOCK_PAYMENTS or not (settings.DEBUG or settings.DEMO_MODE):
        raise Http404
    payment = get_object_or_404(
        Payment.objects.select_related("order"), checkout_token=checkout_token,
        provider=Payment.Provider.CARD,
    )
    if request.method == "POST":
        try:
            complete_payment(payment.pk)
        except PaymentGatewayError:
            return render(request, "storefront/mock_payment.html", {"payment": payment, "error": "This payment is no longer available."}, status=409)
        return redirect(f"/account/?section=orders&payment=complete&order_id={payment.order_id}")
    return render(request, "storefront/mock_payment.html", {"payment": payment})
