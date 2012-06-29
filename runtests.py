#!/usr/bin/env python
import sys

from os.path import dirname, abspath

from django.conf import settings

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
        SITE_DOMAIN = "localhost"
    )

from django.test.simple import DjangoTestSuiteRunner


def runtests(*test_args):
    if not test_args:
        test_args = ['linkcheck']
    parent = dirname(abspath(__file__))
    sys.path.insert(0, parent)
    test_runner = DjangoTestSuiteRunner(verbosity=1, interactive=True)
    failures = test_runner.run_tests(test_args)
    sys.exit(failures)


if __name__ == '__main__':
    runtests(*sys.argv[1:])
