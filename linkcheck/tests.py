import unittest
#from urllib2 import HTTPError
import urllib2
import socket
import re

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
        

    
#replace urllib2.urlopen with mock method
urllib2.urlopen = mock_urlopen

from linkcheck.models import Url

class CheckTestCase(unittest.TestCase):
    def test_internal_check_mailto(self):
        uv = Url(url="mailto:nobody", still_exists=True)
        uv.check()
        self.assertEquals(uv.status, None)
        self.assertEquals(uv.message, 'Email link (not automatically checked)')

    def test_internal_check_blank(self):
        uv = Url(url="", still_exists=True)
        uv.check()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Empty link')

    def test_internal_check_anchor(self):
        uv = Url(url="#some_anchor", still_exists=True)
        uv.check()
        self.assertEquals(uv.status, None)
        self.assertEquals(uv.message, 'Link to within the same page (not automatically checked)')

    def test_internal_check_media_missing(self):
        uv = Url(url="/media/not_found", still_exists=True)
        uv.check()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Missing Document')

#   TODO: WRITE TEST
#    def test_internal_check_media_found(self):
#        uv = Url(url="/media/not_found", still_exists=True)
#        self.assertEquals(uv.status, True)
#        self.assertEquals(uv.message, 'Working document link')

    def test_internal_check_view_302(self):
        uv = Url(url="/admin/linkcheck", still_exists=True)
        uv.check()
        self.assertEquals(uv.status, None)
        self.assertEquals(uv.message, 'This link redirects: code 302 (not automatically checked)')

#   TODO: WRITE TEST that will not return 302 from Client
#    def test_internal_check_admin_found(self):
#        uv = Url(url="/admin", still_exists=True)
#        self.assertEquals(uv.status, True)
#        self.assertEquals(uv.message, 'Working document link')

    def test_internal_check_broken_internal_link(self):
        uv = Url(url="/broken/internal/link", still_exists=True)
        uv.check()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Broken internal link')

    def test_internal_check_invalid_url(self):
        uv = Url(url="invalid/url", still_exists=True)
        uv.check()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, 'Invalid URL')

    def test_external_check_404(self):
        uv = Url(url="http://localhost/404", still_exists=True)
        uv.check()
        self.assertEquals(uv.status, False)
        self.assertEquals(uv.message, "Unreachable: (61, 'Connection refused')")

    def test_same_page_anchor(self):
        # TODO Make this test
        pass
        #uv = Url(url="#anchor", still_exists=True)
        #uv.check()
        #self.assertEquals(uv.status, None)
        #self.assertEquals(uv.message, "")

    def test_external_check_200(self):
        # TODO fix this test
        pass
        #uv = Url(url="http://localhost/200", still_exists=True)
        #uv.check()
        #self.assertEquals(uv.status, True)
        #self.assertEquals(uv.message, '200 OK')


    def test_external_check_301(self):
        # TODO fix this test
        pass
        #uv = Url(url="http://localhost/301", still_exists=True)
        #uv.check()
        #self.assertEquals(uv.status, False)
        #self.assertEquals(uv.message, '301 Moved Permanently')
