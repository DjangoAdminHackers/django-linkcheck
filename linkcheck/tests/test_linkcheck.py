import os
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import LiveServerTestCase, TestCase
from django.test.utils import override_settings
from django.urls import reverse

from linkcheck.linkcheck_settings import MAX_URL_LENGTH
from linkcheck.listeners import (
    disable_listeners,
    enable_listeners,
    linkcheck_worker,
    register_listeners,
    tasks_queue,
    unregister_listeners,
)
from linkcheck.models import Link, Url
from linkcheck.views import get_jquery_min_js

from .sampleapp.models import Author, Book, Journal


@override_settings(ROOT_URLCONF='linkcheck.tests.urls')
class InternalCheckTestCase(TestCase):

    def test_internal_check_mailto(self):
        uv = Url(url="mailto:nobody")
        uv.check_url()
        self.assertEqual(uv.status, None)
        self.assertEqual(uv.message, 'Email link (not automatically checked)')

    def test_internal_check_blank(self):
        uv = Url(url="")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Empty link')

    def test_same_page_anchor(self):
        uv = Url(url="#some_anchor")
        uv.check_url()
        self.assertEqual(uv.status, None)
        self.assertEqual(uv.message, 'Link to within the same page (not automatically checked)')

    def test_working_internal_anchor(self):
        uv = Url(url="/http/anchor/#anchor")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "Working internal link, working internal hash anchor")

    @patch("linkcheck.models.TOLERATE_BROKEN_ANCHOR", False)
    def test_broken_internal_anchor(self):
        uv = Url(url="/http/anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, "Working internal link, broken internal hash anchor")

    def test_broken_internal_anchor_tolerated(self):
        uv = Url(url="/http/anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "Working internal link, broken internal hash anchor")

    def test_redirect_working_internal_anchor(self):
        uv = Url(url="/http/redirect_to_anchor/#anchor")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "Working temporary redirect, working internal hash anchor")

    @patch("linkcheck.models.TOLERATE_BROKEN_ANCHOR", False)
    def test_redirect_broken_internal_anchor(self):
        uv = Url(url="/http/redirect_to_anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, "Working temporary redirect, broken internal hash anchor")

    def test_redirect_broken_internal_anchor_tolerated(self):
        uv = Url(url="/http/redirect_to_anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "Working temporary redirect, broken internal hash anchor")

    def test_internal_check_view_redirect(self):
        uv = Url(url="/admin/linkcheck")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "Working temporary redirect")
        uv = Url(url="/http/brokenredirect/")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Broken temporary redirect')

    def test_internal_check_found(self):
        uv = Url(url="/public/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working internal link')
        self.assertEqual(uv.type, 'internal')

    def test_internal_check_with_protocol(self):
        # "localhost" is configured as SITE_DOMAIN in settings
        uv = Url(url="http://localhost/public/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working internal link')
        self.assertEqual(uv.type, 'internal')

    def test_internal_check_broken_internal_link(self):
        uv = Url(url="/broken/internal/link")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Broken internal link')

    def test_internal_check_invalid_url(self):
        uv = Url(url="invalid/url")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Invalid URL')


class InternalMediaCheckTestCase(TestCase):
    def setUp(self):
        self.old_media_root = settings.MEDIA_ROOT
        settings.MEDIA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media')

    def tearDown(self):
        settings.MEDIA_ROOT = self.old_media_root

    def test_internal_check_media_missing(self):
        uv = Url(url="/media/not_found")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Missing Document')

    def test_internal_check_media_found(self):
        uv = Url(url="/media/found")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working file link')

    def test_internal_check_media_utf8(self):
        media_file = os.path.join(os.path.dirname(__file__), 'media', 'rückmeldung')
        open(media_file, 'a').close()
        self.addCleanup(os.remove, media_file)
        uv = Url(url="/media/r%C3%BCckmeldung")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working file link')
        # Also when the url is not encoded
        uv = Url(url="/media/rückmeldung")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, 'Working file link')


@override_settings(SITE_DOMAIN='example.com')
class ExternalCheckTestCase(LiveServerTestCase):
    def test_external_check_200(self):
        uv = Url(url=f"{self.live_server_url}/http/200/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_200_missing_cert(self):
        uv = Url(url=f"{self.live_server_url.replace('http://', 'https://')}/http/200/")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'SSL Error: wrong version number')
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_200_incomplete_cert(self):
        uv = Url(url="https://incomplete-chain.badssl.com/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK, SSL certificate could not be verified')
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_200_broken_anchor_incomplete_cert(self):
        uv = Url(url="https://incomplete-chain.badssl.com/#broken")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK, broken external hash anchor, SSL certificate could not be verified')
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_404_incomplete_cert(self):
        uv = Url(url="https://incomplete-chain.badssl.com/404")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, '404 Not Found, SSL certificate could not be verified')
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_200_utf8(self):
        uv = Url(url=f"{self.live_server_url}/http/200/r%C3%BCckmeldung/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')
        # Also when the url is not encoded
        uv = Url(url=f"{self.live_server_url}/http/200/rückmeldung/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')

    def test_external_check_301(self):
        uv = Url(url=f"{self.live_server_url}/http/301/")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, '301 Moved Permanently')
        self.assertEqual(uv.redirect_to, '')

    def test_external_check_301_followed(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect/301/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '301 Moved Permanently')
        self.assertEqual(uv.redirect_to, f'{self.live_server_url}/http/200/')

    def test_external_check_302_followed(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect/302/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '302 Found')
        self.assertEqual(uv.redirect_to, f'{self.live_server_url}/http/200/')

    def test_external_check_404(self):
        uv = Url(url=f"{self.live_server_url}/whatever/")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message.lower(), '404 not found')

    def test_external_check_redirect_final_404(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect_to_404/")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message.lower(), '404 not found')

    def test_external_check_get_only(self):
        # An URL that allows GET but not HEAD, linkcheck should fallback on GET.
        uv = Url(url=f"{self.live_server_url}/http/getonly/405/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')
        # Same test with other 40x error
        uv = Url(url=f"{self.live_server_url}/http/getonly/400/")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, '200 OK')

    def test_external_check_timedout(self):
        uv = Url(url=f"{self.live_server_url}/timeout/")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, 'Other Error: The read operation timed out')

    def test_working_external_anchor(self):
        uv = Url(url=f"{self.live_server_url}/http/anchor/#anchor")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "200 OK, working external hash anchor")

    @patch("linkcheck.models.TOLERATE_BROKEN_ANCHOR", False)
    def test_broken_external_anchor(self):
        uv = Url(url=f"{self.live_server_url}/http/anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, "200 OK, broken external hash anchor")

    def test_broken_external_anchor_tolerated(self):
        uv = Url(url=f"{self.live_server_url}/http/anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "200 OK, broken external hash anchor")

    def test_redirect_working_external_anchor(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect_to_anchor/#anchor")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "302 Found, working external hash anchor")

    @patch("linkcheck.models.TOLERATE_BROKEN_ANCHOR", False)
    def test_redirect_broken_external_anchor(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect_to_anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.status, False)
        self.assertEqual(uv.message, "302 Found, broken external hash anchor")

    def test_redirect_broken_external_anchor_tolerated(self):
        uv = Url(url=f"{self.live_server_url}/http/redirect_to_anchor/#broken-anchor")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "302 Found, broken external hash anchor")

    def test_video_with_time_anchor(self):
        uv = Url(url=f"{self.live_server_url}/static-files/video.mp4#t=2.0")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "200 OK")

    def test_forged_video_with_time_anchor(self):
        uv = Url(url=f"{self.live_server_url}/static-files/fake-video.mp4#t=2.0")
        uv.check_url()
        self.assertEqual(uv.status, True)
        self.assertEqual(uv.message, "200 OK, failed to parse HTML for anchor")


class ModelTestCase(TestCase):

    def test_str(self):
        Author.objects.create(name="John Smith", website="http://www.example.org/smith")
        self.assertEqual(
            str(Url.objects.first()),
            "http://www.example.org/smith",
        )
        self.assertEqual(
            str(Link.objects.first()),
            "http://www.example.org/smith (Author object (1))",
        )

    def test_repr(self):
        Author.objects.create(name="John Smith", website="http://www.example.org/smith")
        self.assertEqual(
            repr(Url.objects.first()),
            "<Url (id: 1, url: http://www.example.org/smith)>",
        )
        self.assertEqual(
            repr(Link.objects.first()),
            (
                "<Link (id: 1, url: <Url (id: 1, url: http://www.example.org/smith)>, "
                "source: <Author: Author object (1)>)>"
            ),
        )


class ChecklinksTestCase(TestCase):

    def test_checklinks_command(self):
        Book.objects.create(title='My Title', description="""
            Here's an external link: <a href="http://www.example.org">External</a>,
            an internal link: <a href="/public/">Internal</a>,
            and an image: <img src="http://www.example.org/logo.png" alt="logo">""")

        out = StringIO()
        call_command('checklinks', stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 10080 minutes.\n"
            "1 internal URLs and 0 external URLs have been checked.\n"
        )

        yesterday = datetime.now() - timedelta(days=1)
        Url.objects.all().update(last_checked=yesterday)
        out = StringIO()
        call_command('checklinks', externalinterval=20, stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 20 minutes.\n"
            "1 internal URLs and 2 external URLs have been checked.\n"
        )

        Url.objects.all().update(last_checked=yesterday)
        out = StringIO()
        call_command('checklinks', externalinterval=20, limit=1, stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Checking all links that haven't been tested for 20 minutes.\n"
            "Will run maximum of 1 checks this run.\n"
            "1 internal URLs and 1 external URLs have been checked.\n"
        )


class FindingLinksTestCase(TestCase):
    def test_found_links(self):
        self.assertEqual(Url.objects.all().count(), 0)
        Book.objects.create(title='My Title', description="""
            Here's a link: <a href="http://www.example.org">Example</a>,
            and an image: <img src="http://www.example.org/logo.png" alt="logo">""")
        self.assertEqual(Url.objects.all().count(), 2)
        self.assertQuerysetEqual(
            Url.objects.all().order_by('url'),
            ["http://www.example.org", "http://www.example.org/logo.png"],
            transform=lambda obj: obj.url
        )

    def test_urls_exceeding_max_length(self):
        self.assertEqual(Url.objects.all().count(), 0)
        with self.assertLogs(logger="linkcheck", level="WARN") as cm:
            Book.objects.create(
                title="My Title",
                description=(
                    "Here's a link: <a href='http://www.example.org'>Example</a>, and here's a url exceeding "
                    f"the max length: <img src='http://www.example.org/{MAX_URL_LENGTH * 'X'}' alt='logo'>"
                ),
            )
        # We skip urls which are too long because we can't store them in the database
        self.assertIn(
            (
                "WARNING:linkcheck.listeners:URL exceeding max length will be skipped: "
                f"http://www.example.org/{MAX_URL_LENGTH * 'X'}"
            ),
            cm.output,
        )
        self.assertEqual(Url.objects.all().count(), 1)

    def test_empty_url_field(self):
        """
        Test that URLField empty content is excluded depending on ignore_empty list.
        """
        all_linklists = apps.get_app_config('linkcheck').all_linklists
        all_linklists['Authors'].ignore_empty = ['website']
        try:
            Author.objects.create(name="William Shakespeare")
            Author.objects.create(name="John Smith", website="http://www.example.org/smith")
            self.assertEqual(Url.objects.all().count(), 1)
        finally:
            all_linklists['Authors'].ignore_empty = []
        Author.objects.create(name="Alphonse Daudet")
        # This time, the empty 'website' is extracted
        self.assertEqual(Url.objects.all().count(), 2)

    def test_findlinks_command(self):
        # Disable listeners to only check the management command
        with disable_listeners():
            Author.objects.create(name="John Smith", website="https://www.example.org/smith")
            self.assertEqual(
                findlinks(),
                "Updating all links...\n"
                "Urls: 1 created, 0 deleted, 0 unchanged\n"
                "Links: 1 created, 0 deleted, 0 unchanged\n"
            )
            Author.objects.create(name="John Doe", website="https://www.example.org/doe")
            Book.objects.create(
                title='My Title',
                description="My fav author: <a href='https://www.example.org/doe'>John Doe</a>"
            )
            self.assertEqual(
                findlinks(),
                "Updating all links...\n"
                "Urls: 1 created, 0 deleted, 1 unchanged\n"
                "Links: 2 created, 0 deleted, 1 unchanged\n"
            )
            Author.objects.get(name="John Doe").delete()
            self.assertEqual(
                findlinks(),
                "Updating all links...\n"
                "Urls: 0 created, 0 deleted, 2 unchanged\n"
                "Links: 0 created, 1 deleted, 2 unchanged\n"
            )
            Book.objects.first().delete()
            self.assertEqual(
                findlinks(),
                "Updating all links...\n"
                "Urls: 0 created, 1 deleted, 1 unchanged\n"
                "Links: 0 created, 1 deleted, 1 unchanged\n"
            )


class ObjectsUpdateTestCase(TestCase):
    def test_update_object(self):
        """
        Test that updating a broken URL in an object also updates the
        corresponding Link, and don't leak the old URL.
        """
        bad_url = "/broken/internal/link"
        good_url = "/public/"
        author = Author.objects.create(name="John Smith", website=bad_url)
        self.assertEqual(
            Link.objects.filter(ignore=False, url__status=False).count(),
            1
        )
        self.assertEqual(
            Link.objects.filter(ignore=False, url__status=True).count(),
            0
        )
        self.assertEqual(Url.objects.all().count(), 1)
        self.assertEqual(Url.objects.all()[0].url, bad_url)
        # Fix the link
        author.website = good_url
        author.save()
        self.assertEqual(
            Link.objects.filter(ignore=False, url__status=False).count(),
            0
        )
        self.assertEqual(
            Link.objects.filter(ignore=False, url__status=True).count(),
            1
        )
        self.assertEqual(Url.objects.all().count(), 1)
        self.assertEqual(Url.objects.all()[0].url, good_url)


class RegisteringTests(TestCase):
    good_url = "/public/"

    def test_unregister(self):
        self.assertEqual(Link.objects.count(), 0)
        unregister_listeners()
        Author.objects.create(name="John Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 0)
        register_listeners()
        Author.objects.create(name="Jill Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 1)

    def test_disable_listeners(self):
        self.assertEqual(Link.objects.count(), 0)
        with disable_listeners():
            Author.objects.create(name="John Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 0)
        Author.objects.create(name="Jill Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 1)

    def test_enable_listeners(self):
        self.assertEqual(Link.objects.count(), 0)
        unregister_listeners()
        with enable_listeners():
            Author.objects.create(name="John Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 1)
        Author.objects.create(name="Jill Smith", website=self.good_url)
        self.assertEqual(Link.objects.count(), 1)
        register_listeners()


class QueueTests(TestCase):
    def test_queue_handling_continue_on_task_crash(self):
        assert tasks_queue.empty() is True

        def raising():
            raise RuntimeError("Failing task")

        def passing():
            pass

        for func in (raising, passing):
            tasks_queue.put({
                'target': func,
                'args': (),
                'kwargs': {},
            })
        with self.assertLogs() as cm:
            linkcheck_worker(block=False)
        self.assertEqual(
            cm.output[0].split('\n')[0],
            'ERROR:linkcheck.listeners:RuntimeError while running raising with '
            'args=() and kwargs={}: Failing task'
        )


class ViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'admin@example.org', 'password')

    def test_display_url(self):
        Book.objects.create(
            title='My Title', description="Here's a link: <a href='http://www.example.org'>Example</a>"
        )
        Author.objects.create(name="John Smith", website="http://www.example.org#john")
        self.assertEqual(Link.objects.count(), 2)
        self.assertEqual(
            set([link.display_url for link in Link.objects.all()]),
            set(["http://www.example.org", "http://www.example.org#john"]),
        )

    def test_report_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('linkcheck_report'))
        self.assertContains(response, "<h1>Link Checker</h1>")

    def test_report_ignore_unignore(self):
        Author.objects.create(name="John Smith", website="http://www.example.org/john")
        self.client.force_login(self.user)
        link = Link.objects.first()
        self.assertFalse(link.ignore)
        response = self.client.post(
            reverse('linkcheck_report') + f"?ignore={link.pk}",
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json(), {'link': link.pk})
        link.refresh_from_db()
        self.assertTrue(link.ignore)
        response = self.client.post(
            reverse('linkcheck_report') + f"?unignore={link.pk}",
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json(), {'link': link.pk})
        link.refresh_from_db()
        self.assertFalse(link.ignore)

    def test_report_recheck(self):
        Author.objects.create(name="John Smith", website="http://www.example.org/john")
        self.client.force_login(self.user)
        link = Link.objects.first()
        response = self.client.post(
            reverse('linkcheck_report') + f"?recheck={link.pk}",
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json(), {
            'colour': 'red',
            'links': [link.pk],
            'message': '404 Not Found',
        })

    def test_coverage_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('linkcheck_coverage'))
        self.assertContains(
            response,
            '<tr><td>sampleapp.Book</td>'
            '<td style="font-weight: bold;color:green;">Yes</td>'
            '<td style="font-weight: bold;color:green;"></td></tr>',
            html=True,
        )


class GetJqueryMinJsTestCase(TestCase):
    def test(self):
        self.assertEqual(
            'admin/js/vendor/jquery/jquery.min.js', get_jquery_min_js()
        )


class FixtureTestCase(TestCase):
    fixtures = ['linkcheck/tests/sampleapp/fixture.json']

    def test_fixture(self):
        self.assertEqual(Book.objects.count(), 1)


class FilterCallableTestCase(TestCase):
    def test_filter_callable(self):
        all_linklists = apps.get_app_config('linkcheck').all_linklists
        all_linklists['Journals'].html_fields = []
        Journal.objects.create(title='My Title', description="""
            My description <a href="http://www.example.org">Example</a>""")
        Journal.objects.create(title='My Title', version=1, description="""
            My new description <a href="http://www.example.org">Example</a>""")
        all_linklists['Journals'].html_fields = ['description']
        # assert there are two versions of the same journal
        self.assertEqual(Journal.objects.count(), 2)
        # assert command just finds the latest version of same journals
        self.assertEqual(
            findlinks(),
            "Updating all links...\n"
            "Urls: 1 created, 0 deleted, 0 unchanged\n"
            "Links: 1 created, 0 deleted, 0 unchanged\n"
        )


def findlinks():
    """
    Helper function for running the findlinks command and checking its output
    """
    out = StringIO()
    call_command('findlinks', stdout=out)
    return out.getvalue()
