from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ("stock",)

    def get_in_stock(self, product) -> bool:
        return product.stock is not None and product.stock > 0

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

    def validate_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters.")
        return self._validate_catalog_text(value.strip())

    def validate_description(self, value):
        return self._validate_catalog_text(value)

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", ""))
        description = attrs.get("description", getattr(self.instance, "description", ""))
        self._validate_catalog_text(f"{name}\n{description}")
        return attrs

    @staticmethod
    def _validate_catalog_text(value):
        from apps.chatbot.security import PromptInjectionDetected, normalize_input

        try:
            return normalize_input(value) if value else value
        except (PromptInjectionDetected, ValueError) as exc:
            raise serializers.ValidationError("Catalog text contains blocked instructions or is too long.") from exc
