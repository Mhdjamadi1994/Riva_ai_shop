from pathlib import Path
import os
from decimal import Decimal, InvalidOperation
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("DEBUG", "False").lower() in {"1", "true", "yes", "on"}
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in {"1", "true", "yes", "on"}
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ValueError("SECRET_KEY must be set when DEBUG is disabled.")
    SECRET_KEY = "django-insecure-local-development-only"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
if not DEBUG:
    if len(SECRET_KEY) < 50 or SECRET_KEY == "django-insecure-local-development-only":
        raise ValueError("Production SECRET_KEY must contain at least 50 characters.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ValueError("Production ALLOWED_HOSTS must list exact hostnames.")
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if os.getenv("TRUST_PROXY_SSL", "false").lower() in {"1", "true", "yes", "on"}:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() in {"1", "true", "yes", "on"}
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() in {"1", "true", "yes", "on"}
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "false").lower() in {"1", "true", "yes", "on"}
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.products.apps.ProductsConfig",
    "apps.chatbot.apps.ChatbotConfig",
    "apps.recommendation.apps.RecommendationConfig",
    "apps.agents.apps.AgentsConfig",
    "apps.storefront.apps.StorefrontConfig",
    "django_extensions",
    "django_filters",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()
if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "ai_shop_assistant"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        }
    }
elif DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        }
    }
else:
    raise ValueError("DB_ENGINE must be either 'sqlite' or 'postgresql'.")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
        if not DEBUG else
        {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "riva-local"}
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
_configured_currency = os.getenv("SHOP_CURRENCY", "USDT")
SHOP_CURRENCY = _configured_currency if _configured_currency.isascii() else "USDT"
try:
    TOMAN_PER_USD = Decimal(os.getenv("TOMAN_PER_USD", "265900"))
except InvalidOperation as exc:
    raise ValueError("TOMAN_PER_USD must be a positive decimal number.") from exc
if not TOMAN_PER_USD.is_finite() or TOMAN_PER_USD <= 0:
    raise ValueError("TOMAN_PER_USD must be a positive decimal number.")
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "").rstrip("/")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", BASE_DIR / "backups"))
BACKUP_S3_BUCKET = os.getenv("BACKUP_S3_BUCKET", "").strip()
BACKUP_S3_PREFIX = os.getenv("BACKUP_S3_PREFIX", "riva/database").strip("/")
BACKUP_S3_REGION = os.getenv("BACKUP_S3_REGION", "us-east-1")
BACKUP_S3_KMS_KEY_ID = os.getenv("BACKUP_S3_KMS_KEY_ID", "")
BACKUP_S3_ENDPOINT_URL = os.getenv("BACKUP_S3_ENDPOINT_URL", "")
BACKUP_RESTORE_TEST_ENABLED = os.getenv("BACKUP_RESTORE_TEST_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
FX_RATE_MAX_AGE_HOURS = int(os.getenv("FX_RATE_MAX_AGE_HOURS", "24"))
FX_RATE_PROVIDER_URL = os.getenv("FX_RATE_PROVIDER_URL", "").strip()
FX_RATE_PROVIDER_TOKEN = os.getenv("FX_RATE_PROVIDER_TOKEN", "")
FX_RATE_PROVIDER_SOURCE = os.getenv("FX_RATE_PROVIDER_SOURCE", "").strip()[:100]
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "mock" if DEBUG else "disabled").strip().lower()
ALLOW_MOCK_PAYMENTS = os.getenv("ALLOW_MOCK_PAYMENTS", str(DEBUG)).lower() in {"1", "true", "yes", "on"}
ALLOW_UNAUDITED_FX_FALLBACK = os.getenv("ALLOW_UNAUDITED_FX_FALLBACK", str(DEBUG)).lower() in {"1", "true", "yes", "on"}
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "")
PAYMENT_GATEWAY_TIMEOUT_SECONDS = float(os.getenv("PAYMENT_GATEWAY_TIMEOUT_SECONDS", "15"))
PAYMENT_RESERVATION_MINUTES = int(os.getenv("PAYMENT_RESERVATION_MINUTES", "30"))
PAYMENT_WEBHOOK_TOLERANCE_SECONDS = int(os.getenv("PAYMENT_WEBHOOK_TOLERANCE_SECONDS", "300"))
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").lower() in {"1", "true", "yes", "on"}
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Riva Support <support@example.com>")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 2,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10/minute",
        "token_refresh": "30/minute",
        "llm": "30/minute",
        "telegram": "120/minute",
        "storefront": "120/minute",
        "registration": "5/hour",
    },
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = TIME_ZONE
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "shop_catalog")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
SEMANTIC_SEARCH_ENABLED = bool(EMBEDDING_MODEL and LLM_BASE_URL and LLM_API_KEY)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
TELEGRAM_MAX_MESSAGE_LENGTH = 4000

CELERY_BEAT_SCHEDULE = {}
if os.getenv("DATABASE_BACKUP_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
    CELERY_BEAT_SCHEDULE["daily-database-backup"] = {
        "task": "apps.agents.tasks.create_scheduled_backup",
        "schedule": crontab(
            hour=int(os.getenv("DATABASE_BACKUP_HOUR", "2")),
            minute=int(os.getenv("DATABASE_BACKUP_MINUTE", "0")),
        ),
    }
if os.getenv("ADMIN_DAILY_REPORT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
    CELERY_BEAT_SCHEDULE["daily-admin-report"] = {
        "task": "apps.agents.tasks.create_scheduled_admin_report",
        "schedule": crontab(
            hour=int(os.getenv("ADMIN_REPORT_HOUR", "9")),
            minute=int(os.getenv("ADMIN_REPORT_MINUTE", "0")),
        ),
    }
CELERY_BEAT_SCHEDULE["expire-pending-checkouts"] = {
    "task": "apps.core.tasks.expire_stale_order_payments",
    "schedule": crontab(minute="*/5"),
}
if os.getenv("BACKUP_RESTORE_TEST_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
    CELERY_BEAT_SCHEDULE["weekly-backup-restore-drill"] = {
        "task": "apps.agents.tasks.verify_latest_backup",
        "schedule": crontab(day_of_week="sun", hour=3, minute=0),
    }
if FX_RATE_PROVIDER_URL:
    CELERY_BEAT_SCHEDULE["hourly-usd-toman-rate-refresh"] = {
        "task": "apps.core.tasks.refresh_usd_toman_rate",
        "schedule": crontab(minute=5),
    }
