"""Django settings for TrystSol.

Environment-driven; see .env.example at the repository root.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    ACCESS_TOKEN_TTL_SECONDS=(int, 900),
    REFRESH_TOKEN_TTL_DAYS=(int, 30),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
    SOLANA_CLUSTER=(str, "devnet"),
    SOLANA_RPC_URL=(str, "https://api.devnet.solana.com"),
    SERVER_RPC_URL=(str, ""),
    SIWS_DOMAIN=(str, "localhost:3000"),
    SIWS_URI=(str, "http://localhost:3000"),
    PROGRAM_ID=(str, "11111111111111111111111111111111"),
    DJANGO_ENV=(str, "development"),
    JUPITER_API_KEY=(str, ""),
    GITHUB_TOKEN=(str, ""),
    JUPITER_BASE_URL=(str, "https://api.jup.ag"),
    GITHUB_API_URL=(str, "https://api.github.com"),
    JUPITER_CACHE_TTL=(int, 300),
    GITHUB_CACHE_TTL=(int, 900),
    RPC_FACT_CACHE_TTL=(int, 300),
    MAINNET_RPC_URL=(str, "https://api.mainnet-beta.solana.com"),
)

environ.Env.read_env(ROOT_DIR / ".env")

ENVIRONMENT = env("DJANGO_ENV")
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
    "apps.projects",
    "apps.milestones",
    "apps.evidence",
    "apps.reviews",
    "apps.chain",
    "apps.integrations",
    "apps.decision_pages",
    "apps.passport",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db_url("DATABASE_URL", default="postgres://trystsol:trystsol@127.0.0.1:5433/trystsol")}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "auth": "20/min",
        "anon": "60/min",
        "user": "240/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "TrystSol API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6380/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "trystsol",
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BEAT_SCHEDULE = {
    "check-rpc-health": {
        "task": "apps.chain.tasks.check_rpc_health",
        "schedule": 300.0,
    },
    "reconcile-chain-state": {
        "task": "apps.chain.tasks.reconcile_chain_state",
        "schedule": 900.0,
    },
    "prune-expired-intents": {
        "task": "apps.chain.tasks.prune_expired_intents",
        "schedule": 86400.0,
    },
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

REFRESH_COOKIE_NAME = env("REFRESH_COOKIE_NAME", default="trystsol_refresh")
REFRESH_COOKIE_PATH = "/api/auth/"
REFRESH_COOKIE_SAMESITE = "Lax"

# --- Application settings -------------------------------------------------

ACCESS_TOKEN_SECRET = env("ACCESS_TOKEN_SECRET", default=SECRET_KEY)
ACCESS_TOKEN_TTL_SECONDS = env("ACCESS_TOKEN_TTL_SECONDS")
REFRESH_TOKEN_TTL_DAYS = env("REFRESH_TOKEN_TTL_DAYS")

SIWS_DOMAIN = env("SIWS_DOMAIN")
SIWS_URI = env("SIWS_URI")
SIWS_CHAIN_ID = env("SOLANA_CLUSTER")  # devnet / mainnet / localnet
SIWS_NONCE_TTL_SECONDS = env.int("SIWS_NONCE_TTL_SECONDS", default=300)
SIWS_ISSUED_AT_SKEW_SECONDS = env.int("SIWS_ISSUED_AT_SKEW_SECONDS", default=600)
SIWS_STATEMENT = (
    "Sign in to TrystSol. This proves you control this wallet. "
    "It does not trigger a blockchain transaction or cost any fee."
)

SOLANA_CLUSTER = env("SOLANA_CLUSTER")
SOLANA_RPC_URL = env("SOLANA_RPC_URL")
SERVER_RPC_URL = env("SERVER_RPC_URL") or env("SOLANA_RPC_URL")
PROGRAM_ID = env("PROGRAM_ID")
INDEXER_SHARED_SECRET = env("INDEXER_SHARED_SECRET", default="dev-indexer-secret")

# --- Phase 4 integrations (read-only) -------------------------------------
JUPITER_API_KEY = env("JUPITER_API_KEY")
JUPITER_BASE_URL = env("JUPITER_BASE_URL")
GITHUB_TOKEN = env("GITHUB_TOKEN")
GITHUB_API_URL = env("GITHUB_API_URL")
JUPITER_CACHE_TTL = env("JUPITER_CACHE_TTL")
GITHUB_CACHE_TTL = env("GITHUB_CACHE_TTL")
RPC_FACT_CACHE_TTL = env("RPC_FACT_CACHE_TTL")
MAINNET_RPC_URL = env("MAINNET_RPC_URL")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.common.logging.JsonFormatter"},
        "plain": {"format": "%(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if not DEBUG else "plain",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}


# --- Production guardrails -------------------------------------------------

def validate_production_settings() -> None:
    """Fail closed when DJANGO_ENV=production is misconfigured."""
    global ENVIRONMENT
    problems: list[str] = []
    if SECRET_KEY.startswith("dev-only") or len(SECRET_KEY) < 32:
        problems.append("DJANGO_SECRET_KEY must be a long, non-default secret.")
    if len(ACCESS_TOKEN_SECRET) < 32:
        problems.append("ACCESS_TOKEN_SECRET must be at least 32 characters.")
    if not ALLOWED_HOSTS:
        problems.append("DJANGO_ALLOWED_HOSTS must not be empty.")
    if "*" in ALLOWED_HOSTS:
        problems.append("DJANGO_ALLOWED_HOSTS must not contain '*'.")
    if not CORS_ALLOWED_ORIGINS:
        problems.append("CORS_ALLOWED_ORIGINS must not be empty.")
    if any(origin.startswith("http://") for origin in CORS_ALLOWED_ORIGINS):
        problems.append("Production CORS origins must use https.")
    if SIWS_DOMAIN.startswith("localhost") or SIWS_DOMAIN.startswith("127."):
        problems.append("SIWS_DOMAIN must be the public host in production.")
    if problems:
        raise ImproperlyConfigured("Invalid production configuration: " + " ".join(problems))


if ENVIRONMENT == "production":
    validate_production_settings()
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
