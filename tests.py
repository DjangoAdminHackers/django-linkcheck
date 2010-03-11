import unittest
#from urllib2 import HTTPError
import urllib2
from django.conf import settings
import socket
import re

#MOCK addinfurl
class addinfourl():
    """class to add info() and geturl() methods to an open file."""

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
        
    raise urllib2.HTTPError(url, code, msg, None, None)
        

    
#replace urllib2.urlopen with mock method
urllib2.urlopen = mock_urlopen

from linkcheck.utils import UrlValidator

class CheckTestCase(unittest.TestCase):
    def test_internal_check_mailto(self):
        uv = UrlValidator("mailto:nobody").verify_internal()
        self.assertEquals(uv.status, None)
        self.assertEquals(uv.message, 'Email link (not checked)')

    def test_internal_check_blank(self):
        uv = UrlValidator("").verify_internal()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Empty link')

    def test_internal_check_null(self):
        url = None
        uv = UrlValidator(url).verify_internal()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Empty link')

    def test_internal_check_anchor(self):
        uv = UrlValidator("#some_anchor").verify_internal()
        self.assertEquals(uv.status, None)
        self.assertEquals(uv.message, 'Link to same page (not checked)')

    def test_internal_check_media_missing(self):
        uv = UrlValidator("/media/not_found").verify_internal()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Missing Document')

#   TODO: WRITE TEST
#    def test_internal_check_media_found(self):
#        uv = UrlValidator("/media/not_found").verify_internal()
#        self.assertEquals(uv.status, True)
#        self.assertEquals(uv.message, 'Working document link')

    def test_internal_check_view_302(self):
        uv = UrlValidator("/admin/linkcheck").verify_internal()
        self.assertEquals(uv.status, None)
        self.assertEquals(uv.message, 'Redirect 302')

#   TODO: WRITE TEST that will not return 302 from Client
#    def test_internal_check_admin_found(self):
#        uv = UrlValidator("/admin").verify_internal()
#        self.assertEquals(uv.status, True)
#        self.assertEquals(uv.message, 'Working document link')

    def test_internal_check_broken_internal_link(self):
        uv = UrlValidator("/broken/internal/link").verify_internal()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Broken internal link')

    def test_internal_check_invalid_url(self):
        uv = UrlValidator("invalid/url").verify_internal()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Invalid URL')

    def test_external_check_404(self):
        uv = UrlValidator("http://localhost/404").verify_external()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, '404 Not Found')

    def test_external_check_200(self):
        uv = UrlValidator("http://localhost/200").verify_external()
        self.assertEquals(uv.status, True)
        self.assertEquals(uv.message, '200 OK')

    def test_external_check_301(self):
        uv = UrlValidator("http://localhost/301").verify_external()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, '301 Moved Permanently')
