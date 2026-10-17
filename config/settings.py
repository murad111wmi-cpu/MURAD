import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from .key_material import configured_secret_key
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DEBUG', '0') == '1'
SECRET_KEY = configured_secret_key(os.environ)
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY securely, or DEBUG=1 for local development only.')
    secret_path = BASE_DIR / 'data' / 'dev-secret'
    secret_path.parent.mkdir(exist_ok=True)
    if not secret_path.exists():
        import secrets
        fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(secrets.token_urlsafe(64))
    SECRET_KEY = secret_path.read_text()
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]' if DEBUG else '').split(',')
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if x]
# Render supplies this hostname; custom domains still use explicit environment settings.
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)
    CSRF_TRUSTED_ORIGINS.append('https://' + render_hostname)
STORE_SETUP_TOKEN = os.environ.get('STORE_SETUP_TOKEN', '')
SERVE_PUBLIC_UPLOADS = os.environ.get('SERVE_PUBLIC_UPLOADS', '0') == '1'
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','shop.apps.ShopConfig']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','shop.middleware.ActiveStaffMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','shop.context.store_context']}}]
WSGI_APPLICATION = 'config.wsgi.application'
(BASE_DIR/'data').mkdir(exist_ok=True)
DATABASES = {'default':dj_database_url.config(default=f'sqlite:///{BASE_DIR}/data/store.sqlite3', conn_max_age=60)}
if DATABASES['default']['ENGINE'].endswith('sqlite3'):
    DATABASES['default']['OPTIONS'] = {'timeout':30}
AUTH_USER_MODEL = 'shop.User'
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'ar'
LANGUAGES = [('ar','العربية'),('en','English')]
TIME_ZONE = os.environ.get('STORE_TIME_ZONE','Asia/Amman')
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR/'static']
STATIC_ROOT = BASE_DIR/'staticfiles'
STORAGES = {'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT',str(BASE_DIR/'media')))
MEDIA_URL = '/media/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/worker/login/'
LOGIN_REDIRECT_URL = '/worker/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8*60*60
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# Set TRUST_PROXY=1 only behind the included Nginx config or a trusted hosting proxy.
if os.environ.get('TRUST_PROXY') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND','django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST','')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT','587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD','')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS','1') == '1'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL','')
EMAIL_TIMEOUT = 10
DATA_UPLOAD_MAX_MEMORY_SIZE = 15*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2*1024*1024
CACHES = {'default':{'BACKEND':'django.core.cache.backends.db.DatabaseCache','LOCATION':'shop_cache'}}
