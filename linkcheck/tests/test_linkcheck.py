from datetime import datetime, timedelta
from io import StringIO
from unittest import skipIf
from urllib import request
from urllib.error import HTTPError
import os
import re

import django
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import LiveServerTestCase, TestCase
from django.test.utils import override_settings
from django.urls import reverse

from linkcheck.listeners import (
    enable_listeners, disable_listeners, register_listeners, unregister_listeners,
)
from linkcheck.models import Link, Url
from linkcheck.views import get_jquery_min_js

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

def mock_urlopen(url, data=None, **kwargs):
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


@override_settings(ROOT_URLCONF='linkcheck.tests.urls')
class InternalCheckTestCase(TestCase):

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

    def test_internal_check_view_redirect(self):
        uv = Url(url="/admin/linkcheck", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertIn(uv.message,
            ['This link redirects: code %s (Working redirect)' % status for status in [301, 302]]
        )
        uv = Url(url="/http/brokenredirect/", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'This link redirects: code 302 (Broken redirect)')

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
        media_file = os.path.join(os.path.dirname(__file__), 'media', 'rückmeldung')
        open(media_file, 'a').close()
        self.addCleanup(os.remove, media_file)
        uv = Url(url="/media/r%C3%BCckmeldung", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working file link')
        # Also when the url is not encoded
        uv = Url(url="/media/rückmeldung", still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working file link')


# See https://code.djangoproject.com/ticket/29849 (fixed in Django 2.1+)
@skipIf(django.VERSION[:2]==(2, 0), 'LiveServerTestCase is broken on Django 2.0.x')
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
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_301_followed(self):
        uv = Url(url="%s/http/redirect/301/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '301 Moved Permanently')
        self.assertEqual(uv.redirect_to, '%s/http/200/' % self.live_server_url)

    def test_external_check_302_followed(self):
        uv = Url(url="%s/http/redirect/302/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '302 Found')
        self.assertEqual(uv.redirect_to, '%s/http/200/' % self.live_server_url)

    def test_external_check_404(self):
        uv = Url(url="%s/whatever/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message.lower(), '404 not found')

    def test_external_check_redirect_final_404(self):
        uv = Url(url="%s/http/redirect_to_404/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message.lower(), '404 not found')

    def test_external_check_get_only(self):
        # An URL that allows GET but not HEAD, linkcheck should fallback on GET.
        uv = Url(url="%s/http/getonly/405/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')
        # Same test with other 40x error
        uv = Url(url="%s/http/getonly/400/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')

    def test_external_check_timedout(self):
        uv = Url(url="%s/timeout/" % self.live_server_url, still_exists=True)
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Other Error: The read operation timed out')


class ChecklinksTestCase(TestCase):
    def setUp(self):
        request.urlopen = mock_urlopen

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
        self.assertQuerysetEqual(
            Url.objects.all().order_by('url'),
            ["<Url: http://www.example.org>", "<Url: http://www.example.org/logo.png>"]
        )

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
        all_linklists = apps.get_app_config('linkcheck').all_linklists
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


class ViewTestCase(TestCase):
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

    def test_coverage_view(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('linkcheck_coverage'))
        self.assertContains(
            response,
            '<tr><td>sampleapp.Book</td>'
            '<td style="font-weight: bold;color:green;">True</td>'
            '<td style="font-weight: bold;color:green;"></td></tr>',
            html=True,
        )


class GetJqueryMinJsTestCase(TestCase):
    def test(self):
        self.assertEqual(
            'admin/js/vendor/jquery/jquery.min.js', get_jquery_min_js()
        )


class FixtureTestCase(TestCase):
    fixtures = ['linkcheck/tests/sampleapp/fixture.json']

    def test_fixture(self):
        self.assertEqual(Book.objects.count(), 1)
