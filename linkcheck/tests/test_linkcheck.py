# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime, timedelta
import os
import re
import socket

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.urlresolvers import reverse
from django.test import LiveServerTestCase, TestCase
from django.test.utils import override_settings
from django.utils.six import StringIO
from django.utils.six.moves.urllib import request
from django.utils.six.moves.urllib.error import HTTPError

from linkcheck.models import Link, Url

from .sampleapp.models import Author, Book


#MOCK addinfurl
class addinfourl():
    """class to add info() and geturl(url=) methods to an open file."""

    def __init__(self, url, code, msg):
        self.headers = None
        self.url = url
        self.code = code
        self.msg  = msg

    def info(self):
        return self.headers

    def getcode(self):
        return self.code

    def geturl(self):
        return self.url

#
# Mock Method so test can run independently
#

# Fix for Python<2.6
try:
    timeout = socket._GLOBAL_DEFAULT_TIMEOUT
except AttributeError:
    timeout = 1000

def mock_urlopen(url, data=None, timeout=timeout):
    msg_dict = {'301': "Moved Permanently", '404': 'Not Found', '200': 'OK'}

    code = '404'
    msg  = msg_dict.get(code)

    m = re.search("([0-9]*)$", url)
    if m:
        code = m.group(0)
        msg  = msg_dict.get(code, 'Something Happened')
        if code == "200":
            return addinfourl(url, code, msg)

    raise HTTPError(url, code, msg, None, None)


class InternalCheckTestCase(TestCase):
    urls = 'linkcheck.tests.urls'

    def setUp(self):
        #replace urllib2.urlopen with mock method
        request.urlopen = mock_urlopen

    def test_internal_check_mailto(self):
        uv = Url(url="mailto:nobody", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, None)
        self.assertEqual(uv.message, 'Email link (not automatically checked)')

    def test_internal_check_blank(self):
        uv = Url(url="", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Empty link')

    def test_internal_check_anchor(self):
        uv = Url(url="#some_anchor", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, None)
        self.assertEqual(uv.message, 'Link to within the same page (not automatically checked)')

    def test_internal_check_view_301(self):
        uv = Url(url="/admin/linkcheck", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, None)
        self.assertEqual(uv.message, 'This link redirects: code 301 (not automatically checked)')

    def test_internal_check_found(self):
        uv = Url(url="/public/", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working internal link')

    def test_internal_check_broken_internal_link(self):
        uv = Url(url="/broken/internal/link", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Broken internal link')

    def test_internal_check_invalid_url(self):
        uv = Url(url="invalid/url", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Invalid URL')

    def test_same_page_anchor(self):
        # TODO Make this test
        pass
        #uv = Url(url="#anchor", still_exists=True)
        #uv.check_url()
        #self.assertEqual(uv.status, None)
        #self.assertEqual(uv.message, "")


class InternalMediaCheckTestCase(TestCase):
    def setUp(self):
        self.old_media_root = settings.MEDIA_ROOT
        settings.MEDIA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media')

    def tearDown(self):
        settings.MEDIA_ROOT = self.old_media_root

    def test_internal_check_media_missing(self):
        uv = Url(url="/media/not_found", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Missing Document')

    def test_internal_check_media_found(self):
        uv = Url(url="/media/found", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working file link')

    def test_internal_check_media_utf8(self):
        uv = Url(url="/media/r%C3%BCckmeldung", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working file link')
        # Also when the url is not encoded
        uv = Url(url="/media/rückmeldung", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working file link')


@override_settings(SITE_DOMAIN='example.com')
class ExternalCheckTestCase(LiveServerTestCase):
    def test_external_check_200(self):
        uv = Url(url="%s/http/200/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_200_utf8(self):
        uv = Url(url="%s/http/200/r%%C3%%BCckmeldung/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')
        # Also when the url is not encoded
        uv = Url(url="%s/http/200/rückmeldung/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')

    def test_external_check_301(self):
        uv = Url(url="%s/http/301/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message.lower(), '301 moved permanently')

    def test_external_check_301_followed(self):
        uv = Url(url="%s/http/redirect/301/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '301 OK')
        self.assertEqual(uv.redirect_to, '%s/http/200/' % self.live_server_url)

    def test_external_check_302_followed(self):
        """
        For temporary redirects, we do not report any redirection in `redirect_to`.
        """
        uv = Url(url="%s/http/redirect/302/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_404(self):
        uv = Url(url="%s/whatever/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message.lower(), '404 not found')


class ChecklinksTestCase(TestCase):
    def setUp(self):
        request.urlopen = mock_urlopen

    def test_checklinks_command(self):
        Book.objects.create(title='My Title', description="""
            Here's a link: <a href="http://www.example.org">Example</a>,
            and an image: <img src="http://www.example.org/logo.png" alt="logo">""")

        out = StringIO()
        call_command('checklinks', stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 10080 minutes.\n"
            "0 internal URLs and 0 external URLs have been checked.\n"
        )

        yesterday = datetime.now() - timedelta(days=1)
        Url.objects.all().update(last_checked=yesterday)
        out = StringIO()
        call_command('checklinks', externalinterval=20, stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 20 minutes.\n"
            "0 internal URLs and 2 external URLs have been checked.\n"
        )

        Url.objects.all().update(last_checked=yesterday)
        out = StringIO()
        call_command('checklinks', externalinterval=20, limit=1, stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 20 minutes.\n"
            "Will run maximum of 1 checks this run.\n"
            "0 internal URLs and 1 external URLs have been checked.\n"
        )


class FindingLinksTestCase(TestCase):
    def test_found_links(self):
        self.assertEqual(Url.objects.all().count(), 0)
        Book.objects.create(title='My Title', description="""
            Here's a link: <a href="http://www.example.org">Example</a>,
            and an image: <img src="http://www.example.org/logo.png" alt="logo">""")
        self.assertEqual(Url.objects.all().count(), 2)
        self.assertQuerysetEqual(
            Url.objects.all().order_by('url'),
            ["<Url: http://www.example.org>", "<Url: http://www.example.org/logo.png>"]
        )

    def test_empty_url_field(self):
        """
        Test that URLField empty content is excluded depending on ignore_empty list.
        """
        from linkcheck.models import all_linklists
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
        from linkcheck.models import all_linklists
        all_linklists['Authors'].url_fields = []
        Author.objects.create(name="John Smith", website="http://www.example.org/smith")
        all_linklists['Authors'].url_fields = ['website']

        out = StringIO()
        call_command('findlinks', stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Finding all new links...\n"
            "1 new Url object(s), 1 new Link object(s), 0 Url object(s) deleted\n"
        )


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


class ReportViewTestCase(TestCase):
    def setUp(self):
        User.objects.create_superuser('admin', 'admin@example.org', 'password')

    def test_display_url(self):
        Book.objects.create(title='My Title', description="""Here's a link: <a href="http://www.example.org">Example</a>""")
        Author.objects.create(name="John Smith", website="http://www.example.org#john")
        self.assertEqual(Link.objects.count(), 2)
        self.assertEqual(
            set([l.display_url for l in Link.objects.all()]),
            set(['http://www.example.org', 'http://www.example.org#john'])
        )

    def test_report_view(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('linkcheck_report'))
        self.assertContains(response, "<h1>Link Checker</h1>")
