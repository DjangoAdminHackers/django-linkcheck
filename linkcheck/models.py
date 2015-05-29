import re
import imp
import os.path
import sys

from datetime import datetime
from datetime import timedelta
from httplib import BadStatusLine
from HTMLParser import HTMLParseError
import logging
import urllib2

from django.conf import settings
try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import signals as model_signals
from django.test.client import Client
try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module
try:
    from django.utils.timezone import now
except ImportError:
    now = datetime.now 

from linkcheck_settings import MAX_URL_LENGTH
from linkcheck_settings import MEDIA_PREFIX
from linkcheck_settings import SITE_DOMAINS
from linkcheck_settings import EXTERNAL_REGEX_STRING
from linkcheck_settings import EXTERNAL_RECHECK_INTERVAL
from linkcheck_settings import LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT

logger = logging.getLogger('linkcheck')

TIMEOUT_SUPPORT = False
if sys.version_info >= (2,6): #timeout arg of urlopen is available
    TIMEOUT_SUPPORT = True

EXTERNAL_REGEX = re.compile(EXTERNAL_REGEX_STRING)
METHOD_NOT_ALLOWED = 405

class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"

class GetRequest(urllib2.Request):
    def get_method(self):
        return "GET"

class Url(models.Model):
    # A URL represents a distinct URL.
    # A single Url can have multiple Links associated with it
    url = models.CharField(max_length=MAX_URL_LENGTH, unique=True) # See http://www.boutell.com/newfaq/misc/urllength.html
    last_checked = models.DateTimeField(blank=True, null=True)
    status = models.NullBooleanField()
    message = models.CharField(max_length=1024, blank=True, null=True)
    still_exists = models.BooleanField(default=False)

    @property
    def type(self):
        if EXTERNAL_REGEX.match(self.url):
            return 'external'
        if self.url.startswith('mailto'):
            return 'mailto'
        elif str(self.url)=='':
            return 'empty'
        elif self.url.startswith('#'):
            return 'anchor'
        elif self.url.startswith(MEDIA_PREFIX):
            return 'file'
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

    @property
    def external(self):
        return EXTERNAL_REGEX.match(self.url)

    def url_unquoted(self):
        try:
            # URLs should be ascii encodable
            url = self.url.encode('ascii')
        except UnicodeEncodeError:
            url = self.url
        return urllib2.unquote(url).decode('utf8')

    def check_url(self, check_internal=True, check_external=True, external_recheck_interval=EXTERNAL_RECHECK_INTERVAL):

        from linkcheck.utils import LinkCheckHandler
        external_recheck_datetime = now() - timedelta(minutes=external_recheck_interval)
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

        if check_internal and (not self.external):
            if not(self.url):
                self.message = 'Empty link'

            elif self.url.startswith('mailto:'):
                self.status = None
                self.message = 'Email link (not automatically checked)'

            elif self.url.startswith('#'):
                self.status = None
                self.message = 'Link to within the same page (not automatically checked)'

            elif self.url.startswith(MEDIA_PREFIX):
                #TODO Assumes a direct mapping from media url to local filesystem path. This will break quite easily for alternate setups
                if os.path.exists(settings.MEDIA_ROOT + self.url_unquoted()[len(MEDIA_PREFIX)-1:]):
                    self.message = 'Working file link'
                    self.status = True
                else:
                    self.message = 'Missing Document'

            elif getattr(self, '_internal_hash', False) and getattr(self, '_instance', None):
                # This is a hash link pointing to itself
                from linkcheck import parse_anchors

                hash = self._internal_hash
                instance = self._instance
                if hash == '#': # special case, point to #
                    self.message = 'Working internal hash anchor'
                    self.status = True
                else:
                    hash = hash[1:] #'#something' => 'something'
                    html_content = ''
                    for field in instance._linklist.html_fields:
                        html_content += getattr(instance, field, '')
                    names = parse_anchors(html_content)
                    if hash in names:
                        self.message = 'Working internal hash anchor'
                        self.status = True
                    else:
                        self.message = 'Broken internal hash anchor'

            elif self.url.startswith('/'):
                old_prepend_setting = settings.PREPEND_WWW
                settings.PREPEND_WWW = False
                c = Client()
                c.handler = LinkCheckHandler()
                response = c.get(self.url, follow=True)
                if response.status_code == 200:
                    self.message = 'Working internal link'
                    self.status = True
                    # see if the internal link points an anchor
                    if self.url[-1] == '#': # special case, point to #
                        self.message = 'Working internal hash anchor'
                    elif self.url.count('#'):
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
                settings.PREPEND_WWW = old_prepend_setting
            else:
                self.message = 'Invalid URL'

            if original_url: # restore the original url before saving
                self.url = original_url

            self.last_checked  = now()
            self.save()

        elif check_external and self.external:
            logger.info('checking external link: %s' % self.url)
            if self.last_checked and (self.last_checked > external_recheck_datetime):
                return self.status

            try:

                # Remove URL fragment identifiers
                url = self.url.rsplit('#')[0]

                if self.url.count('#'):
                    # We have to get the content so we can check the anchors
                    if TIMEOUT_SUPPORT:
                        response = urllib2.urlopen(
                            url,
                            timeout=LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT
                        )
                    else:
                        response = urllib2.urlopen(url)
                else:
                    # Might as well just do a HEAD request
                    req = HeadRequest(url, headers={'User-Agent' : "http://%s Linkchecker" % settings.SITE_DOMAIN})
                    try:
                        if TIMEOUT_SUPPORT:
                            response = urllib2.urlopen(
                                req,
                                timeout=LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT
                            )
                        else:
                            response = urllib2.urlopen(req)
                    except (ValueError, urllib2.HTTPError):
                        _, error, _ = sys.exc_info()
                        # ...except sometimes it triggers a bug in urllib2
                        if hasattr(error, 'code') and error.code == METHOD_NOT_ALLOWED:
                            req = GetRequest(url, headers={'User-Agent' : "http://%s Linkchecker" % settings.SITE_DOMAIN})
                        else:
                            req = url
                        if TIMEOUT_SUPPORT:
                            response = urllib2.urlopen(
                                req,
                                timeout=LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT
                            )
                        else:
                            response = urllib2.urlopen(req)

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

                    except:
                        # The external web page is mal-formatted #or maybe other parse errors like encoding
                        # I reckon a broken anchor on an otherwise good URL should count as a pass
                        self.message = "Page OK but anchor can't be checked"
                        self.status = True

            except BadStatusLine:
                    self.message = "Bad Status Line"

            except urllib2.HTTPError, e:
                if hasattr(e, 'code') and hasattr(e, 'msg'):
                    self.message = ' '.join([str(e.code), e.msg])
                else:
                    self.message = "Unknown Error"

            except urllib2.URLError, e:
                if hasattr(e, 'reason'):
                    self.message = 'Unreachable: '+str(e.reason)
                elif hasattr(e, 'code') and e.code!=301:
                    self.message = 'Error: '+str(e.code)
                else:
                    self.message = 'Redirect. Check manually: '+str(e.code)
            except Exception, e:
                self.message = 'Other Error: %s' % e

            self.last_checked  = now()
            self.save()

        return self.status

class Link(models.Model):
    # A Link represents a specific URL in a specific field in a specific model
    # Multiple Links can reference a single Url
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    field = models.CharField(max_length=128)
    url = models.ForeignKey(Url, related_name="links")
    text = models.CharField(max_length=256, default='')
    ignore = models.BooleanField(default=False)

    @property
    def display_url(self):
        # when page /test/ has a anchor link to /test/#anchor, we display it
        # as "#anchor" rather than "/test/#anchor"
        if self.url.url.count('#'):
            url_part, anchor_part = self.url.url.split('#')
            absolute_url = self.content_object.get_absolute_url()
            if url_part == absolute_url:
                return '#' + anchor_part
        return self.url.url


def link_post_delete(sender, instance, **kwargs):
    try:
        #url.delete() => link.delete() => link_post_delete
        #in this case link.url is already deleted from db, so we need a try here.
        url = instance.url
        count = url.links.all().count()
        if count == 0:
            url.delete()
    except Url.DoesNotExist:
        pass
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

#add a reference to the linklist in the model. This change is for internal hash link,
#but might also be useful elsewhere in the future
for key, linklist in all_linklists.items():
    setattr(linklist.model, '_linklist', linklist)

#-------------------------register listeners-------------------------

import listeners
