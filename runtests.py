#!/usr/bin/env python
import sys

from os.path import dirname, abspath

import django
from django.conf import settings

if not settings.configured:
    test_settings = {
        'DATABASES': {'default': {'ENGINE': 'django.db.backends.sqlite3'}},
        'STATIC_URL': '/static/',
        'MEDIA_URL': '/media/',
        'INSTALLED_APPS': [
            'django.contrib.admin', 'django.contrib.auth',
            'django.contrib.sessions', 'django.contrib.contenttypes',
            'django.contrib.messages',
            'linkcheck', 'linkcheck.tests.sampleapp',
        ],
        'ROOT_URLCONF': "linkcheck.tests.urls",
        'SITE_DOMAIN': "localhost",
        'MIDDLEWARE': [
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
        ],
        'TEMPLATES': [{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                    'django.template.context_processors.static',
                    'django.template.context_processors.request',
                ],
            },
        }],
        'DEFAULT_AUTO_FIELD': 'django.db.models.AutoField',
        'SECRET_KEY': 'arandomstring',
        'LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT': 1,
    }
    settings.configure(**test_settings)


def runtests(*test_args):
    from django.test.runner import DiscoverRunner

    parent = dirname(abspath(__file__))
    sys.path.insert(0, parent)
    test_runner = DiscoverRunner(verbosity=1, interactive=True)
    failures = test_runner.run_tests(test_args)
    sys.exit(failures)


if __name__ == '__main__':
    django.setup()
    runtests(*sys.argv[1:])
