import socket
import re
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.utils.six import StringIO
from django.utils.six.moves.urllib import request
from django.utils.six.moves.urllib.error import HTTPError

from linkcheck.models import Link, Url

from .sampleapp.models import Author, Book


#MOCK addinfurl
class addinfoUrl():
    """class to add info() and getUrl(url=) methods to an open file."""

    def __init__(self, url, code, msg):
        self.headers = None
        self.url = url
        self.code = code
        self.msg  = msg

    def info(self):
        return self.headers

    def getcode(self):
        return self.code

    def getUrl(self):
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
            return addinfoUrl(url, code, msg)

    raise HTTPError(url, code, msg, None, None)


class InternalCheckTestCase(TestCase):
    urls = 'linkcheck.tests.test_urls'

    def setUp(self):
        #replace urllib2.urlopen with mock method
        request.urlopen = mock_urlopen

    def test_internal_check_mailto(self):
        uv = Url(url="mailto:nobody", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, None)
        self.assertEquals(uv.message, 'Email link (not automatically checked)')

    def test_internal_check_blank(self):
        uv = Url(url="", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Empty link')

    def test_internal_check_anchor(self):
        uv = Url(url="#some_anchor", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, None)
        self.assertEquals(uv.message, 'Link to within the same page (not automatically checked)')

#    TODO: This now fails, because with follow=True, redirects are automatically followed
#    def test_internal_check_view_302(self):
#        uv = Url(url="/admin/linkcheck", still_exists=True)
#        uv.check_url()
#        self.assertEquals(uv.status, None)
#        self.assertEquals(uv.message, 'This link redirects: code 302 (not automatically checked)')

    def test_internal_check_admin_found(self):
        uv = Url(url="/admin/", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, True)
        self.assertEquals(uv.message, 'Working internal link')

    def test_internal_check_broken_internal_link(self):
        uv = Url(url="/broken/internal/link", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Broken internal link')

    def test_internal_check_invalid_url(self):
        uv = Url(url="invalid/url", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Invalid URL')

    def test_same_page_anchor(self):
        # TODO Make this test
        pass
        #uv = Url(url="#anchor", still_exists=True)
        #uv.check_url()
        #self.assertEquals(uv.status, None)
        #self.assertEquals(uv.message, "")


class InternalMediaCheckTestCase(TestCase):
    def setUp(self):
        self.old_media_root = settings.MEDIA_ROOT
        settings.MEDIA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media')

    def tearDown(self):
        settings.MEDIA_ROOT = self.old_media_root

    def test_internal_check_media_missing(self):
        uv = Url(url="/media/not_found", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Missing Document')

    def test_internal_check_media_found(self):
        uv = Url(url="/media/found", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, True)
        self.assertEquals(uv.message, 'Working file link')

    def test_internal_check_media_utf8(self):
        uv = Url(url="/media/r%C3%BCckmeldung", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, True)
        self.assertEquals(uv.message, 'Working file link')


class ExternalCheckTestCase(TestCase):
    def test_external_check_200(self):
        uv = Url(url="http://qa-dev.w3.org/link-testsuite/http.php?code=200", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, True)
        self.assertEquals(uv.message, '200 OK')

    def test_external_check_301(self):
        uv = Url(url="http://qa-dev.w3.org/link-testsuite/http.php?code=301", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, '301 Moved Permanently')

    def test_external_check_404(self):
        uv = Url(url="http://qa-dev.w3.org/link-testsuite/http.php?code=404", still_exists=True)
        uv.check_url()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, '404 Not Found')


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
        response = self.client.get(reverse('linkcheck.views.report'))
        self.assertContains(response, "<h1>Link Checker</h1>")
