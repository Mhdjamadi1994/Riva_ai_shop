import unicodedata
import re
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.templatetags.static import static
from django.utils import timezone
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from apps.products.models import InventoryMovement, Order, OrderItem, Product, ProductFavorite, ProductLike, ProductReview
from apps.products.serializers import ProductSerializer
from apps.core.models import CustomerProfile, CustomerSupportTicket, Payment, WalletTransaction


PRODUCT_CATEGORY_IMAGES = {
    "laptops": "laptops.jpg", "pcs": "pcs.jpg", "cpus": "cpus.jpg",
    "gpus": "gpus.jpg", "ram": "ram.jpg", "monitors": "monitors.jpg",
    "keyboards": "keyboards.jpg", "gaming": "gaming.jpg",
    "accessories": "accessories.jpg", "motherboards": "motherboards.jpg",
    "storage": "storage.jpg", "power": "power.jpg", "cooling": "cooling.jpg",
    "cases": "cases.jpg", "other": "other.jpg",
}


def product_category_image_url(category):
    image_name = PRODUCT_CATEGORY_IMAGES.get(category, "other.jpg")
    return static(f"storefront/images/products/{image_name}")


class CustomerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ("username", "email", "display_name", "phone", "address", "created_at", "updated_at")
        read_only_fields = ("username", "email", "created_at", "updated_at")

    def validate_phone(self, value):
        value = "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in unicodedata.normalize("NFKC", value)).strip()
        if not re.fullmatch(r"\+[1-9]\d{7,14}", value):
            raise serializers.ValidationError("Use the international format with a country calling code, without spaces.")
        return value


class StorefrontProductSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True)
    favorite_count = serializers.IntegerField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True, allow_null=True)
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "name", "description", "price", "category", "image_url", "is_available", "in_stock", "created_at", "like_count", "favorite_count", "review_count", "average_rating", "is_liked", "is_saved")

    def get_image_url(self, obj) -> str:
        return product_category_image_url(obj.category)

    def get_in_stock(self, obj) -> bool:
        return bool(obj.is_available and obj.stock is not None and obj.stock > 0)

    def get_is_liked(self, obj) -> bool:
        user = self.context["request"].user
        return bool(user.is_authenticated and ProductLike.objects.filter(user=user, product=obj).exists())

    def get_is_saved(self, obj) -> bool:
        user = self.context["request"].user
        return bool(user.is_authenticated and ProductFavorite.objects.filter(user=user, product=obj).exists())


class ProductReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ProductReview
        fields = ("id", "username", "rating", "body", "created_at", "updated_at")
        read_only_fields = ("id", "username", "created_at", "updated_at")

    def validate_body(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Write at least five characters so the review is useful.")
        return value


class CustomerSupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerSupportTicket
        fields = ("id", "subject", "message", "status", "staff_reply", "created_at", "updated_at")
        read_only_fields = ("id", "status", "staff_reply", "created_at", "updated_at")

    def validate_subject(self, value):
        value = " ".join(value.split())
        if len(value) < 4:
            raise serializers.ValidationError("Add a short subject with at least four characters.")
        return value

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Describe the issue in at least ten characters.")
        return value


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ("reference", "kind", "status", "amount", "currency", "description", "created_at")


class PaymentSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Payment
        fields = ("id", "order_id", "provider", "status", "amount", "currency", "provider_reference", "checkout_url", "created_at", "paid_at")


class ProductEngagementUpdateSerializer(serializers.Serializer):
    liked = serializers.BooleanField(required=False)
    saved = serializers.BooleanField(required=False)


class ProductEngagementResponseSerializer(serializers.Serializer):
    likes = serializers.IntegerField()
    saves = serializers.IntegerField()
    liked = serializers.BooleanField()
    saved = serializers.BooleanField()


class ProductReviewListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    average = serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True)
    results = ProductReviewSerializer(many=True)


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, max_length=128, write_only=True, trim_whitespace=False)
    phone = serializers.CharField(min_length=9, max_length=16)

    def validate_phone(self, value):
        value = "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in unicodedata.normalize("NFKC", value)).strip()
        if not re.fullmatch(r"\+[1-9]\d{7,14}", value):
            raise serializers.ValidationError("Use an international number, including the country calling code, without spaces.")
        return value

    def validate_username(self, value):
        value = value.strip()
        if get_user_model().objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_password(self, value):
        User = get_user_model()
        user = User(username=self.initial_data.get("username", ""), email=self.initial_data.get("email", ""))
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        phone = validated_data.pop("phone")
        user = get_user_model().objects.create_user(**validated_data)
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.phone = phone
        profile.save(update_fields=("phone", "updated_at"))
        return user


class PublicProductPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 48


class OrderLineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=20)
    recommendation_run_id = serializers.UUIDField(required=False, write_only=True)

    def validate(self, attrs):
        run_id = attrs.get("recommendation_run_id")
        if run_id:
            from apps.recommendation.models import RecommendationRun
            try:
                run = RecommendationRun.objects.get(pk=run_id)
            except RecommendationRun.DoesNotExist as exc:
                raise serializers.ValidationError({"recommendation_run_id": "Recommendation record was not found."}) from exc
            if attrs["product_id"] not in run.candidate_product_ids:
                raise serializers.ValidationError({"recommendation_run_id": "This product was not in that recommendation."})
            attrs["recommendation_run_object"] = run
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("product_id", "product_name", "unit_price", "quantity", "line_total", "order_status")


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "status", "full_name", "phone", "address", "total_amount", "quoted_total_usd", "fx_rate_toman_per_usd", "fx_rate_source", "fx_rate_observed_at", "items", "payments", "created_at", "updated_at")

    payments = PaymentSerializer(many=True, read_only=True)


class CustomerAccountSerializer(serializers.Serializer):
    profile = CustomerProfileSerializer()
    wallet = serializers.DictField()
    transactions = WalletTransactionSerializer(many=True)
    payments = PaymentSerializer(many=True)
    orders = OrderReadSerializer(many=True)
    liked_products = ProductSerializer(many=True)
    saved_products = ProductSerializer(many=True)
    support_tickets = CustomerSupportTicketSerializer(many=True)


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderLineInputSerializer(many=True, write_only=True, allow_empty=False)

    class Meta:
        model = Order
        fields = ("full_name", "phone", "address", "items")

    def validate_full_name(self, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("Enter the recipient’s full name.")
        return value

    def validate_phone(self, value):
        value = "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in unicodedata.normalize("NFKC", value)).strip()
        if not re.fullmatch(r"\+[1-9]\d{7,14}", value):
            raise serializers.ValidationError("Use the international format +countrycode followed by the number.")
        return value

    def validate_address(self, value):
        value = value.strip()
        if len(value) < 8:
            raise serializers.ValidationError("Enter a more complete address.")
        return value

    def validate_items(self, lines):
        product_ids = [line["product_id"] for line in lines]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Add each product only once.")
        return lines

    def create(self, validated_data):
        idempotency_key = validated_data.pop("idempotency_key")
        request_fingerprint = validated_data.pop("request_fingerprint")
        exchange_quote = validated_data.pop("exchange_quote")
        lines = validated_data.pop("items")
        product_ids = [line["product_id"] for line in lines]
        with transaction.atomic():
            products = {
                product.pk: product
                for product in Product.objects.select_for_update().filter(pk__in=product_ids, is_available=True).order_by("pk")
            }
            if len(products) != len(product_ids):
                raise serializers.ValidationError({"items": "One or more products are no longer available."})
            quantities = {line["product_id"]: line["quantity"] for line in lines}
            unavailable_stock = [
                products[product_id].name
                for product_id, quantity in quantities.items()
                if products[product_id].stock is None or products[product_id].stock < quantity
            ]
            if unavailable_stock:
                raise serializers.ValidationError({
                    "items": "Insufficient or untracked stock for: " + ", ".join(unavailable_stock)
                    + ". Contact support before placing this order."
                })
            total = sum((products[line["product_id"]].price * line["quantity"] for line in lines), Decimal("0.00"))
            usd_total = (total / exchange_quote.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if settings.PAYMENT_PROVIDER == "stripe" and usd_total < Decimal("0.50"):
                raise serializers.ValidationError({"items": "The order total is below the hosted payment provider minimum."})
            order = Order.objects.create(
                user=self.context["request"].user,
                status=Order.Status.AWAITING_PAYMENT,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                total_amount=total,
                quoted_total_usd=usd_total,
                fx_rate_toman_per_usd=exchange_quote.rate,
                fx_rate_source=exchange_quote.source,
                fx_rate_observed_at=exchange_quote.observed_at,
                reservation_expires_at=timezone.now() + timedelta(minutes=settings.PAYMENT_RESERVATION_MINUTES),
                **validated_data,
            )
            for line in lines:
                product = products[line["product_id"]]
                recommendation_run = line.get("recommendation_run_object")
                item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    recommendation_run=recommendation_run,
                    product_name=product.name,
                    unit_price=product.price,
                    quantity=line["quantity"],
                )
                product.stock -= line["quantity"]
                product.save(update_fields=["stock"])
                InventoryMovement.objects.create(
                    product=product, order=order, kind=InventoryMovement.Kind.SALE,
                    quantity=line["quantity"], reference=f"order:{order.pk}",
                    note="Stock reserved for a customer order.", created_by=order.user,
                )
            return order
