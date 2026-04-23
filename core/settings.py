"""
Django settings for core project - Production Ready
"""

from pathlib import Path
import environ
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ==================================================
# ENVIRONMENT
# ==================================================

env = environ.Env()

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ==================================================
# SEGURIDAD
# ==================================================

SECRET_KEY = env('SECRET_KEY')

DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env('ALLOWED_HOSTS').split(',')

# ==================================================
# APPS
# ==================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps propias
    'users',
    'branches',
    'products',
    'inventory',
    'sales',
    'dashboard',
    'diets',
    'orders',
    'cashregister',
    'earnings',
    'finished',
]

# ==================================================
# MIDDLEWARE
# ==================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ==================================================
# URLS
# ==================================================

ROOT_URLCONF = 'core.urls'

# ==================================================
# TEMPLATES
# ==================================================

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

# ==================================================
# WSGI
# ==================================================

WSGI_APPLICATION = 'core.wsgi.application'

# ==================================================
# DATABASE
# ==================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
    }
}

# ==================================================
# PASSWORD VALIDATION
# ==================================================

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

# ==================================================
# INTERNATIONALIZATION
# ==================================================

LANGUAGE_CODE = 'es-mx'

TIME_ZONE = 'America/Mexico_City'

USE_I18N = True

USE_TZ = True

# ==================================================
# STATIC FILES
# ==================================================

STATIC_URL = '/static/'

STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ==================================================
# MEDIA FILES
# ==================================================

MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'

# ==================================================
# USER MODEL
# ==================================================

AUTH_USER_MODEL = 'users.User'

# ==================================================
# LOGIN
# ==================================================

LOGIN_REDIRECT_URL = '/redirect/'
LOGIN_URL = '/login/'
LOGOUT_REDIRECT_URL = '/login/'

# ==================================================
# SEGURIDAD EXTRA
# ==================================================

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = 'DENY'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ==================================================
# LOGGING
# ==================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}