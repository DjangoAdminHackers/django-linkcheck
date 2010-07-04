import os.path
from datetime import datetime, timedelta
from urllib2 import urlopen, URLError, HTTPError

from django.conf import settings
from django.db import connection
from django.test.client import Client
from django.test.client import ClientHandler

from linkcheck.models import Link, Url

#This needs some kind of autodiscovery mechanism
from linkcheck.models import all_linklists
from linkcheck.settings import SITE_DOMAINS

import logging
log = logging.getLogger('linkcheck.utils')

class LinkCheckHandler(ClientHandler):
    #customize the ClientHandler to allow us removing some middlewares

    def load_middleware(self):
        self.ignore_keywords = ['reversion.middleware','CommonMiddleware','MaintenanceModeMiddleware']
        super(LinkCheckHandler, self).load_middleware()
        new_request_middleware = []

        #############################_request_middleware#################################
        for method in self._request_middleware:
            ignored = False
            for keyword in self.ignore_keywords:
                if method.__str__().count(keyword):
                    ignored = True
                    break
            if not ignored:
                new_request_middleware.append(method)
        self._request_middleware = new_request_middleware

        #############################_view_middleware#################################
        new_view_middleware = []
        for method in self._view_middleware:
            ignored = False
            for keyword in self.ignore_keywords:
                if method.__str__().count(keyword):
                    ignored = True
                    break
            if not ignored:
                new_view_middleware.append(method)
        self._view_middleware = new_view_middleware

        #############################_response_middleware#################################
        new_response_middleware = []
        for method in self._response_middleware:
            ignored = False
            for keyword in self.ignore_keywords:
                if method.__str__().count(keyword):
                    ignored = True
                    break
            if not ignored:
                new_response_middleware.append(method)
        self._response_middleware = new_response_middleware

        #############################_exception_middleware#################################
        new_exception_middleware = []
        for method in self._exception_middleware:
            ignored = False
            for keyword in self.ignore_keywords:
                if method.__str__().count(keyword):
                    ignored = True
                    break
            if not ignored:
                new_exception_middleware.append(method)
        self._exception_middleware = new_exception_middleware

def check(internal_recheck_interval, external_recheck_interval, limit):
    check_internal_links(internal_recheck_interval, limit)
    check_external_links(external_recheck_interval, limit)

def check_link(u, external=False):
    if external:
        uv = UrlValidator(u.url).verify_external()
    else:
        uv = UrlValidator(u.url).verify_internal()
    u.status        = uv.status
    u.message       = uv.message
    u.last_checked  = datetime.now()
    u.save()
    
def check_internal_links(internal_recheck_interval=300, limit=None):
    compare_date = datetime.now() - timedelta(seconds=internal_recheck_interval)

    #select urls where still_exists = True AND last_checked <= compare_date AND DOES NOT begin with http:// or https://

    urls = Url.objects.filter(still_exists__exact='TRUE').exclude(last_checked__gt=compare_date).exclude(url__regex=r'^https?://')
    #if limit is specified set the limit
    if limit and limit > -1:
        urls = urls[:limit]

    for u in urls:
        check_link(u, external=False)

def check_external_links(external_recheck_interval=86400, limit=None):
    compare_date = datetime.now() - timedelta(seconds=external_recheck_interval)

    #select Urls which begin with (http:// or https://) and still_exists=TRUE AND last_checked lt compare date
    urls = Url.objects.filter(url__regex=r'https?://', still_exists__exact='TRUE').exclude(last_checked__gt=compare_date)

    #if limit is specified set the limit
    if limit and limit > -1:
        urls = urls[:limit]

    for u in urls:
        check_link(u, external=True)

def update_urls(urls, content_type, object_id):
    # url structure = (field, link text, url)
    for url in urls:
        url = url[2]
        if url.startswith('#'):
            url = instance.get_absolute_url() + url
        u, created = Url.objects.get_or_create(url=url)
        l, created = Link.objects.get_or_create(url=u, field=url[0], text=url[1], content_type=content_type, object_id=object_id)
        u.still_exists = True
        u.save()

def find_all_links(all_linklists):
    all_links_dict = {}
    Url.objects.all().update(still_exists=False)
    for linklist_name, linklist_cls in all_linklists.items():
        content_type = linklist_cls.content_type()
        linklists = linklist_cls().get_linklist()
        for linklist in linklists:
            object_id = linklist['object'].id
            urls = linklist['urls']+linklist['images']
            if urls:
                update_urls(urls, content_type, object_id)
        all_links_dict[linklist_name] = linklists
    Url.objects.filter(still_exists=False).delete()

class UrlValidator():
    def __init__(self, uri, **kwargs):
        self.uri     = uri
        self.status  = False
        self.message = "Not Tested"
        self.page = kwargs.pop('instance', None)

    def verify_internal(self):
        self.status = False
        self.message = 'Invalid URL'
        try:
            if not self.uri:
                self.message = 'Empty link'
            elif self.uri.startswith('mailto:'):
                self.status = None
                self.message = 'Email link (not checked)'
            elif self.uri.startswith('#'):
                self.status = None
                self.message = 'Link to same page (not checked)'
            elif self.uri.startswith('/media/'): #TODO fix hard-coded media self.uri
                if os.path.exists(settings.MEDIA_ROOT+self.uri[6:]): #TODO fix hard-coded media prefix length
                    self.message = 'Working document link'
                    self.status = True
                else:
                    self.message = 'Missing Document'
            elif self.uri.startswith('/'):
                c = Client()
                c.handler = LinkCheckHandler()
                response = c.get(self.uri, follow=True)
                if response.status_code == 200:
                    self.message = 'Working internal link'
                    self.status = True
                    if self.uri.count('#'):
                        anchor = self.uri.split('#')[1]
                        log.critical('anchor: %s' % anchor)
                        from linkcheck import parse_anchors
                        names = parse_anchors(response.content)
                        log.critical('names: %s' % names)
                        if anchor in names:
                            self.message = 'Working internal hash anchor'
                            self.status = True
                        else:
                            self.message = 'Broken internal hash anchor'
                            self.status = False

                elif (response.status_code == 302 or response.status_code == 301):
                    self.status = None
                    self.message = 'Redirect %d' % (response.status_code, )
                else:
                    self.message = 'Broken internal link'
        except:
            pass
        
        return self

    def verify_external(self):
        self.status = False
        internal_exceptions = SITE_DOMAINS
        for ex in internal_exceptions:
            if ex and self.uri.startswith(ex):
                self.uri = self.uri.replace(ex, '', 1)
                return self.verify_internal()
        try:
            response = urlopen(self.uri.rsplit('#')[0]) # Remove URL fragment identifiers
            self.message = ' '.join([str(response.code), response.msg])
            self.status = True
            if self.uri.count('#'):
                anchor = self.uri.split('#')[1]
                from linkcheck import parse_anchors
                names = parse_anchors(response.read())
                if anchor in names:
                    self.message = 'Working external hash anchor'
                    self.status = True
                else:
                    self.message = 'Broken external hash anchor'
                    self.status = False
        except HTTPError, e:
            if hasattr(e, 'code') and hasattr(e, 'msg'):
                self.message = ' '.join([str(e.code), e.msg])
            else:
                self.message = "Unknown Error"
        except URLError, e:
            if hasattr(e, 'reason'):
                self.message = 'Unreachable: '+str(e.reason)
            elif hasattr(e, 'code') and e.code!=301:
                self.message = 'Error: '+str(e.code)
            else:
                self.message = 'Redirect. Check manually: '+str(e.code)

        return self
