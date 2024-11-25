import logging
import os.path
import re
from datetime import timedelta
from http import HTTPStatus
from urllib.parse import unquote, urlparse

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
from django.utils.translation import gettext as _
from requests.exceptions import ConnectionError, ReadTimeout

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


STATUS_CODE_CHOICES = [(s.value, f'{s.value} {s.phrase}') for s in HTTPStatus]
DEFAULT_USER_AGENT = f'{settings.SITE_DOMAIN} Linkchecker'
FALLBACK_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'


class Url(models.Model):
    """
    Represents a distinct URL found somewhere in the models registered with linkcheck
    A single Url can have multiple Links associated with it.
    """
    # See http://www.boutell.com/newfaq/misc/urllength.html
    url = models.CharField(max_length=MAX_URL_LENGTH, unique=True)
    last_checked = models.DateTimeField(blank=True, null=True)
    anchor_status = models.BooleanField(null=True)
    ssl_status = models.BooleanField(null=True)
    status = models.BooleanField(null=True)
    status_code = models.IntegerField(choices=STATUS_CODE_CHOICES, null=True)
    redirect_status_code = models.IntegerField(choices=STATUS_CODE_CHOICES, null=True)
    message = models.CharField(max_length=1024, blank=True, null=True)
    error_message = models.CharField(max_length=1024, default='', blank=True)
    redirect_to = models.TextField(blank=True)

    @property
    def redirect_ok(self):
        return self.redirect_status_code < 300 if self.redirect_status_code else None

    @property
    def type(self):
        if self.external:
            return 'external'
        if self.url.startswith('mailto:'):
            return 'mailto'
        if self.url.startswith('tel:'):
            return 'phone'
        elif self.internal_url == '':
            return 'empty'
        elif self.internal_url.startswith('#'):
            return 'anchor'
        elif self.internal_url.startswith(MEDIA_PREFIX):
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
    def anchor_message(self):
        if not self.has_anchor or not self.last_checked:
            return ''
        if self.anchor == '':
            return _('Working empty anchor')
        if self.anchor_status is None:
            return _('Anchor could not be checked')
        elif self.anchor_status is False:
            return _('Broken anchor')
        return _('Working anchor')

    @property
    def ssl_message(self):
        if self.internal:
            return ''
        if self.external_url.startswith('http://'):
            return _('Insecure link')
        if self.ssl_status is None:
            return _('SSL certificate could not be checked')
        elif self.ssl_status is False:
            return _('Broken SSL certificate')
        return _('Valid SSL certificate')

    @property
    def get_message(self):
        if not self.last_checked and self.status is None:
            return _('URL Not Yet Checked')
        elif self.type == 'empty':
            return _('Empty link')
        elif self.type == 'invalid':
            return _('Invalid URL')
        elif self.type == 'mailto':
            return '{} ({})'.format(_("Email link"), _("not automatically checked"))
        elif self.type == 'phone':
            return '{} ({})'.format(_("Phone number link"), _("not automatically checked"))
        elif self.type == 'anchor':
            return '{} ({})'.format(_("Anchor link"), _("not automatically checked"))
        elif self.type == 'file':
            return _('Working file link') if self.status else _('Missing file')
        elif not self.status_code:
            return self.error_message
        elif self.status_code < 300:
            return _('Working external link') if self.external else _('Working internal link')
        elif self.status_code < 400:
            permanent = self.status_code in [HTTPStatus.MOVED_PERMANENTLY, HTTPStatus.PERMANENT_REDIRECT]
            if self.redirect_ok:
                return _('Working permanent redirect') if permanent else _('Working temporary redirect')
            else:
                return _('Broken permanent redirect') if permanent else _('Broken temporary redirect')
        return _('Broken external link') if self.external else _('Broken internal link')

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

        # Encode path and query and remove anchor fragment
        parsed = urlparse(self.url)
        external_url = parsed._replace(
            path=iri_to_uri(parsed.path),
            query=iri_to_uri(parsed.query),
            fragment=""
        ).geturl()

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

    def reset_for_check(self):
        """
        Reset all fields which depend on the status after checking a URL.
        This is done to ensure that results from the last check do not remain if the fields are not overwritten.
        """
        # Reset all database fields
        self.anchor_status = None
        self.status = None
        self.status_code = None
        self.redirect_status_code = None
        self.ssl_status = None
        self.error_message = ''
        self.message = ''

    def check_url(self, check_internal=True, check_external=True, external_recheck_interval=EXTERNAL_RECHECK_INTERVAL):
        """
        Return:
         * True if the link was checked and found valid
         * False if the link was checked and found invalid
         * None if the link was not checked
        """

        if check_internal and self.internal:
            return self.check_internal()
        elif check_external and self.external:
            return self.check_external(external_recheck_interval)
        else:
            return None

    def check_internal(self):
        """
        Check an internal URL
        """
        if not self.internal:
            logger.info('URL %r is not internal', self)
            return None

        logger.debug('checking internal link: %s', self.internal_url)

        # Reset all fields in case they were already set
        self.reset_for_check()

        from linkcheck.utils import LinkCheckHandler

        if self.type == 'empty':
            self.status = False
            self.message = 'Empty link'

        elif self.type == 'mailto':
            self.message = 'Email link (not automatically checked)'

        elif self.type == 'phone':
            self.message = 'Phone number (not automatically checked)'

        elif self.type == 'anchor':
            self.message = 'Link to within the same page (not automatically checked)'

        elif self.type == 'file':
            # TODO: Assumes a direct mapping from media url to local filesystem path.
            # This will break quite easily for alternate setups
            path = settings.MEDIA_ROOT + unquote(self.internal_url)[len(MEDIA_PREFIX) - 1:]
            decoded_path = html_decode(path)
            self.status = os.path.exists(path) or os.path.exists(decoded_path)
            self.message = 'Working file link' if self.status else 'Missing Document'

        elif self.type == 'internal':
            old_prepend_setting = settings.PREPEND_WWW
            settings.PREPEND_WWW = False
            c = Client()
            c.handler = LinkCheckHandler()
            with modify_settings(ALLOWED_HOSTS={'append': 'testserver'}):
                response = c.get(self.internal_url)
            self.status_code = response.status_code
            if response.status_code < 300:
                self.message = 'Working internal link'
                self.status = True
            elif response.status_code < 400:
                initial_location = response.get('Location')
                redirect_type = "permanent" if response.status_code == 301 else "temporary"
                with modify_settings(ALLOWED_HOSTS={'append': 'testserver'}):
                    response = c.get(self.internal_url, follow=True)
                if response.redirect_chain:
                    self.redirect_to, _ = response.redirect_chain[-1]
                else:
                    self.redirect_to = initial_location
                self.redirect_status_code = response.status_code
                self.status = response.status_code < 300
                redirect_result = "Working" if self.status else "Broken"
                self.message = f'{redirect_result} {redirect_type} redirect'
            else:
                self.status = False
                self.message = 'Broken internal link'

            # Check the anchor (if it exists)
            self.check_anchor(response.content)

            settings.PREPEND_WWW = old_prepend_setting
        else:
            self.status = False
            self.message = 'Invalid URL'

        if USE_REVERSION:
            # using test client will clear the RevisionContextManager stack.
            revision_context_manager.start()

        self.last_checked = now()
        self.save()
        return self.status

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

        # Reset all fields in case they were already set
        self.reset_for_check()

        request_params = {
            'allow_redirects': True,
            'headers': {'User-Agent': DEFAULT_USER_AGENT},
            'timeout': LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT,
            'verify': True,
        }
        try:
            try:
                # At first try a HEAD request
                fetch = requests.head
                response = fetch(self.external_url, **request_params)
                # If no exceptions occur, the SSL certificate is valid
                if self.external_url.startswith('https://'):
                    self.ssl_status = True
            except ConnectionError as e:
                # This error could also be caused by an incomplete root certificate bundle,
                # so let's retry without verifying the certificate
                if "unable to get local issuer certificate" in str(e):
                    request_params['verify'] = False
                    response = fetch(self.external_url, **request_params)
                else:
                    # Re-raise exception if it's definitely not a false positive
                    raise
            # If HEAD is not allowed, let's try with GET
            if response.status_code in [HTTPStatus.BAD_REQUEST, HTTPStatus.METHOD_NOT_ALLOWED]:
                logger.debug('HEAD is not allowed, retry with GET')
                fetch = requests.get
                response = fetch(self.external_url, **request_params)
            # If access is denied, possibly the user agent is blocked
            if response.status_code == HTTPStatus.FORBIDDEN:
                logger.debug('Forbidden, retry with different user agent')
                request_params['headers'] = {'User-Agent': FALLBACK_USER_AGENT}
                response = fetch(self.external_url, **request_params)
            # If URL contains hash anchor and is a valid HTML document, let's repeat with GET
            elif (
                self.has_anchor and
                response.ok and
                fetch == requests.head and
                'text/html' in response.headers.get('content-type')
            ):
                logger.debug('Retrieve content for anchor check')
                fetch = requests.get
                response = fetch(self.external_url, **request_params)
        except ReadTimeout:
            self.status = False
            self.message = 'Other Error: The read operation timed out'
            self.error_message = 'The read operation timed out'
        except ConnectionError as e:
            self.status = False
            self.message = self.error_message = format_connection_error(e)
            if 'SSLError' in str(e):
                self.ssl_status = False
        except Exception as e:
            self.status = False
            self.message = f'Other Error: {e}'
            self.error_message = str(e)
        else:
            self.status = response.status_code < 300
            self.message = f"{response.status_code} {response.reason}"
            logger.debug('Response message: %s', self.message)

            # If initial response was a redirect, return the initial return code
            if response.history:
                logger.debug('Redirect history: %r', response.history)
                if response.ok:
                    self.message = f'{response.history[0].status_code} {response.history[0].reason}'
                self.redirect_to = response.url
                self.redirect_status_code = response.status_code
                self.status_code = response.history[0].status_code
            else:
                self.status_code = response.status_code

            # Check the anchor (if it exists)
            if fetch == requests.get:
                self.check_anchor(response.text)
            if not request_params['verify']:
                self.message += ', SSL certificate could not be verified'

        # When a rate limit was hit or the server returned an internal error, do not update
        # the last_checked date so the result is not cached for EXTERNAL_RECHECK_INTERVAL minutes
        if (
            not self.status_code or
            self.status_code != HTTPStatus.TOO_MANY_REQUESTS and
            self.status_code < 500
        ):
            self.last_checked = now()
        self.save()
        return self.status

    def check_anchor(self, html):
        from linkcheck import parse_anchors

        scope = "internal" if self.internal else "external"

        # Only check when the URL contains an anchor
        if self.has_anchor:
            # Empty fragment '#' is always valid
            if not self.anchor:
                self.anchor_status = True
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
                        self.anchor_status = True
                        self.message += f', working {scope} hash anchor'
                    else:
                        self.anchor_status = False
                        self.message += f', broken {scope} hash anchor'
                        if not TOLERATE_BROKEN_ANCHOR:
                            self.status = False
        return self.anchor_status, self.anchor_message


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

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="content_type_and_object_id"),
        ]

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
    # If the underlying cause is a name resolution error, provide additional formatting
    if reason.startswith("NameResolutionError"):
        return format_name_resolution_error(reason)
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


def format_name_resolution_error(reason):
    """
    Helper function to provide better readable output of name resolution errors thrown by urllib3
    """
    resolution_reason = re.search(
        r"NameResolutionError\([\"']<urllib3\.connection\.HTTPSConnection object at 0x[0-9a-f]+>: (.+)[\"']\)",
        reason,
    )
    if resolution_reason:
        return f"Name Resolution Error: {resolution_reason[1]}"
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
