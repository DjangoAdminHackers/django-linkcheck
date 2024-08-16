import os
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

import requests_mock
import urllib3
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import LiveServerTestCase, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from requests.exceptions import ConnectionError

from linkcheck.linkcheck_settings import MAX_URL_LENGTH
from linkcheck.listeners import (
    disable_listeners,
    enable_listeners,
    linkcheck_worker,
    register_listeners,
    tasks_queue,
    unregister_listeners,
)
from linkcheck.models import Link, Url
from linkcheck.views import get_jquery_min_js

from .sampleapp.models import Author, Book, Journal, Page


@override_settings(ROOT_URLCONF='linkcheck.tests.urls')
class InternalCheckTestCase(TestCase):

    def test_internal_check_mailto(self):
        uv = Url(url="mailto:nobody")
        uv.check_url()
        self.assertEqual(uv.message, 'Email link (not automatically checked)')
        self.assertEqual(uv.get_message, 'Email link (not automatically checked)')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, None)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'mailto')

    def test_internal_check_tel(self):
        uv = Url(url="tel:+123456789")
        uv.check_url()
        self.assertEqual(uv.message, 'Phone number (not automatically checked)')
        self.assertEqual(uv.get_message, 'Phone number link (not automatically checked)')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, None)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'phone')

    def test_internal_check_blank(self):
        uv = Url(url="")
        uv.check_url()
        self.assertEqual(uv.message, 'Empty link')
        self.assertEqual(uv.get_message, 'Empty link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'empty')

    def test_same_page_anchor(self):
        uv = Url(url="#some_anchor")
        uv.check_url()
        self.assertEqual(uv.message, 'Link to within the same page (not automatically checked)')
        self.assertEqual(uv.get_message, 'Anchor link (not automatically checked)')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, None)
        self.assertEqual(uv.anchor_message, 'Anchor could not be checked')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'anchor')

    def test_working_internal_anchor(self):
        uv = Url(url="/http/anchor/#anchor")
        uv.check_url()
        self.assertEqual(uv.message, "Working internal link, working internal hash anchor")
        self.assertEqual(uv.get_message, 'Working internal link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Working anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'internal')

    @patch("linkcheck.models.TOLERATE_BROKEN_ANCHOR", False)
    def test_broken_internal_anchor(self):
        uv = Url(url="/http/anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.message, "Working internal link, broken internal hash anchor")
        self.assertEqual(uv.get_message, 'Working internal link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'internal')

    def test_broken_internal_anchor_tolerated(self):
        uv = Url(url="/http/anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.message, "Working internal link, broken internal hash anchor")
        self.assertEqual(uv.get_message, 'Working internal link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'internal')

    def test_redirect_working_internal_anchor(self):
        uv = Url(url="/http/redirect_to_anchor/#anchor")
        uv.check_url()
        self.assertEqual(uv.message, "Working temporary redirect, working internal hash anchor")
        self.assertEqual(uv.get_message, 'Working temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Working anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, '/http/anchor/')
        self.assertEqual(uv.type, 'internal')

    @patch("linkcheck.models.TOLERATE_BROKEN_ANCHOR", False)
    def test_redirect_broken_internal_anchor(self):
        uv = Url(url="/http/redirect_to_anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.message, "Working temporary redirect, broken internal hash anchor")
        self.assertEqual(uv.get_message, 'Working temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, '/http/anchor/')
        self.assertEqual(uv.type, 'internal')

    def test_redirect_broken_internal_anchor_tolerated(self):
        uv = Url(url="/http/redirect_to_anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.message, "Working temporary redirect, broken internal hash anchor")
        self.assertEqual(uv.get_message, 'Working temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, '/http/anchor/')
        self.assertEqual(uv.type, 'internal')

    def test_internal_check_working_redirect(self):
        uv = Url(url="/admin/linkcheck")
        uv.check_url()
        self.assertEqual(uv.message, "Working temporary redirect")
        self.assertEqual(uv.get_message, 'Working temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, '/admin/login/?next=/admin/linkcheck')
        self.assertEqual(uv.type, 'internal')

    def test_internal_check_broken_redirect(self):
        uv = Url(url="/http/brokenredirect/")
        uv.check_url()
        self.assertEqual(uv.message, 'Broken temporary redirect')
        self.assertEqual(uv.get_message, 'Broken temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '404 Not Found')
        self.assertEqual(uv.redirect_to, '/non-existent/')
        self.assertEqual(uv.type, 'internal')

    def test_internal_check_found(self):
        uv = Url(url="/public/")
        uv.check_url()
        self.assertEqual(uv.message, 'Working internal link')
        self.assertEqual(uv.get_message, 'Working internal link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'internal')

    def test_internal_check_with_protocol(self):
        # "localhost" is configured as SITE_DOMAIN in settings
        uv = Url(url="http://localhost/public/")
        uv.check_url()
        self.assertEqual(uv.message, 'Working internal link')
        self.assertEqual(uv.get_message, 'Working internal link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'internal')

    def test_internal_check_broken_internal_link(self):
        uv = Url(url="/broken/internal/link")
        uv.check_url()
        self.assertEqual(uv.message, 'Broken internal link')
        self.assertEqual(uv.get_message, 'Broken internal link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), '404 Not Found')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'internal')

    def test_internal_check_invalid_url(self):
        uv = Url(url="invalid/url")
        uv.check_url()
        self.assertEqual(uv.message, 'Invalid URL')
        self.assertEqual(uv.get_message, 'Invalid URL')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'invalid')


class InternalMediaCheckTestCase(TestCase):
    def setUp(self):
        self.old_media_root = settings.MEDIA_ROOT
        settings.MEDIA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media')

    def tearDown(self):
        settings.MEDIA_ROOT = self.old_media_root

    def test_internal_check_media_missing(self):
        uv = Url(url="/media/not_found")
        uv.check_url()
        self.assertEqual(uv.message, 'Missing Document')
        self.assertEqual(uv.get_message, 'Missing file')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'file')

    def test_internal_check_media_found(self):
        uv = Url(url="/media/found")
        uv.check_url()
        self.assertEqual(uv.message, 'Working file link')
        self.assertEqual(uv.get_message, 'Working file link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'file')

    def test_internal_check_media_utf8(self):
        media_file = os.path.join(os.path.dirname(__file__), 'media', 'rückmeldung')
        open(media_file, 'a').close()
        self.addCleanup(os.remove, media_file)
        uv = Url(url="/media/r%C3%BCckmeldung")
        uv.check_url()
        self.assertEqual(uv.message, 'Working file link')
        self.assertEqual(uv.get_message, 'Working file link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'file')
        # Also when the url is not encoded
        uv = Url(url="/media/rückmeldung")
        uv.check_url()
        self.assertEqual(uv.message, 'Working file link')
        self.assertEqual(uv.get_message, 'Working file link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, '')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'file')


@override_settings(SITE_DOMAIN='example.com')
class ExternalCheckTestCase(LiveServerTestCase):

    def setUp(self):
        urllib3.disable_warnings()

    def test_external_check_200(self):
        uv = Url(url=f"{self.live_server_url}/http/200/")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_200_valid_cert(self):
        uv = Url(url='https://rsa4096.badssl.com/')
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, True)
        self.assertEqual(uv.ssl_message, 'Valid SSL certificate')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_200_missing_cert(self):
        uv = Url(url=f"{self.live_server_url.replace('http://', 'https://')}/http/200/")
        uv.check_url()
        self.assertEqual(uv.message, 'SSL Error: wrong version number')
        self.assertEqual(uv.get_message, 'SSL Error: wrong version number')
        self.assertEqual(uv.error_message, 'SSL Error: wrong version number')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, False)
        self.assertEqual(uv.ssl_message, 'Broken SSL certificate')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_200_incomplete_cert(self):
        uv = Url(url="https://incomplete-chain.badssl.com/")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK, SSL certificate could not be verified')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'SSL certificate could not be checked')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_200_broken_anchor_incomplete_cert(self):
        uv = Url(url="https://incomplete-chain.badssl.com/#broken")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK, broken external hash anchor, SSL certificate could not be verified')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'SSL certificate could not be checked')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_404_incomplete_cert(self):
        uv = Url(url="https://incomplete-chain.badssl.com/404")
        uv.check_url()
        self.assertEqual(uv.message, '404 Not Found, SSL certificate could not be verified')
        self.assertEqual(uv.get_message, 'Broken external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'SSL certificate could not be checked')
        self.assertEqual(uv.get_status_code_display(), '404 Not Found')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    @requests_mock.Mocker()
    def test_external_check_unreachable(self, mocker):
        exc = ConnectionError(
            "HTTPSConnectionPool(host='name-resolution-error.example.com', port=443): Max retries exceeded with url: / "
            "(Caused by NameResolutionError(\"<urllib3.connection.HTTPSConnection object at 0xdeadbeef>: "
            "Failed to resolve 'name-resolution-error.example.com' ([Errno -2] Name or service not known)\"))"
        )
        mocked_url = 'https://name-resolution-error.example.com/'
        mocker.register_uri('HEAD', mocked_url, exc=exc),
        uv = Url(url=mocked_url)
        uv.check_url()
        formatted_message = (
            "Name Resolution Error: Failed to resolve 'name-resolution-error.example.com' "
            "([Errno -2] Name or service not known)"
        )
        self.assertEqual(uv.message, formatted_message)
        self.assertEqual(uv.get_message, formatted_message)
        self.assertEqual(uv.error_message, formatted_message)
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'SSL certificate could not be checked')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_200_utf8(self):
        uv = Url(url=f"{self.live_server_url}/http/200/r%C3%BCckmeldung/")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_200_utf8_not_encoded(self):
        uv = Url(url=f"{self.live_server_url}/http/200/rückmeldung/")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    @requests_mock.Mocker()
    def test_external_check_200_utf8_domain(self, mocker):
        mocker.register_uri('HEAD', 'https://xn--utf8-test--z5a0txc.example.com/', reason='OK'),
        uv = Url(url='https://utf8-test-äüö.example.com/')
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, True)
        self.assertEqual(uv.ssl_message, 'Valid SSL certificate')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    @requests_mock.Mocker()
    def test_external_check_200_punycode_domain(self, mocker):
        punycode_domain = 'https://xn--utf8-test--z5a0txc.example.com/'
        mocker.register_uri('HEAD', punycode_domain, reason='OK'),
        uv = Url(url=punycode_domain)
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, True)
        self.assertEqual(uv.ssl_message, 'Valid SSL certificate')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_301(self):
        uv = Url(url=f"{self.live_server_url}/http/301/")
        uv.check_url()
        self.assertEqual(uv.message, '301 Moved Permanently')
        self.assertEqual(uv.get_message, 'Broken permanent redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '301 Moved Permanently')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_301_followed(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect/301/")
        uv.check_url()
        self.assertEqual(uv.message, '301 Moved Permanently')
        self.assertEqual(uv.get_message, 'Working permanent redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '301 Moved Permanently')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, f'{self.live_server_url}/http/200/')
        self.assertEqual(uv.type, 'external')

    def test_external_check_302_followed(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect/302/")
        uv.check_url()
        self.assertEqual(uv.message, '302 Found')
        self.assertEqual(uv.get_message, 'Working temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, f'{self.live_server_url}/http/200/')
        self.assertEqual(uv.type, 'external')

    def test_external_check_404(self):
        uv = Url(url=f"{self.live_server_url}/whatever/")
        uv.check_url()
        self.assertEqual(uv.message, '404 Not Found')
        self.assertEqual(uv.get_message, 'Broken external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '404 Not Found')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_redirect_final_404(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect_to_404/")
        uv.check_url()
        self.assertEqual(uv.message, '404 Not Found')
        self.assertEqual(uv.get_message, 'Broken permanent redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '301 Moved Permanently')
        self.assertEqual(uv.get_redirect_status_code_display(), '404 Not Found')
        self.assertEqual(uv.redirect_to, f'{self.live_server_url}/http/404/')
        self.assertEqual(uv.type, 'external')

    def test_external_check_get_only_405(self):
        # An URL that allows GET but not HEAD, linkcheck should fallback on GET.
        uv = Url(url=f"{self.live_server_url}/http/getonly/405/")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_get_only_400(self):
        uv = Url(url=f"{self.live_server_url}/http/getonly/400/")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_blocked_user_agent(self):
        uv = Url(url=f"{self.live_server_url}/http/block-user-agent/")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_blocked_user_agent_blocked_head(self):
        uv = Url(url=f"{self.live_server_url}/http/block-user-agent/block-head/")
        uv.check_url()
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_timedout(self):
        uv = Url(url=f"{self.live_server_url}/timeout/")
        uv.check_url()
        self.assertEqual(uv.message, 'Other Error: The read operation timed out')
        self.assertEqual(uv.get_message, 'The read operation timed out')
        self.assertEqual(uv.error_message, 'The read operation timed out')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), None)
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_external_check_rate_limit(self):
        uv = Url(url=f"{self.live_server_url}/http/429/")
        uv.check_url()
        self.assertEqual(uv.last_checked, None)
        self.assertEqual(uv.message, '429 Too Many Requests')
        self.assertEqual(uv.get_message, 'Broken external link')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.anchor_message, '')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '429 Too Many Requests')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_working_external_anchor(self):
        uv = Url(url=f"{self.live_server_url}/http/anchor/#anchor")
        uv.check_url()
        self.assertEqual(uv.message, "200 OK, working external hash anchor")
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Working anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    @patch("linkcheck.models.TOLERATE_BROKEN_ANCHOR", False)
    def test_broken_external_anchor(self):
        uv = Url(url=f"{self.live_server_url}/http/anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.message, "200 OK, broken external hash anchor")
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_broken_external_anchor_tolerated(self):
        uv = Url(url=f"{self.live_server_url}/http/anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.message, "200 OK, broken external hash anchor")
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_redirect_working_external_anchor(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect_to_anchor/#anchor")
        uv.check_url()
        self.assertEqual(uv.message, "302 Found, working external hash anchor")
        self.assertEqual(uv.get_message, 'Working temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Working anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, f'{self.live_server_url}/http/anchor/')
        self.assertEqual(uv.type, 'external')

    @patch("linkcheck.models.TOLERATE_BROKEN_ANCHOR", False)
    def test_redirect_broken_external_anchor(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect_to_anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.message, "302 Found, broken external hash anchor")
        self.assertEqual(uv.get_message, 'Working temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, f'{self.live_server_url}/http/anchor/')
        self.assertEqual(uv.type, 'external')

    def test_redirect_broken_external_anchor_tolerated(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect_to_anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.message, "302 Found, broken external hash anchor")
        self.assertEqual(uv.get_message, 'Working temporary redirect')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Broken anchor')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '302 Found')
        self.assertEqual(uv.get_redirect_status_code_display(), '200 OK')
        self.assertEqual(uv.redirect_to, f'{self.live_server_url}/http/anchor/')
        self.assertEqual(uv.type, 'external')

    def test_video_with_time_anchor(self):
        uv = Url(url=f"{self.live_server_url}/static-files/video.mp4#t=2.0")
        uv.check_url()
        self.assertEqual(uv.message, "200 OK")
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Anchor could not be checked')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')

    def test_forged_video_with_time_anchor(self):
        uv = Url(url=f"{self.live_server_url}/static-files/fake-video.mp4#t=2.0")
        uv.check_url()
        self.assertEqual(uv.message, "200 OK, failed to parse HTML for anchor")
        self.assertEqual(uv.get_message, 'Working external link')
        self.assertEqual(uv.error_message, '')
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.anchor_message, 'Anchor could not be checked')
        self.assertEqual(uv.ssl_status, None)
        self.assertEqual(uv.ssl_message, 'Insecure link')
        self.assertEqual(uv.get_status_code_display(), '200 OK')
        self.assertEqual(uv.get_redirect_status_code_display(), None)
        self.assertEqual(uv.redirect_to, '')
        self.assertEqual(uv.type, 'external')


class ModelTestCase(TestCase):

    def test_str(self):
        Author.objects.create(name="John Smith", website="http://www.example.org/smith")
        self.assertEqual(
            str(Url.objects.first()),
            "http://www.example.org/smith",
        )
        self.assertEqual(
            str(Link.objects.first()),
            "http://www.example.org/smith (Author object (1))",
        )

    def test_repr(self):
        Author.objects.create(name="John Smith", website="http://www.example.org/smith")
        self.assertEqual(
            repr(Url.objects.first()),
            "<Url (id: 1, url: http://www.example.org/smith)>",
        )
        self.assertEqual(
            repr(Link.objects.first()),
            (
                "<Link (id: 1, url: <Url (id: 1, url: http://www.example.org/smith)>, "
                "source: <Author: Author object (1)>)>"
            ),
        )


class ChecklinksTestCase(TestCase):

    def test_checklinks_command(self):
        Book.objects.create(title='My Title', description="""
            Here's an external link: <a href="http://www.example.org">External</a>,
            an internal link: <a href="/public/">Internal</a>,
            and an image: <img src="http://www.example.org/logo.png" alt="logo">""")

        out = StringIO()
        call_command('checklinks', stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 10080 minutes.\n"
            "1 internal URLs and 0 external URLs have been checked.\n"
        )

        yesterday = datetime.now() - timedelta(days=1)
        Url.objects.all().update(last_checked=yesterday)
        out = StringIO()
        call_command('checklinks', externalinterval=20, stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 20 minutes.\n"
            "1 internal URLs and 2 external URLs have been checked.\n"
        )

        Url.objects.all().update(last_checked=yesterday)
        out = StringIO()
        call_command('checklinks', externalinterval=20, limit=1, stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 20 minutes.\n"
            "Will run maximum of 1 checks this run.\n"
            "1 internal URLs and 1 external URLs have been checked.\n"
        )


class FindingLinksTestCase(TestCase):
    def test_found_links(self):
        self.assertEqual(Url.objects.all().count(), 0)
        Book.objects.create(title='My Title', description="""
            Here's a link: <a href="http://www.example.org">Example</a>,
            and an image: <img src="http://www.example.org/logo.png" alt="logo">""")
        self.assertEqual(Url.objects.all().count(), 2)
        self.assertQuerySetEqual(
            Url.objects.all().order_by('url'),
            ["http://www.example.org", "http://www.example.org/logo.png"],
            transform=lambda obj: obj.url
        )

    def test_urls_exceeding_max_length(self):
        self.assertEqual(Url.objects.all().count(), 0)
        with self.assertLogs(logger="linkcheck", level="WARN") as cm:
            Book.objects.create(
                title="My Title",
                description=(
                    "Here's a link: <a href='http://www.example.org'>Example</a>, and here's a url exceeding "
                    f"the max length: <img src='http://www.example.org/{MAX_URL_LENGTH * 'X'}' alt='logo'>"
                ),
            )
        # We skip urls which are too long because we can't store them in the database
        self.assertIn(
            (
                "WARNING:linkcheck.listeners:URL exceeding max length will be skipped: "
                f"http://www.example.org/{MAX_URL_LENGTH * 'X'}"
            ),
            cm.output,
        )
        self.assertEqual(Url.objects.all().count(), 1)

    def test_empty_url_field(self):
        """
        Test that URLField empty content is excluded depending on ignore_empty list.
        """
        all_linklists = apps.get_app_config('linkcheck').all_linklists
        all_linklists['Authors'].ignore_empty = ['website']
        try:
            Author.objects.create(name="William Shakespeare")
            Author.objects.create(name="John Smith", website="http://www.example.org/smith")
            self.assertEqual(Url.objects.all().count(), 1)
        finally:
            all_linklists['Authors'].ignore_empty = []
        Author.objects.create(name="Alphonse Daudet")
        # This time, the empty 'website' is extracted
        self.assertEqual(Url.objects.all().count(), 2)

    def test_findlinks_command(self):
        # Disable listeners to only check the management command
        with disable_listeners():
            Author.objects.create(name="John Smith", website="https://www.example.org/smith")
            self.assertEqual(
                findlinks(),
                "Updating all links...\n"
                "Urls: 1 created, 0 deleted, 0 unchanged\n"
                "Links: 1 created, 0 deleted, 0 unchanged\n"
            )
            Author.objects.create(name="John Doe", website="https://www.example.org/doe")
            Book.objects.create(
                title='My Title',
                description="My fav author: <a href='https://www.example.org/doe'>John Doe</a>"
            )
            self.assertEqual(
                findlinks(),
                "Updating all links...\n"
                "Urls: 1 created, 0 deleted, 1 unchanged\n"
                "Links: 2 created, 0 deleted, 1 unchanged\n"
            )
            Author.objects.get(name="John Doe").delete()
            self.assertEqual(
                findlinks(),
                "Updating all links...\n"
                "Urls: 0 created, 0 deleted, 2 unchanged\n"
                "Links: 0 created, 1 deleted, 2 unchanged\n"
            )
            Book.objects.first().delete()
            self.assertEqual(
                findlinks(),
                "Updating all links...\n"
                "Urls: 0 created, 1 deleted, 1 unchanged\n"
                "Links: 0 created, 1 deleted, 1 unchanged\n"
            )


class ManagementCommandTestCase(TestCase):

    def test_linkcheck_suggest_config(self):
        """
        Test that the config of uncovered models is correctly suggested
        """
        out, err = get_command_output('linkcheck_suggest_config')
        self.assertEqual(
            out,
            'All covered models:\n'
            '\x1b[36msampleapp.Book\x1b[0m, \x1b[36msampleapp.Page\x1b[0m\n\n'
            'Suggested config for model sampleapp.UncoveredModel:\n'
            '\x1b[36mfrom sampleapp.models import UncoveredModel\n\n'
            'class UncoveredModelLinklist(Linklist):\n'
            '    model = UncoveredModel\n\n'
            'linklists = {\n'
            '    "UncoveredModel": UncoveredModelLinklist,\n'
            '}\n\x1b[0m\n'
        )
        self.assertEqual(err, '')

    def test_linkcheck_suggest_config_model(self):
        """
        Test that the config of given model is correctly printed
        """
        out, err = get_command_output('linkcheck_suggest_config', '--model', 'sampleapp.Author')
        self.assertEqual(
            out,
            'from sampleapp.models import Author\n\n'
            'class AuthorLinklist(Linklist):\n'
            '    model = Author\n\n'
            'linklists = {\n'
            '    "Author": AuthorLinklist,\n'
            '}\n'
        )
        self.assertEqual(err, '')

    def test_linkcheck_suggest_config_model_non_existing(self):
        """
        Test that the command raises an error when the model does not exist
        """
        with self.assertRaises(CommandError) as cm:
            get_command_output('linkcheck_suggest_config', '--model', 'non-existing')
        self.assertEqual(str(cm.exception), 'Model "non-existing" does not exist.')


class ObjectsUpdateTestCase(TestCase):
    def test_update_object(self):
        """
        Test that updating a broken URL in an object also updates the
        corresponding Link, and don't leak the old URL.
        """
        bad_url = "/broken/internal/link"
        good_url = "/public/"
        author = Author.objects.create(name="John Smith", website=bad_url)
        self.assertEqual(
            Link.objects.filter(ignore=False, url__status=False).count(),
            1
        )
        self.assertEqual(
            Link.objects.filter(ignore=False, url__status=True).count(),
            0
        )
        self.assertEqual(Url.objects.all().count(), 1)
        self.assertEqual(Url.objects.all()[0].url, bad_url)
        # Fix the link
        author.website = good_url
        author.save()
        self.assertEqual(
            Link.objects.filter(ignore=False, url__status=False).count(),
            0
        )
        self.assertEqual(
            Link.objects.filter(ignore=False, url__status=True).count(),
            1
        )
        self.assertEqual(Url.objects.all().count(), 1)
        self.assertEqual(Url.objects.all()[0].url, good_url)


class RegisteringTests(TestCase):
    good_url = "/public/"

    def test_unregister(self):
        self.assertEqual(Link.objects.count(), 0)
        unregister_listeners()
        Author.objects.create(name="John Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 0)
        register_listeners()
        Author.objects.create(name="Jill Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 1)

    def test_disable_listeners(self):
        self.assertEqual(Link.objects.count(), 0)
        with disable_listeners():
            Author.objects.create(name="John Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 0)
        Author.objects.create(name="Jill Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 1)

    def test_enable_listeners(self):
        self.assertEqual(Link.objects.count(), 0)
        unregister_listeners()
        with enable_listeners():
            Author.objects.create(name="John Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 1)
        Author.objects.create(name="Jill Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 1)
        register_listeners()


class QueueTests(TestCase):
    def test_queue_handling_continue_on_task_crash(self):
        assert tasks_queue.empty() is True

        def raising():
            raise RuntimeError("Failing task")

        def passing():
            pass

        for func in (raising, passing):
            tasks_queue.put({
                'target': func,
                'args': (),
                'kwargs': {},
            })
        with self.assertLogs() as cm:
            linkcheck_worker(block=False)
        self.assertEqual(
            cm.output[0].split('\n')[0],
            'ERROR:linkcheck.listeners:RuntimeError while running raising with '
            'args=() and kwargs={}: Failing task'
        )


class ViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'admin@example.org', 'password')

    def test_display_url(self):
        Book.objects.create(
            title='My Title', description="Here's a link: <a href='http://www.example.org'>Example</a>"
        )
        Author.objects.create(name="John Smith", website="http://www.example.org#john")
        self.assertEqual(Link.objects.count(), 2)
        self.assertEqual(
            set([link.display_url for link in Link.objects.all()]),
            set(["http://www.example.org", "http://www.example.org#john"]),
        )

    def test_report_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('linkcheck_report'))
        self.assertContains(response, "<h1>Link Checker</h1>")

    def test_report_ignore_unignore(self):
        Author.objects.create(name="John Smith", website="http://www.example.org/john")
        self.client.force_login(self.user)
        link = Link.objects.first()
        self.assertFalse(link.ignore)
        response = self.client.post(
            reverse('linkcheck_report') + f"?ignore={link.pk}",
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json(), {'link': link.pk})
        link.refresh_from_db()
        self.assertTrue(link.ignore)
        response = self.client.post(
            reverse('linkcheck_report') + f"?unignore={link.pk}",
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json(), {'link': link.pk})
        link.refresh_from_db()
        self.assertFalse(link.ignore)

    def test_report_recheck(self):
        Author.objects.create(name="John Smith", website="http://www.example.org/john")
        self.client.force_login(self.user)
        link = Link.objects.first()
        response = self.client.post(
            reverse('linkcheck_report') + f"?recheck={link.pk}",
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json(), {
            'colour': 'red',
            'links': [link.pk],
            'message': '404 Not Found',
        })


class GetJqueryMinJsTestCase(TestCase):
    def test(self):
        self.assertEqual(
            'admin/js/vendor/jquery/jquery.min.js', get_jquery_min_js()
        )


class FixtureTestCase(TestCase):
    fixtures = ['linkcheck/tests/sampleapp/fixture.json']

    def test_fixture(self):
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(Page.objects.count(), 1)


class FilterCallableTestCase(TestCase):
    def test_filter_callable(self):
        all_linklists = apps.get_app_config('linkcheck').all_linklists
        all_linklists['Journals'].html_fields = []
        Journal.objects.create(title='My Title', description="""
            My description <a href="http://www.example.org">Example</a>""")
        Journal.objects.create(title='My Title', version=1, description="""
            My new description <a href="http://www.example.org">Example</a>""")
        all_linklists['Journals'].html_fields = ['description']
        # assert there are two versions of the same journal
        self.assertEqual(Journal.objects.count(), 2)
        # assert command just finds the latest version of same journals
        self.assertEqual(
            findlinks(),
            "Updating all links...\n"
            "Urls: 1 created, 0 deleted, 0 unchanged\n"
            "Links: 1 created, 0 deleted, 0 unchanged\n"
        )


def get_command_output(command, *args, **kwargs):
    """
    Helper function for running a management command and checking its output
    """
    out = StringIO()
    err = StringIO()
    call_command(command, *args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


def findlinks():
    """
    Helper function for running the findlinks command and checking its output
    """
    return get_command_output('findlinks')[0]
