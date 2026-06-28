"""
Smart-Stua Django Settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# ─── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Production: set ALLOWED_HOSTS to your Render subdomain (or custom domain).
# Development: localhost and 127.0.0.1 are included automatically.
_default_hosts = 'localhost,127.0.0.1,smartstua-backend.onrender.com'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', _default_hosts).split(',')

# ── Production Security Flags ─────────────────────────────────────────────────
# These only activate when DEBUG=False (i.e. in production).
# Behind Nginx: SECURE_SSL_REDIRECT is handled by Nginx itself, so we disable
# Django's redirect to avoid a redirect loop (Nginx already forces HTTPS).
if not DEBUG:
    SECURE_PROXY_SSL_HEADER      = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT          = False  # Nginx handles this
    SECURE_HSTS_SECONDS          = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD          = True
    SESSION_COOKIE_SECURE        = True
    CSRF_COOKIE_SECURE           = True
    SECURE_CONTENT_TYPE_NOSNIFF  = True

# ─── Applications ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'jazzmin',                     # ← MUST be before django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'django_ratelimit',            # Brute-force protection on login + IoT endpoints
    # Local
    'monitoring',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise: serves collected static files directly via Gunicorn on Render
    # (no separate Nginx needed). Must be second, right after SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'smartstua.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'smartstua.wsgi.application'

# ─── Database ────────────────────────────────────────────────────────────────
# Production: reads DATABASE_URL from environment (set by Docker Compose).
# Development fallback: SQLite (auto-used when DATABASE_URL is not set).
_DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{BASE_DIR / "db.sqlite3"}'
)
DATABASES = {
    'default': dj_database_url.parse(_DATABASE_URL, conn_max_age=600)
}

# ─── Cache (Redis) ────────────────────────────────────────────────────────────
# Required by django-ratelimit for shared, distributed rate-limit counters.
# Uses Django 4.2's built-in RedisCache — no extra package needed.
_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': _REDIS_URL,
        'TIMEOUT': 300,
        'OPTIONS': {
            'db': '1',          # Use DB 1 for cache; DB 0 is reserved for Celery
        },
    }
}

# ─── Auth ────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kampala'
USE_I18N = True
USE_TZ = True

# ─── Static Files ────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# WhiteNoise: compress + fingerprint assets at collectstatic time.
# Serves admin (Jazzmin) CSS/JS via Gunicorn on Render — no separate Nginx required.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Django REST Framework ───────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ],
}

# ─── CORS ────────────────────────────────────────────────────────────────────
# Production CORS: lock to Render subdomain + Expo dev server.
# Override via CORS_ALLOWED_ORIGINS env var in production .env.
_default_cors = 'http://localhost:3000,http://localhost:8081,https://smartstua-backend.onrender.com'
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', _default_cors).split(',')
CORS_ALLOW_CREDENTIALS = True

CELERY_BROKER_URL      = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND  = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT  = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE        = 'Africa/Kampala'
# In production (Docker) Redis is always present — disable eager mode.
# Override via env var for local dev without Redis: CELERY_TASK_ALWAYS_EAGER=True
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'

# ─── MQTT ────────────────────────────────────────────────────────────────────
MQTT_BROKER   = os.environ.get('MQTT_BROKER', 'localhost')
MQTT_PORT     = int(os.environ.get('MQTT_PORT', 1883))
MQTT_USE_TLS  = os.environ.get('MQTT_USE_TLS', 'False') == 'True'
MQTT_USERNAME = os.environ.get('MQTT_USERNAME', '')
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD', '')


# Periodic tasks
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'calculate-cumulative-duration-every-15-min': {
        'task': 'monitoring.tasks.calculate_all_cumulative_durations',
        'schedule': crontab(minute='*/15'),
    },
    # Tightened from */15 to */2 to support real-time node offline detection
    # (nodes now publish every 5s; flag as offline after 60s without a reading)
    'check-offline-nodes-every-2-min': {
        'task': 'monitoring.tasks.check_offline_nodes',
        'schedule': crontab(minute='*/2'),
    },
}

# ─── Twilio SMS ──────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN  = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE       = os.environ.get('TWILIO_PHONE_NUMBER', '')

# ─── Sensor API Key ──────────────────────────────────────────────────────────
SENSOR_API_KEY = os.environ.get('SENSOR_API_KEY', 'dev-sensor-api-key')

# ─── Jazzmin Admin UI ────────────────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    # ── Branding ────────────────────────────────────────────────────────────────
    'site_title':      'Smart-Stua Admin',
    'site_header':     'Smart-Stua',
    'site_brand':      'Smart-Stua',
    'site_logo':        None,
    'login_logo':       None,
    'welcome_sign':    'Welcome to Smart-Stua IoT Platform',
    'copyright':       'Smart-Stua © 2025',

    # ── Top Navigation Bar ──────────────────────────────────────────────────────
    'topmenu_links': [
        {'name': 'API Health',  'url': '/api/health/',   'new_window': True},
        {'name': 'Dashboard',   'url': '/api/dashboard/summary/', 'new_window': True},
        {'model': 'monitoring.sensornode'},
        {'app': 'monitoring'},
    ],

    # ── User Menu (top-right) ───────────────────────────────────────────────────
    'usermenu_links': [
        {'name': 'Smart-Stua Docs', 'url': 'https://github.com/', 'new_window': True, 'icon': 'fas fa-book'},
    ],

    # ── Sidebar Navigation ──────────────────────────────────────────────────────
    'show_sidebar':         True,
    'navigation_expanded':  True,
    'hide_apps':            [],
    'hide_models':          [],
    'order_with_respect_to': [
        'monitoring',
        'monitoring.sensornode',
        'monitoring.reading',
        'monitoring.alertlog',
        'monitoring.threshold',
        'monitoring.user',
        'auth',
    ],

    # ── Per-Model Icons (Font Awesome 5) ────────────────────────────────────────
    'icons': {
        # App icons
        'monitoring':                   'fas fa-seedling',
        'auth':                         'fas fa-lock',
        # Model icons
        'monitoring.user':              'fas fa-users',
        'monitoring.sensornode':        'fas fa-microchip',
        'monitoring.reading':           'fas fa-chart-line',
        'monitoring.alertlog':          'fas fa-bell',
        'monitoring.threshold':         'fas fa-sliders-h',
        'auth.user':                    'fas fa-user-shield',
        'auth.group':                   'fas fa-users-cog',
        'authtoken.tokenproxy':         'fas fa-key',
    },
    'default_icon_parents':  'fas fa-folder',
    'default_icon_children': 'fas fa-circle',

    # ── UI Tweaks ───────────────────────────────────────────────────────────────
    'related_modal_active': True,
    'custom_css':            None,
    'custom_js':             None,
    'show_ui_builder':       False,     # Set True to use the live theme editor
    'changeform_format':     'horizontal_tabs',
    'changeform_format_overrides': {
        'auth.user':     'collapsible',
        'auth.group':    'vertical_tabs',
    },
    'language_chooser': False,
}

JAZZMIN_UI_TWEAKS = {
    'navbar_small_text':    False,
    'footer_small_text':    False,
    'body_small_text':      False,
    'brand_small_text':     False,
    'brand_colour':         'navbar-success',   # green brand bar
    'accent':               'accent-success',
    'navbar':               'navbar-dark',
    'no_navbar_border':     True,
    'navbar_fixed':         True,
    'layout_boxed':         False,
    'footer_fixed':         False,
    'sidebar_fixed':        True,
    'sidebar':              'sidebar-dark-success',
    'sidebar_nav_small_text': False,
    'sidebar_disable_expand': False,
    'sidebar_nav_child_indent': True,
    'sidebar_nav_compact_style': False,
    'sidebar_nav_legacy_style':  False,
    'sidebar_nav_flat_style':    False,
    'theme':                'flatly',
    'dark_mode_theme':      'darkly',
    'button_classes': {
        'primary':   'btn-outline-primary',
        'secondary': 'btn-outline-secondary',
        'info':      'btn-info',
        'warning':   'btn-warning',
        'danger':    'btn-danger',
        'success':   'btn-success',
    },
}
