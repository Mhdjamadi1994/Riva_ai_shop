import logging

from django.conf import settings
from qdrant_client import QdrantClient, models

from .llm import embed_text
from .security import normalize_input

logger = logging.getLogger(__name__)


def _client() -> QdrantClient:
    return QdrantClient(
        url=settings.QDRANT_URL,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def _ensure_collection(client: QdrantClient) -> None:
    name = settings.QDRANT_COLLECTION
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )


def index_product(product) -> None:
    if not settings.SEMANTIC_SEARCH_ENABLED:
        raise RuntimeError("Semantic indexing requires an embedding model, provider URL, and API key.")
    raw_text = f"{product.name}\n{product.description or ''}"
    clean_text = normalize_input(raw_text)

    vector = embed_text(clean_text)
    client = _client()
    _ensure_collection(client)

    payload = {
        "product_id": product.pk,
        "name": product.name,
        "category": product.category,
        "price": float(product.price),
        "is_available": product.is_available,
        "description": product.description or "",
    }

    client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=[
            models.PointStruct(
                id=product.pk,
                vector=vector,
                payload=payload,
            )
        ],
    )

    logger.info(
        "Indexed product pk=%s to Qdrant collection=%s",
        product.pk,
        settings.QDRANT_COLLECTION,
    )


def search_products(
    query: str,
    limit: int = 5,
    only_available: bool = False,
) -> list[dict]:
    if not settings.SEMANTIC_SEARCH_ENABLED:
        raise RuntimeError("Semantic search requires an embedding model, provider URL, and API key.")
    vector = embed_text(query)
    client = _client()
    _ensure_collection(client)

    query_kwargs = {
        "collection_name": settings.QDRANT_COLLECTION,
        "query": vector,
        "limit": limit,
        "with_payload": True,
    }

    if only_available:
        query_kwargs["query_filter"] = models.Filter(
            must=[
                models.FieldCondition(
                    key="is_available",
                    match=models.MatchValue(value=True),
                )
            ]
        )

    response = client.query_points(**query_kwargs)

    return [point.payload for point in response.points if point.payload]


def delete_product(product_id: int) -> None:
    client = _client()

    if client.collection_exists(settings.QDRANT_COLLECTION):
        client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=models.PointIdsList(points=[product_id]),
        )

        logger.info("Deleted product pk=%s from Qdrant", product_id)
