from __future__ import unicode_literals

import re
import imp
import os.path

from datetime import datetime
from datetime import timedelta
import logging

from django.conf import settings
try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import signals as model_signals
from django.test.client import Client
from django.utils.encoding import iri_to_uri, python_2_unicode_compatible
from django.utils.http import urlunquote
try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module
from django.utils.six.moves import http_client
from django.utils.six.moves.urllib.error import HTTPError, URLError
from django.utils.six.moves.urllib.request import HTTPRedirectHandler, Request, build_opener
try:
    from django.utils.timezone import now
except ImportError:
    now = datetime.now

try:
    from reversion.revisions import revision_context_manager
    USE_REVERSION = True
except ImportError:
    USE_REVERSION = False

from .linkcheck_settings import (
    MAX_URL_LENGTH,
    MEDIA_PREFIX,
    SITE_DOMAINS,
    EXTERNAL_REGEX_STRING,
    EXTERNAL_RECHECK_INTERVAL,
    LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT,
)

logger = logging.getLogger('linkcheck')


EXTERNAL_REGEX = re.compile(EXTERNAL_REGEX_STRING)
METHOD_NOT_ALLOWED = 405


class HeadRequest(Request):
    def get_method(self):
        return "HEAD"


class GetRequest(Request):
    def get_method(self):
        return "GET"


class RedirectHandler(HTTPRedirectHandler):
    """With this custom handler, we'll be able to identify 301 redirections"""
    def http_error_301(self, req, fp, code, *args):
        result = HTTPRedirectHandler.http_error_301(self, req, fp, code, *args)
        if result:
            result.code = result.status = code
        return result


def html_decode(s):
    """
    Returns the ASCII decoded version of the given HTML string. This does
    NOT remove normal HTML tags like <p>.
    """
    html_codes = (
            ("'", '&#39;'),
            ('"', '&quot;'),
            ('>', '&gt;'),
            ('<', '&lt;'),
            ('&', '&amp;')
        )
    for code in html_codes:
        s = s.replace(code[1], code[0])
    return s


@python_2_unicode_compatible
class Url(models.Model):
    
    """
    Represents a distinct URL found somewhere in the models registered with linkcheck
    A single Url can have multiple Links associated with it.
    """
    url = models.CharField(max_length=MAX_URL_LENGTH, unique=True)  # See http://www.boutell.com/newfaq/misc/urllength.html
    last_checked = models.DateTimeField(blank=True, null=True)
    status = models.NullBooleanField()
    message = models.CharField(max_length=1024, blank=True, null=True)
    still_exists = models.BooleanField(default=False)
    redirect_to = models.CharField(max_length=MAX_URL_LENGTH, default='')

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

    def __str__(self):
        return self.url

    @property
    def external(self):
        return EXTERNAL_REGEX.match(self.url)

    def check_url(self, check_internal=True, check_external=True, external_recheck_interval=EXTERNAL_RECHECK_INTERVAL):
        """
        Return:
         * True if the link was checked and found valid
         * False if the link was checked and found invalid
         * None if the link was not checked
        """

        self.status = False

        # Remove current domain from URLs as the test client chokes when trying to test them during a page save
        # They shouldn't generally exist but occasionally slip through
        # If settings.SITE_DOMAINS isn't set then use settings.SITE_DOMAIN
        # but also check for variants: example.org, www.example.org, test.example.org

        tested_url = self.url  # May receive transformation before being checked

        if SITE_DOMAINS:  # If the setting is present
            internal_exceptions = SITE_DOMAINS

        else:  # try using SITE_DOMAIN
            root_domain = settings.SITE_DOMAIN
            if root_domain.startswith('www.'):
                root_domain = root_domain[4:]
            elif root_domain.startswith('test.'):
                root_domain = root_domain[5:]
            internal_exceptions = ['http://'+root_domain, 'http://www.'+root_domain, 'http://test.'+root_domain]

        for ex in internal_exceptions:
            if ex and tested_url.startswith(ex):
                tested_url = tested_url.replace(ex, '', 1)

        external = bool(EXTERNAL_REGEX.match(tested_url))

        if check_internal and not external:
            self._check_internal(tested_url)

        elif check_external and external:
            self._check_external(tested_url, external_recheck_interval)

        else:
            return None

        return self.status

    def _check_internal(self, tested_url):

        from linkcheck.utils import LinkCheckHandler

        if not(tested_url):
            self.message = 'Empty link'

        elif tested_url.startswith('mailto:'):
            self.status = None
            self.message = 'Email link (not automatically checked)'

        elif tested_url.startswith('#'):
            self.status = None
            self.message = 'Link to within the same page (not automatically checked)'

        elif tested_url.startswith(MEDIA_PREFIX):
            # TODO Assumes a direct mapping from media url to local filesystem path. This will break quite easily for alternate setups
            path = settings.MEDIA_ROOT + urlunquote(tested_url)[len(MEDIA_PREFIX)-1:]
            decoded_path = html_decode(path)
            if os.path.exists(path) or os.path.exists(decoded_path):
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

        elif tested_url.startswith('/'):
            old_prepend_setting = settings.PREPEND_WWW
            settings.PREPEND_WWW = False
            c = Client()
            c.handler = LinkCheckHandler()
            response = c.get(tested_url)
            if USE_REVERSION:
                # using test client will clear the RevisionContextManager stack.
                revision_context_manager.start()

            if response.status_code == 200:
                self.message = 'Working internal link'
                self.status = True
                # see if the internal link points an anchor
                if tested_url[-1] == '#': # special case, point to #
                    self.message = 'Working internal hash anchor'
                elif tested_url.count('#'):
                    anchor = tested_url.split('#')[1]
                    from linkcheck import parse_anchors
                    names = parse_anchors(response.content)
                    if anchor in names:
                        self.message = 'Working internal hash anchor'
                        self.status = True
                    else:
                        self.message = 'Broken internal hash anchor'
                        self.status = False

            elif response.status_code == 302 or response.status_code == 301:
                self.status = None
                self.message = 'This link redirects: code %d (not automatically checked)' % (response.status_code, )
            else:
                self.message = 'Broken internal link'
            settings.PREPEND_WWW = old_prepend_setting
        else:
            self.message = 'Invalid URL'

        self.last_checked = now()
        self.save()

    def _check_external(self, tested_url, external_recheck_interval):
        logger.info('checking external link: %s' % tested_url)
        external_recheck_datetime = now() - timedelta(minutes=external_recheck_interval)

        if self.last_checked and (self.last_checked > external_recheck_datetime):
            return self.status

        opener = build_opener(RedirectHandler)
        # Remove URL fragment identifiers
        url = tested_url.rsplit('#')[0]
        # Check that non-ascii chars are properly encoded
        try:
            url.encode('ascii')
        except UnicodeEncodeError:
            url = iri_to_uri(url)

        try:
            if tested_url.count('#'):
                # We have to get the content so we can check the anchors
                response = opener.open(
                    url,
                    timeout=LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT
                )
            else:
                # Might as well just do a HEAD request
                req = HeadRequest(url, headers={'User-Agent' : "http://%s Linkchecker" % settings.SITE_DOMAIN})
                try:
                    response = opener.open(
                        req,
                        timeout=LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT
                    )
                except (ValueError, HTTPError) as error:
                    # ...except sometimes it triggers a bug in urllib2
                    if hasattr(error, 'code') and error.code == METHOD_NOT_ALLOWED:
                        req = GetRequest(url, headers={'User-Agent' : "http://%s Linkchecker" % settings.SITE_DOMAIN})
                    else:
                        req = url
                    response = opener.open(
                        req,
                        timeout=LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT
                    )

            self.message = ' '.join([str(response.code), response.msg])
            self.status = True

            if tested_url.count('#'):

                anchor = tested_url.split('#')[1]
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

        except http_client.BadStatusLine:
                self.message = "Bad Status Line"

        except HTTPError as e:
            if hasattr(e, 'code') and hasattr(e, 'msg'):
                self.message = ' '.join([str(e.code), e.msg])
            else:
                self.message = "Unknown Error"

        except URLError as e:
            if hasattr(e, 'reason'):
                self.message = 'Unreachable: '+str(e.reason)
            elif hasattr(e, 'code') and e.code!=301:
                self.message = 'Error: '+str(e.code)
            else:
                self.message = 'Redirect. Check manually: '+str(e.code)
        except Exception as e:
            self.message = 'Other Error: %s' % e
        else:
            if response.getcode() == 301 and response.geturl() != url:
                self.redirect_to = response.geturl()
            elif self.redirect_to:
                self.redirect_to = ''

        self.last_checked = now()
        self.save()


class Link(models.Model):
    """
    A Link represents a specific URL in a specific field in a specific model
    It can be come from a single field such as a URLField or a field containing multiple links
    Such as a HTML or Rich Text field.
    Multiple Links can reference a single Url
    """
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
        if self.url.url.count('#') and hasattr(self.content_object, 'get_absolute_url'):
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


# Autodiscovery of linkLists


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

# Add a reference to the linklist in the model. This change is for internal hash link,
# But might also be useful elsewhere in the future

for key, linklist in all_linklists.items():
    setattr(linklist.model, '_linklist', linklist)


# Register listeners

from . import listeners
