from rest_framework import serializers

from apps.products.serializers import ProductSerializer


class APIErrorSerializer(serializers.Serializer):
    error = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)
    message = serializers.CharField(required=False)
    query = serializers.CharField(required=False)


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=8000, trim_whitespace=False)
    conversation_id = serializers.IntegerField(required=False, min_value=1)


class ChatResponseSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField()
    reply = serializers.CharField()
    metadata = serializers.JSONField(required=False)


class TelegramUpdateSerializer(serializers.Serializer):
    update_id = serializers.IntegerField(required=False)
    message = serializers.JSONField(required=False)
    edited_message = serializers.JSONField(required=False)


class TelegramWebhookResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


class RecommendationRequestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=1000)


class RecommendationProductSerializer(ProductSerializer):
    recommendation_reason = serializers.CharField(read_only=True)

    class Meta(ProductSerializer.Meta):
        fields = "__all__"


class RecommendationResponseSerializer(serializers.Serializer):
    results = RecommendationProductSerializer(many=True)
