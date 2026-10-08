from django.db import connections
from django.db.utils import OperationalError
from django.conf import settings
from django.http import JsonResponse


def health_check(request):
    checks = {
        "database": "ok",
        "semantic_search": "enabled" if settings.SEMANTIC_SEARCH_ENABLED else "not_configured",
    }
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError:
        checks["database"] = "error"
    try:
        from redis import Redis
        Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1).ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    if settings.SEMANTIC_SEARCH_ENABLED:
        try:
            import httpx
            response = httpx.get(f"{settings.QDRANT_URL.rstrip('/')}/readyz", timeout=1)
            checks["qdrant"] = "ok" if response.is_success else "error"
        except Exception:
            checks["qdrant"] = "error"
    else:
        checks["qdrant"] = "not_configured"
    healthy = (checks["database"] == "ok" and checks["redis"] == "ok" and
               checks["qdrant"] != "error")
    critical_dependencies_ok = (
        checks["database"] == "ok" and
        (settings.DEBUG or checks["redis"] == "ok") and
        (checks["qdrant"] != "error" or settings.DEBUG)
    )
    return JsonResponse({"status": "ok" if healthy else "degraded", **checks}, status=200 if critical_dependencies_ok else 503)
