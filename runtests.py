#!/usr/bin/env python
import sys

from os.path import dirname, abspath

import django
from django.conf import settings
from django.test.runner import DiscoverRunner

if not settings.configured:
    settings.configure(
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3'}},
        STATIC_URL = '/static/',
        INSTALLED_APPS=[
            'django.contrib.admin', 'django.contrib.auth',
            'django.contrib.sessions', 'django.contrib.contenttypes',
            'linkcheck', 'linkcheck.tests.sampleapp',
        ],
        ROOT_URLCONF = "linkcheck.tests.test_urls",
        MIDDLEWARE_CLASSES=(
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
        ),
        SITE_DOMAIN = "localhost"
    )


def runtests(*test_args):
    if not test_args:
        test_args = ['linkcheck']
    parent = dirname(abspath(__file__))
    sys.path.insert(0, parent)
    test_runner = DiscoverRunner(verbosity=1, interactive=True)
    failures = test_runner.run_tests(test_args)
    sys.exit(failures)


if __name__ == '__main__':
    django.setup()
    runtests(*sys.argv[1:])
