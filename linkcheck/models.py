import re
import imp
import os.path
from datetime import datetime
from datetime import timedelta
from httplib import BadStatusLine
from HTMLParser import HTMLParseError
from urllib2 import HTTPError
from urllib2 import URLError
from urllib2 import urlopen
from urllib2 import Request as urllib2Request

from django.conf import settings
from django.utils.importlib import import_module
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import signals as model_signals
from django.test.client import Client

from linkcheck_settings import MEDIA_PREFIX
from linkcheck_settings import SITE_DOMAINS
from linkcheck_settings import EXTERNAL_REGEX_STRING
from linkcheck_settings import EXTERNAL_RECHECK_INTERVAL

EXTERNAL_REGEX = re.compile(EXTERNAL_REGEX_STRING)

class HeadRequest(urllib2Request):
    def get_method(self):
        return "HEAD"

class Url(models.Model):
    # A URL represents a distinct URL.
    # Urls can have many links pointing to them
    url = models.CharField(max_length=255, unique=True)
    last_checked = models.DateTimeField(max_length=1024, blank=True, null=True)
    status = models.NullBooleanField()
    message = models.CharField(max_length=1024, blank=True, null=True)
    still_exists = models.BooleanField()

    @property
    def type(self):
        if EXTERNAL_REGEX.match(self.url):
            return 'external'
        if self.url.startswith('mailto'):
            return 'mailto'
        elif str(self.url)=='#' or str(self.url)=='':
            return 'empty'
        elif self.url.startswith('#'):
            return 'anchor'
        elif self.url.startswith('/media/documents/images/'): #TODO this needs to be configurable.
            return 'image'
        elif self.url.startswith('/media/documents/'): #TODO this needs to be configurable.
            return 'document'
        elif self.url.startswith('/media/'): #TODO Can't use MEDIA_URL as it sometimes can include the hostname
            return 'other media'
        else:
            return 'unknown'

    @property
    def get_message(self):
        if self.last_checked:
            return self.message
        else:
            return "URL Not Yet Checked"

    @property
    def colour(self):
        if not self.last_checked:
            return 'blue'
        elif self.status==True:
            return 'green'
        else:
            return 'red'

    def __unicode__(self):
        return self.url

    def check(self, check_internal=True, check_external=True):
        from linkcheck.utils import LinkCheckHandler

        external_recheck_interval = EXTERNAL_RECHECK_INTERVAL
        external_recheck_datetime = datetime.now() - timedelta(seconds=external_recheck_interval)
        self.status  = False

        # Remove current domain from URLs as the test client chokes when trying to test them during a page save
        # They shouldn't generally exist but occasionally slip through
        # If settings.SITE_DOMAINS isn't set then use settings.SITE_DOMAIN
        # but also check for variants: example.org, www.example.org, test.example.org
        original_url = None # used to restore the original url afterwards
        if SITE_DOMAINS: #if the setting is present
            internal_exceptions = SITE_DOMAINS
        else: # try using SITE_DOMAIN
            root_domain = settings.SITE_DOMAIN
            if root_domain.startswith('www.'):
                root_domain = root_domain[4:]
            elif root_domain.startswith('test.'):
                root_domain = root_domain[5:]
            internal_exceptions = ['http://'+root_domain, 'http://www.'+root_domain, 'http://test.'+root_domain]
        for ex in internal_exceptions:
            if ex and self.url.startswith(ex):
                original_url = self.url
                self.url = self.url.replace(ex, '', 1)


        if check_internal and not(EXTERNAL_REGEX.match(self.url)):
            if not(self.url):
                self.message = 'Empty link'

            elif self.url.startswith('mailto:'):
                self.status = None
                self.message = 'Email link (not automatically checked)'

            elif self.url.startswith('#'):
                self.status = None
                self.message = 'Link to within the same page (not automatically checked)'

            elif self.url.startswith(MEDIA_PREFIX):
                if os.path.exists(settings.MEDIA_ROOT+self.url[len(MEDIA_PREFIX)-1:]): #TODO Assumes a direct mapping from media url to local filesystem path. This will break quite easily for alternate setups
                    self.message = 'Working document link'
                    self.status = True
                else:
                    self.message = 'Missing Document'

            elif self.url.startswith('/'):
                c = Client()
                c.handler = LinkCheckHandler()
                response = c.get(self.url, follow=True)
                if response.status_code == 200:
                    self.message = 'Working internal link'
                    self.status = True
                    if self.url.count('#'):
                        anchor = self.url.split('#')[1]
                        from linkcheck import parse_anchors
                        names = parse_anchors(response.content)
                        if anchor in names:
                            self.message = 'Working internal hash anchor'
                            self.status = True
                        else:
                            self.message = 'Broken internal hash anchor'
                            self.status = False

                elif (response.status_code == 302 or response.status_code == 301):
                    self.status = None
                    self.message = 'This link redirects: code %d (not automatically checked)' % (response.status_code, )
                else:
                    self.message = 'Broken internal link'
            else:
                self.message = 'Invalid URL'

            if original_url: # restore the original url before saving
                self.url = original_url

            self.last_checked  = datetime.now()
            self.save()

        elif check_external and EXTERNAL_REGEX.match(self.url):

            if self.last_checked and (self.last_checked > external_recheck_datetime):
                return self.status
            try:
                url = self.url.rsplit('#')[0] # Remove URL fragment identifiers
                req = HeadRequest(url, headers={'User-Agent' : "http://%s Linkchecker" % settings.SITE_DOMAIN})
                response = urlopen(req)
                self.message = ' '.join([str(response.code), response.msg])
                self.status = True

                if self.url.count('#'):
                    anchor = self.url.split('#')[1]
                    from linkcheck import parse_anchors
                    try:
                        names = parse_anchors(response.read())
                        if anchor in names:
                            self.message = 'Working external hash anchor'
                            self.status = True
                        else:
                            self.message = 'Broken external hash anchor'
                            self.status = False
                    except HTMLParseError:
                        # The external web page is mal-formatted
                        self.message = 'Cannot validate this anchor'
                        self.status = None

            except BadStatusLine:
                    self.message = "Bad Status Line"

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
            self.last_checked  = datetime.now()
            self.save()

        return self.status

class Link(models.Model):
    # A link represents a URL in a field in a specific model
    # Many links can point to the same URL
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    field = models.CharField(max_length=128)
    url = models.ForeignKey(Url, related_name="links")
    text = models.CharField(max_length=256, default='')

def link_post_delete(sender, instance, **kwargs):
    url = instance.url
    count = url.links.all().count()
    if count == 0:
        url.delete()
model_signals.post_delete.connect(link_post_delete, sender=Link)


#-------------------------auto discover of LinkLists-------------------------

class AlreadyRegistered(Exception):
    pass

all_linklists = {}

for app in settings.INSTALLED_APPS:
    try:
        app_path = import_module(app).__path__
    except AttributeError:
        continue
    try:
        imp.find_module('linklists', app_path)
    except ImportError:
        continue
    the_module = import_module("%s.linklists" % app)
    try:
        for k in the_module.linklists.keys():
            if k in all_linklists.keys():
                raise AlreadyRegistered('The key %s is already registered in all_linklists' % k)

        for l in the_module.linklists.values():
            for l2 in all_linklists.values():
                if l.model == l2.model:
                    raise AlreadyRegistered('The LinkList %s is already registered in all_linklists' % l)
        all_linklists.update(the_module.linklists)
    except AttributeError:
        pass

#-------------------------register listeners-------------------------

import listeners
