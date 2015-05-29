import urllib2
import socket
import re
import os

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

    raise urllib2.HTTPError(url, code, msg, None, None)

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase
from linkcheck.models import Url

class InternalCheckTestCase(TestCase):
    urls = 'linkcheck.tests.test_urls'

    def setUp(self):
        #replace urllib2.urlopen with mock method
        urllib2.urlopen = mock_urlopen

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
        from linkcheck.tests.sampleapp.models import Book
        self.assertEqual(Url.objects.all().count(), 0)
        Book.objects.create(title='My Title', description="""Here's a link: <a href="http://www.example.org">Example</a>""")
        self.assertEqual(Url.objects.all().count(), 1)
        self.assertEqual(Url.objects.all()[0].url, "http://www.example.org")

class ReportViewTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('admin', 'admin@example.org', 'password')

    def test_report_view(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('linkcheck.views.report'))
        self.assertContains(response, "<h1>Link Checker</h1>")
