GRAPHITE_ROOT = '%(dir)s'
TIME_ZONE = 'UTC'
STATIC_URL = '/static/'
STATIC_ROOT = '%(dir)s/static'
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
