from pathlib import Path
import os
import sys
from datetime import timedelta
from dotenv import load_dotenv

import sentry_sdk

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Carregar variáveis de ambiente priorizando server/.env e, em seguida, a raiz do repositório
env_paths = [
    BASE_DIR / ".env",
    BASE_DIR.parent / ".env",
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "development")
_IS_RUNNING_TESTS = "test" in sys.argv

def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(os.getenv(nome, "").strip() or padrao)
    except ValueError:
        return padrao


if SENTRY_DSN and not _IS_RUNNING_TESTS:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        send_default_pii=True,
        # Amostragem, não 100%. Com traces_sample_rate=1.0 toda requisição
        # virava uma transação com seus spans retidos em memória até o flush,
        # e o profiler contínuo (profile_session_sample_rate=1.0 +
        # profile_lifecycle="trace") amostrava a stack a ~101 Hz em todas
        # elas. Num processo que ficava mais de um mês sem reciclar, isso é
        # um piso de memória alto e permanente por worker.
        #
        # 10% dá volume estatístico suficiente para investigar incidentes.
        # O profiler fica desligado por padrão: liga-se pontualmente, via
        # variável de ambiente, quando houver o que investigar.
        traces_sample_rate=_env_float("SENTRY_TRACES_SAMPLE_RATE", 0.1),
        profile_session_sample_rate=_env_float("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        profile_lifecycle="trace",
        enable_logs=True,
    )

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-kcfth(u$19@ub1bz0de$(-knd-yp0xjj=2o8oold9fb!t+-&wn)')

# Token compartilhado com o scheduler externo (Celery beat/worker) usado para
# autenticar chamadas a endpoints internos em /api/internal/*.
NARA_INTERNAL_TOKEN = os.getenv('NARA_INTERNAL_TOKEN', '')

# UUID da instituição servida por este backend. Cada deploy é dedicado a
# uma escola, então o instituicao_id é configurado no ambiente — não é
# inferido de Usuario.instituicao nem do body da requisição. Quando vazio,
# o backend cai para os fallbacks (request.user / body / query param).
NARA_INSTITUICAO_ID = os.getenv('NARA_INSTITUICAO_ID', '')

# Broker do scheduler externo (mesmo Redis usado por beat/worker). Quando
# definido, o botão "Atualizar" do painel da coordenação enfileira a task
# `tasks.refresh_coordenacao_cache_por_instituicao` (usando NARA_INSTITUICAO_ID)
# em vez de regenerar o cache dentro do request. Vazio = botão desabilitado.
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', '')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'
def _split_env_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(',') if item.strip()]


raw_allowed_hosts = os.getenv('DJANGO_ALLOWED_HOSTS')

ALLOWED_HOSTS = _split_env_list(raw_allowed_hosts) if raw_allowed_hosts else []

# Limite de upload em memória (padrão Django: 2.5 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('DATA_UPLOAD_MAX_MEMORY_MB', '50')) * 1024 * 1024


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'api.middleware.PlanejamentoCorsMiddleware',  # Middleware customizado para planejamento
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'api.middleware.TenantMiddleware',  # Isolamento multi-tenant (escola/instituicao)
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nara_api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'nara_api.wsgi.application'

# Custom User Model
AUTH_USER_MODEL = 'api.Usuario'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# Suporte a SQLite para desenvolvimento local quando PostgreSQL não está disponível
USE_SQLITE = os.getenv('USE_SQLITE', 'false').lower() == 'true'

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'nara_production'),
            'USER': os.getenv('POSTGRES_USER', 'nara_user'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'secure_password'),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }

DATABASE_CONNECTION_POOLING = False

# Havia uma segunda definição de CACHES mais abaixo no arquivo, sem OPTIONS,
# que sobrescrevia esta silenciosamente — a afinação abaixo era código morto.
# Efeito colateral curioso: o bloco que vencia caía no MAX_ENTRIES padrão do
# LocMemCache (300), ou seja, um cache MENOR que o pretendido, não maior.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Usar DB para persistência
SESSION_COOKIE_AGE = 3 * 24 * 60 * 60   # 3 dias
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
SESSION_COOKIE_DOMAIN = os.getenv('SESSION_COOKIE_DOMAIN', None)
SESSION_SAVE_EVERY_REQUEST = True

# SameSite=None exige Secure=True (browsers rejeitam o cookie sem isso).
# Forçar Secure quando SameSite=None, mesmo com DEBUG=True, pois o deploy
# cross-domain (EasyPanel) usa HTTPS.
_samesite_none = SESSION_COOKIE_SAMESITE == 'None'
if _samesite_none or not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# CSRF settings
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_DOMAIN = os.getenv('CSRF_COOKIE_DOMAIN', None)
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5178",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5178",
    "http://nara.edunuvem.com",
    "https://nara.edunuvem.com",
]
extra_csrf_trusted_origins = _split_env_list(os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", ""))
if extra_csrf_trusted_origins:
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS + extra_csrf_trusted_origins))

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    # Rate limiting para segurança
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/min',   # Limite para usuários anônimos
        'user': '200/min',   # Limite para usuários autenticados
        'uploads': '10/min', # Limite específico para uploads
        'pareamento': '5/min', # Pareamento de gravador (único endpoint sem token: freio anti força-bruta)
    },
}

# Autenticação JWT (SimpleJWT) — usada pela API. Sessão/CSRF acima continuam
# valendo em paralelo para o Django Admin, que não passa pelo DRF.
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Multi-tenant: hoje cada escola roda numa instância dedicada (ver
# docs/PLANO_MULTI_TENANT.md), e o `instituicao_id` dos usuários pode divergir
# entre si nos dados legados. Enquanto isso, as checagens de "mesma instituição"
# ficam DESLIGADAS — ligá-las agora produziria falsos "de outra instituição".
# Quando o plano multi-tenant for executado, defina MULTI_TENANT_STRICT=true.
MULTI_TENANT_STRICT = os.getenv('MULTI_TENANT_STRICT', 'false').lower() == 'true'

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://164.92.69.153:5178",  # Frontend em produção
    "https://164.92.69.153:5178",
    "http://nara.edunuvem.com",
    "https://nara.edunuvem.com",
    "http://naraback.edunuvem.com",
    "https://naraback.edunuvem.com",
    "http://localhost:5178",      # Adicione esta linha
    "http://127.0.0.1:5178",      # Adicione esta linha
]
extra_cors_allowed_origins = _split_env_list(os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", ""))
if extra_cors_allowed_origins:
    CORS_ALLOWED_ORIGINS = list(dict.fromkeys(CORS_ALLOWED_ORIGINS + extra_cors_allowed_origins))

CORS_ALLOW_ALL_ORIGINS = False  # Para desenvolvimento
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'ngrok-skip-browser-warning',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_PREFLIGHT_MAX_AGE = 86400  # 24 horas

# Configurações de charset (removido locale problemático)
DEFAULT_CHARSET = 'utf-8'
FILE_CHARSET = 'utf-8'

MAILTRAP_API_TOKEN = "a340ec3c2ae0ab6f22f44f3df3435cce"
EMAIL_BACKEND = "anymail.backends.mailtrap.EmailBackend"
DEFAULT_FROM_EMAIL = "hello@demomailtrap.co"

ANYMAIL = {
  "MAILTRAP_API_TOKEN": MAILTRAP_API_TOKEN,
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} | {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'api': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}