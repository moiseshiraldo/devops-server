TIME_ZONE = 'UTC'
STATIC_URL = '/static/'
STATIC_ROOT = '${GRAPHITE_ROOT}/static'
URL_PREFIX = ''

DATABASES = {
    'default': {
	'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'graphite',
        'USER': 'dashboard',
        'PASSWORD': 'dashboard',
        'HOST': 'localhost',
        'PORT': ''
    }
}
