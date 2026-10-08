import re
import time
from decimal import Decimal, ROUND_DOWN

from django.conf import settings
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.chatbot.models import SecurityEvent
from apps.chatbot.security import PromptInjectionDetected, fingerprint, normalize_input
from apps.chatbot.vector_store import search_products
from apps.products.models import Product
from apps.core.pricing import ExchangeRateUnavailable, get_usd_toman_quote
from .models import RecommendationInteraction, RecommendationRun
from apps.chatbot.api_serializers import (
    APIErrorSerializer,
    RecommendationProductSerializer,
    RecommendationRequestSerializer,
    RecommendationResponseSerializer,
)


CATEGORY_HINTS = {
    "pcs": (
        r"\b(?:gaming\s+(?:pc|computer)|desktop(?:\s+(?:pc|computer))?|computer\s+build|pc\s+build|gaming\s+system)\b",
        r"\bpc\b(?!\s+(?:case|chassis))",
    ),
    "laptops": (r"\b(?:laptops?|notebooks?)\b",),
    "gpus": (r"\b(?:gpus?|graphics?\s+cards?|video\s+cards?|rtx|gtx|radeon)\b",),
    "cpus": (r"\b(?:cpus?|processors?)\b",),
    "monitors": (r"\b(?:monitors?|displays?|screens?)\b",),
    "keyboards": (r"\bkeyboards?\b",),
    "gaming": (r"\b(?:headsets?|gaming\s+mice|gaming\s+mouse|controllers?|gaming\s+gear)\b",),
    "motherboards": (r"\b(?:motherboards?|mainboards?)\b",),
    "ram": (r"\b(?:ram|memory)\b",),
    "storage": (r"\b(?:ssds?|nvme|storage)\b",),
    "power": (r"\b(?:power\s+suppl(?:y|ies)|psu)\b",),
    "cooling": (r"\b(?:coolers?|cooling)\b",),
    "cases": (r"\b(?:pc\s+cases?|computer\s+cases?|chassis|cases?)\b",),
}

STOP_WORDS = {
    "a", "an", "and", "are", "best", "for", "get", "help", "i", "in", "is",
    "looking", "me", "my", "of", "please", "recommend", "riva", "some", "the",
    "to", "want", "what", "with",
}


class ProductRecommendationAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "llm"

    @extend_schema(
        request=RecommendationRequestSerializer,
        responses={200: RecommendationResponseSerializer, 400: APIErrorSerializer},
    )
    def post(self, request):
        started = time.monotonic()
        query_text = request.data.get("query")
        if not isinstance(query_text, str):
            return Response({"query": "Provide a query of 1 to 1000 characters."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            query_text = normalize_input(query_text)
        except PromptInjectionDetected as exc:
            SecurityEvent.objects.create(
                user=request.user,
                source=SecurityEvent.Source.API,
                rule=exc.rule,
                content_sha256=fingerprint(query_text),
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"query": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if len(query_text) > 1000:
            return Response({"query": "Provide a query of 1 to 1000 characters."}, status=status.HTTP_400_BAD_REQUEST)

        categories = self._requested_categories(query_text)
        budget_match = re.search(
            r"(?:\$\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:usd|dollars?|\$))",
            query_text,
            flags=re.IGNORECASE,
        )
        budget_usd = None
        budget_toman = None
        if budget_match:
            budget_usd = Decimal(next(part for part in budget_match.groups() if part).replace(",", ""))
            try:
                budget_toman = budget_usd * get_usd_toman_quote(require_fresh=not settings.DEBUG).rate
            except ExchangeRateUnavailable as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        search_mode = RecommendationRun.SearchMode.CATEGORY if categories else RecommendationRun.SearchMode.KEYWORD
        if categories:
            candidates = list(Product.objects.filter(is_available=True, category__in=categories).order_by("pk")[:100])
        elif settings.SEMANTIC_SEARCH_ENABLED:
            try:
                payloads = search_products(query_text.strip(), limit=30)
                ids = list(dict.fromkeys(item.get("product_id") for item in payloads if item.get("product_id")))
                products = {p.pk: p for p in Product.objects.filter(pk__in=ids, is_available=True)}
                candidates = [products[pk] for pk in ids if pk in products]
                if candidates:
                    search_mode = RecommendationRun.SearchMode.VECTOR
                else:
                    candidates = self._keyword_search(query_text)
            except Exception:
                candidates = self._keyword_search(query_text)
        else:
            candidates = self._keyword_search(query_text)
        in_stock_candidates = [product for product in candidates if product.stock is not None and product.stock > 0]
        within_budget_candidates = (
            [product for product in in_stock_candidates if product.price <= budget_toman]
            if budget_toman is not None else in_stock_candidates
        )
        ordered = within_budget_candidates
        ordered = self._rank_products(query_text, ordered, categories)[:8]
        results = RecommendationProductSerializer(ordered, many=True).data
        category_labels = dict(Product.Category.choices)
        for result in results:
            if result["category"] in categories:
                label = category_labels.get(result["category"], result["category"])
                result["recommendation_reason"] = f"Selected from the {label} category you asked for."
            else:
                result["recommendation_reason"] = "Matches details from your request."
        run = RecommendationRun.objects.create(
            user=request.user if request.user.is_authenticated else None,
            query_sha256=fingerprint(query_text),
            requested_categories=categories,
            budget_usd=budget_usd,
            candidate_product_ids=[item["id"] for item in results],
            candidate_count=len(results),
            matched_product_count=len(candidates),
            in_stock_count=len(in_stock_candidates),
            within_budget_count=len(within_budget_candidates) if budget_toman is not None else None,
            empty_result=not results,
            empty_reason=(
                "no_match" if not candidates else
                "out_of_stock" if not in_stock_candidates else
                "over_budget" if budget_toman is not None and not within_budget_candidates else ""
            ),
            search_mode=search_mode,
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
        for item in results:
            item["recommendation_run_id"] = str(run.pk)
        return Response({"query_id": str(run.pk), "results": results})

    @staticmethod
    def _requested_categories(query_text):
        query = query_text.casefold()
        return [
            category
            for category, patterns in CATEGORY_HINTS.items()
            if any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in patterns)
        ]

    @staticmethod
    def _rank_products(query_text, products, categories=()):
        terms = [
            term for term in re.findall(r"[\w-]{2,}", query_text.casefold())
            if term not in STOP_WORDS
        ][:12]
        category_set = set(categories)

        def score(product):
            name = product.name.casefold()
            description = product.description.casefold()
            value = 100 if product.category in category_set else 0
            value += sum(8 for term in terms if term in name)
            value += sum(2 for term in terms if term in description and term not in name)
            value += 1 if product.stock and product.stock > 0 else 0
            return value

        return sorted(products, key=score, reverse=True)

    @staticmethod
    def _keyword_search(query_text):
        terms = [
            term for term in re.findall(r"[\w-]{2,}", query_text.casefold())
            if term not in STOP_WORDS
        ][:12]
        query = Q()
        for term in terms:
            query |= Q(name__icontains=term) | Q(description__icontains=term)
        return list(
            Product.objects.filter(is_available=True).filter(query).distinct()[:40]
        ) if terms else []


class RecommendationInteractionSerializer(serializers.Serializer):
    query_id = serializers.UUIDField()
    product_id = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(
        choices=(RecommendationInteraction.Kind.CLICK, RecommendationInteraction.Kind.IRRELEVANT),
        default=RecommendationInteraction.Kind.CLICK,
    )


class RecommendationInteractionAPIView(APIView):
    serializer_class = RecommendationInteractionSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "storefront"

    def post(self, request):
        serializer = RecommendationInteractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run = RecommendationRun.objects.get(pk=serializer.validated_data["query_id"])
            product = Product.objects.get(pk=serializer.validated_data["product_id"], is_available=True)
        except (RecommendationRun.DoesNotExist, Product.DoesNotExist):
            return Response({"detail": "Recommendation or product was not found."}, status=status.HTTP_404_NOT_FOUND)
        if run.user_id and run.user_id != (request.user.pk if request.user.is_authenticated else None):
            return Response({"detail": "Recommendation or product was not found."}, status=status.HTTP_404_NOT_FOUND)
        if product.pk not in run.candidate_product_ids:
            return Response({"detail": "The product was not included in that recommendation."}, status=status.HTTP_400_BAD_REQUEST)
        kind = serializer.validated_data["kind"]
        event, created = RecommendationInteraction.objects.get_or_create(
            recommendation_run=run,
            product=product,
            kind=kind,
            user=request.user if request.user.is_authenticated else None,
        ) if kind == RecommendationInteraction.Kind.IRRELEVANT else (
            RecommendationInteraction.objects.create(
                recommendation_run=run, product=product,
                user=request.user if request.user.is_authenticated else None, kind=kind,
            ), True
        )
        return Response({"recorded": True, "kind": kind, "already_recorded": not created}, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)
