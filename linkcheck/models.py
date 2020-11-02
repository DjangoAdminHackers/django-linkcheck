import re
import os.path

from datetime import timedelta
import logging
import requests
from requests.exceptions import ReadTimeout
from requests.models import REDIRECT_STATI
from urllib.parse import unquote

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test.client import Client
from django.test.utils import modify_settings
from django.utils.encoding import iri_to_uri
from django.utils.timezone import now

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


class Url(models.Model):
    """
    Represents a distinct URL found somewhere in the models registered with linkcheck
    A single Url can have multiple Links associated with it.
    """
    url = models.CharField(max_length=MAX_URL_LENGTH, unique=True)  # See http://www.boutell.com/newfaq/misc/urllength.html
    last_checked = models.DateTimeField(blank=True, null=True)
    status = models.BooleanField(null=True)
    message = models.CharField(max_length=1024, blank=True, null=True)
    still_exists = models.BooleanField(default=False)
    redirect_to = models.TextField(blank=True)

    @property
    def type(self):
        if EXTERNAL_REGEX.match(self.url):
            return 'external'
        if self.url.startswith('mailto'):
            return 'mailto'
        if self.url.startswith('tel'):
            return 'phone'
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
        elif self.status is True:
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

        internal_exceptions = []
        if SITE_DOMAINS:  # If the setting is present
            internal_exceptions = SITE_DOMAINS

        elif getattr(settings, 'SITE_DOMAIN', None):  # try using SITE_DOMAIN
            root_domain = settings.SITE_DOMAIN
            if root_domain.startswith('www.'):
                root_domain = root_domain[4:]
            elif root_domain.startswith('test.'):
                root_domain = root_domain[5:]
            internal_exceptions = [
                'http://'+root_domain, 'http://www.'+root_domain, 'http://test.'+root_domain,
                'https://' + root_domain, 'https://www.' + root_domain, 'https://test.' + root_domain,
            ]

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

        elif tested_url.startswith('tel:'):
            self.status = None
            self.message = 'Phone number (not automatically checked)'

        elif tested_url.startswith('#'):
            self.status = None
            self.message = 'Link to within the same page (not automatically checked)'

        elif tested_url.startswith(MEDIA_PREFIX):
            # TODO Assumes a direct mapping from media url to local filesystem path. This will break quite easily for alternate setups
            path = settings.MEDIA_ROOT + unquote(tested_url)[len(MEDIA_PREFIX)-1:]
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
                try:
                    names = parse_anchors(html_content)
                    if hash in names:
                        self.message = 'Working internal hash anchor'
                        self.status = True
                    else:
                        self.message = 'Broken internal hash anchor'
                except UnicodeDecodeError:
                    self.message = 'Failed to parse HTML for anchor'


        elif tested_url.startswith('/'):
            old_prepend_setting = settings.PREPEND_WWW
            settings.PREPEND_WWW = False
            c = Client()
            c.handler = LinkCheckHandler()
            with modify_settings(ALLOWED_HOSTS={'append': 'testserver'}):
                response = c.get(tested_url)
            if response.status_code == 200:
                self.message = 'Working internal link'
                self.status = True
                # see if the internal link points an anchor
                if tested_url[-1] == '#': # special case, point to #
                    self.message = 'Working internal hash anchor'
                elif tested_url.count('#'):
                    anchor = tested_url.split('#')[1]
                    from linkcheck import parse_anchors
                    try:
                        names = parse_anchors(response.content)
                        if anchor in names:
                            self.message = 'Working internal hash anchor'
                            self.status = True
                        else:
                            self.message = 'Broken internal hash anchor'
                            self.status = False
                    except UnicodeDecodeError:
                        self.message = 'Failed to parse HTML for anchor'

            elif response.status_code == 302 or response.status_code == 301:
                with modify_settings(ALLOWED_HOSTS={'append': 'testserver'}):
                    redir_response = c.get(tested_url, follow=True)
                if redir_response.status_code == 200:
                    redir_state = 'Working redirect'
                    self.status = True
                else:
                    redir_state = 'Broken redirect'
                    self.status = False
                self.message = 'This link redirects: code %d (%s)' % (
                    response.status_code, redir_state)
            else:
                self.message = 'Broken internal link'
            settings.PREPEND_WWW = old_prepend_setting
        else:
            self.message = 'Invalid URL'

        if USE_REVERSION:
            # using test client will clear the RevisionContextManager stack.
            revision_context_manager.start()

        self.last_checked = now()
        self.save()

    def _check_external(self, tested_url, external_recheck_interval):
        logger.info('checking external link: %s' % tested_url)
        external_recheck_datetime = now() - timedelta(minutes=external_recheck_interval)

        if self.last_checked and (self.last_checked > external_recheck_datetime):
            return self.status

        # Remove URL fragment identifiers
        url = tested_url.rsplit('#')[0]
        # Check that non-ascii chars are properly encoded
        try:
            url.encode('ascii')
        except UnicodeEncodeError:
            url = iri_to_uri(url)

        request_params = {
            'verify': False, 'allow_redirects': True,
            'headers': {'User-Agent' : "http://%s Linkchecker" % settings.SITE_DOMAIN},
            'timeout': LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT,
        }
        try:
            if tested_url.count('#'):
                # We have to get the content so we can check the anchors
                response = requests.get(url, **request_params)
            else:
                # Might as well just do a HEAD request
                response = requests.head(url, **request_params)

            if response.status_code >= 400:
                # If HEAD is not allowed, let's try with GET
                response = requests.get(url, **request_params)
        except ReadTimeout:
            self.message = 'Other Error: The read operation timed out'
            self.status = False
        except Exception as e:
            self.message = 'Other Error: %s' % e
            self.status = False
        else:
            self.message = ' '.join([str(response.status_code), response.reason])
            self.status = 200 <= response.status_code < 400

            if tested_url.count('#'):
                anchor = tested_url.split('#')[1]
                from linkcheck import parse_anchors
                try:
                    names = parse_anchors(response.text)
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

            if response.status_code in REDIRECT_STATI:
                # This means it could not follow the redirection
                self.status = False
            elif response.status_code < 300 and response.history:
                self.message = ' '.join([str(response.history[0].status_code), response.history[0].reason])
                self.redirect_to = response.url

        self.last_checked = now()
        self.save()


class Link(models.Model):
    """
    A Link represents a specific URL in a specific field in a specific model
    It can be come from a single field such as a URLField or a field containing multiple links
    Such as a HTML or Rich Text field.
    Multiple Links can reference a single Url
    """
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    field = models.CharField(max_length=128)
    url = models.ForeignKey(Url, related_name="links", on_delete=models.CASCADE)
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
