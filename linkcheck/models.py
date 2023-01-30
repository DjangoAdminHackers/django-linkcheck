import logging
import os.path
import re
from datetime import timedelta
from urllib.parse import unquote

import requests
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test.client import Client
from django.test.utils import modify_settings
from django.utils.encoding import iri_to_uri
from django.utils.functional import cached_property
from django.utils.timezone import now
from requests.exceptions import ConnectionError, ReadTimeout
from requests.models import REDIRECT_STATI

try:
    from reversion.revisions import revision_context_manager
    USE_REVERSION = True
except ImportError:
    USE_REVERSION = False

from .linkcheck_settings import (
    EXTERNAL_RECHECK_INTERVAL,
    EXTERNAL_REGEX_STRING,
    LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT,
    MAX_URL_LENGTH,
    MEDIA_PREFIX,
    SITE_DOMAINS,
    TOLERATE_BROKEN_ANCHOR,
)

logger = logging.getLogger(__name__)


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
    # See http://www.boutell.com/newfaq/misc/urllength.html
    url = models.CharField(max_length=MAX_URL_LENGTH, unique=True)
    last_checked = models.DateTimeField(blank=True, null=True)
    status = models.BooleanField(null=True)
    message = models.CharField(max_length=1024, blank=True, null=True)
    redirect_to = models.TextField(blank=True)

    @property
    def type(self):
        if self.external:
            return 'external'
        if self.url.startswith('mailto'):
            return 'mailto'
        if self.url.startswith('tel'):
            return 'phone'
        elif self.url == '':
            return 'empty'
        elif self.url.startswith('#'):
            return 'anchor'
        elif self.url.startswith(MEDIA_PREFIX):
            return 'file'
        elif self.internal_url.startswith('/'):
            return 'internal'
        else:
            return 'invalid'

    @property
    def has_anchor(self):
        return '#' in self.url

    @property
    def anchor(self):
        return self.url.split('#')[1] if self.has_anchor else None

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

    def __repr__(self):
        return f"<Url (id: {self.id}, url: {self.url})>"

    @cached_property
    def internal_url(self):
        """
        Remove current domain from URLs as the test client chokes when trying to test them during a page save
        They shouldn't generally exist but occasionally slip through
        If settings.SITE_DOMAINS isn't set then use settings.SITE_DOMAIN
        but also check for variants: example.org, www.example.org, test.example.org

        In case the URLs is external, `None` is returned.
        """

        # If the URL is not external, directly return it without processing
        if not EXTERNAL_REGEX.match(self.url):
            return self.url

        # May receive transformation before being checked
        prepared_url = self.url

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
                f'{protocol}://{sub}{root_domain}' for sub in ['', 'www.', 'test.'] for protocol in ['http', 'https']
            ]

        for ex in internal_exceptions:
            if ex and prepared_url.startswith(ex):
                prepared_url = prepared_url.replace(ex, '', 1)

        # If the URL is still external, return `None`
        if EXTERNAL_REGEX.match(prepared_url):
            return None

        logger.debug('Internal URL: %s', prepared_url)
        return prepared_url

    @cached_property
    def external_url(self):
        """
        Prepare an external URL to be checked with requests:
        - Remove hash anchors
        - Ensure correct encoding
        """
        # If the URL is internal, return `None`
        if self.internal:
            return None

        # Remove URL fragment identifiers
        external_url = self.url.rsplit('#')[0]
        # Check that non-ascii chars are properly encoded
        try:
            external_url.encode('ascii')
        except UnicodeEncodeError:
            external_url = iri_to_uri(external_url)
        logger.debug('External URL: %s', external_url)
        return external_url

    @property
    def internal(self):
        """
        Check whether this URL is internal
        """
        return self.internal_url is not None

    @property
    def external(self):
        """
        Check whether this URL is external
        """
        return not self.internal

    def check_url(self, check_internal=True, check_external=True, external_recheck_interval=EXTERNAL_RECHECK_INTERVAL):
        """
        Return:
         * True if the link was checked and found valid
         * False if the link was checked and found invalid
         * None if the link was not checked
        """

        self.status = False

        if check_internal and self.internal:
            self.check_internal()

        elif check_external and self.external:
            self.check_external(external_recheck_interval)

        else:
            return None

        return self.status

    def check_internal(self):
        """
        Check an internal URL
        """
        if not self.internal:
            logger.info('URL %r is not internal', self)
            return None

        logger.debug('checking internal link: %s', self.internal_url)

        from linkcheck.utils import LinkCheckHandler

        if self.type == 'empty':
            self.message = 'Empty link'

        elif self.type == 'mailto':
            self.status = None
            self.message = 'Email link (not automatically checked)'

        elif self.type == 'phone':
            self.status = None
            self.message = 'Phone number (not automatically checked)'

        elif self.type == 'anchor':
            self.status = None
            self.message = 'Link to within the same page (not automatically checked)'

        elif self.type == 'file':
            # TODO: Assumes a direct mapping from media url to local filesystem path.
            # This will break quite easily for alternate setups
            path = settings.MEDIA_ROOT + unquote(self.internal_url)[len(MEDIA_PREFIX) - 1:]
            decoded_path = html_decode(path)
            if os.path.exists(path) or os.path.exists(decoded_path):
                self.message = 'Working file link'
                self.status = True
            else:
                self.message = 'Missing Document'

        elif getattr(self, '_internal_hash', False) and getattr(self, '_instance', None):
            # This is a hash link pointing to itself
            hash = self._internal_hash
            instance = self._instance
            if hash == '#':  # special case, point to #
                self.message = 'Working internal hash anchor'
                self.status = True
            else:
                hash = hash[1:]  # '#something' => 'something'
                html_content = ''
                for field in instance._linklist.html_fields:
                    html_content += getattr(instance, field, '')
                self._check_anchor(hash, html_content)

        elif self.type == 'internal':
            old_prepend_setting = settings.PREPEND_WWW
            settings.PREPEND_WWW = False
            c = Client()
            c.handler = LinkCheckHandler()
            with modify_settings(ALLOWED_HOSTS={'append': 'testserver'}):
                response = c.get(self.internal_url)
            if response.status_code == 200:
                self.message = 'Working internal link'
                self.status = True
            elif response.status_code == 302 or response.status_code == 301:
                redirect_type = "permanent" if response.status_code == 301 else "temporary"
                with modify_settings(ALLOWED_HOSTS={'append': 'testserver'}):
                    response = c.get(self.internal_url, follow=True)
                if response.status_code == 200:
                    self.message = f'Working {redirect_type} redirect'
                    self.status = True
                else:
                    self.message = f'Broken {redirect_type} redirect'
            else:
                self.message = 'Broken internal link'

            # Check the anchor (if it exists)
            self.check_anchor(response.content)

            settings.PREPEND_WWW = old_prepend_setting
        else:
            self.message = 'Invalid URL'

        if USE_REVERSION:
            # using test client will clear the RevisionContextManager stack.
            revision_context_manager.start()

        self.last_checked = now()
        self.save()

    def check_external(self, external_recheck_interval=EXTERNAL_RECHECK_INTERVAL):
        """
        Check an external URL
        """
        if not self.external:
            logger.info('URL %r is not external', self)
            return None

        logger.info('checking external link: %s', self.url)
        external_recheck_datetime = now() - timedelta(minutes=external_recheck_interval)

        if self.last_checked and (self.last_checked > external_recheck_datetime):
            logger.debug(
                'URL was last checked in the last %s minutes, so not checking it again',
                external_recheck_interval
            )
            return self.status

        request_params = {
            'allow_redirects': True,
            'headers': {'User-Agent': f"http://{settings.SITE_DOMAIN} Linkchecker"},
            'timeout': LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT,
            'verify': True,
        }
        try:
            try:
                # At first try a HEAD request
                response = requests.head(self.external_url, **request_params)
            except ConnectionError as e:
                # This error could also be caused by an incomplete root certificate bundle,
                # so let's retry without verifying the certificate
                if "unable to get local issuer certificate" in str(e):
                    request_params['verify'] = False
                    response = requests.head(self.external_url, **request_params)
                else:
                    # Re-raise exception if it's definitely not a false positive
                    raise
            # If HEAD is not allowed, let's try with GET
            if response.status_code >= 400:
                logger.debug('HEAD is not allowed, retry with GET')
                response = requests.get(self.external_url, **request_params)
            # If URL contains hash anchor and is a valid HTML document, let's repeat with GET
            elif (
                self.has_anchor and
                response.ok and
                'text/html' in response.headers.get('content-type')
            ):
                logger.debug('Retrieve content for anchor check')
                response = requests.get(self.external_url, **request_params)
        except ReadTimeout:
            self.message = 'Other Error: The read operation timed out'
        except ConnectionError as e:
            self.message = format_connection_error(e)
        except Exception as e:
            self.message = f'Other Error: {e}'
        else:
            self.message = f"{response.status_code} {response.reason}"
            logger.debug('Response message: %s', self.message)

            if response.ok and response.status_code not in REDIRECT_STATI:
                self.status = True
                # If initial response was a redirect, return the initial return code
                if response.history:
                    logger.debug('Redirect history: %r', response.history)
                    self.message = f"{response.history[0].status_code} {response.history[0].reason}"
                    self.redirect_to = response.url
            # Check the anchor (if it exists)
            if response.request.method == 'GET':
                self.check_anchor(response.text)
            if not request_params['verify']:
                self.message += ', SSL certificate could not be verified'

        self.last_checked = now()
        self.save()

    def check_anchor(self, html):
        from linkcheck import parse_anchors

        scope = "internal" if self.internal else "external"

        # Only check when the URL contains an anchor
        if self.has_anchor:
            # Empty fragment '#' is always valid
            if not self.anchor:
                self.message += f', working {scope} hash anchor'
            else:
                try:
                    names = parse_anchors(html)
                # Known possible errors include: AssertionError, NotImplementedError, UnicodeDecodeError
                except Exception as e:
                    logger.debug(
                        '%s while parsing anchors: %s',
                        type(e).__name__,
                        e
                    )
                    self.message += ', failed to parse HTML for anchor'
                    if not TOLERATE_BROKEN_ANCHOR:
                        self.status = False
                else:
                    if self.anchor in names:
                        self.message += f', working {scope} hash anchor'
                    else:
                        self.message += f', broken {scope} hash anchor'
                        if not TOLERATE_BROKEN_ANCHOR:
                            self.status = False


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

    def __str__(self):
        return f"{self.url.url} ({self.content_object})"

    def __repr__(self):
        return f"<Link (id: {self.id}, url: {self.url!r}, source: {self.content_object!r})>"


def link_post_delete(sender, instance, **kwargs):
    try:
        # url.delete() => link.delete() => link_post_delete
        # in this case link.url is already deleted from db, so we need a try here.
        url = instance.url
        count = url.links.all().count()
        if count == 0:
            logger.debug('This was the last link for %r, so deleting it', url)
            url.delete()
    except Url.DoesNotExist:
        pass


def format_connection_error(e):
    """
    Helper function to provide better readable output of connection errors
    """
    # If the exception message is wrapped in an "HTTPSConnectionPool", only give the underlying cause
    reason = re.search(r"\(Caused by ([a-zA-Z]+\(.+\))\)", str(e))
    if not reason:
        return f"Connection Error: {e}"
    reason = reason[1]
    # If the underlying cause is a new connection error, provide additional formatting
    if reason.startswith("NewConnectionError"):
        return format_new_connection_error(reason)
    # If the underlying cause is an SSL error, provide additional formatting
    if reason.startswith("SSLError"):
        return format_ssl_error(reason)
    return f"Connection Error: {reason}"


def format_new_connection_error(reason):
    """
    Helper function to provide better readable output of new connection errors thrown by urllib3
    """
    connection_reason = re.search(
        r"NewConnectionError\('<urllib3\.connection\.HTTPSConnection object at 0x[0-9a-f]+>: (.+)'\)",
        reason,
    )
    if connection_reason:
        return f"New Connection Error: {connection_reason[1]}"
    return reason


def format_ssl_error(reason):
    """
    Helper function to provide better readable output of SSL errors thrown by urllib3
    """
    ssl_reason = re.search(r"SSLError\([a-zA-Z]+\((.+)\)\)", reason)
    if ssl_reason:
        # If the reason lies withing the ssl c library, hide additional debug output
        ssl_c_reason = re.search(r"1, '\[SSL: [A-Z\d_]+\] (.+) \(_ssl\.c:\d+\)'", ssl_reason[1])
        if ssl_c_reason:
            return f"SSL Error: {ssl_c_reason[1]}"
        return f"SSL Error: {ssl_reason[1]}"
    return reason
