#!/usr/bin/python
# -*- coding: utf8 -*-

from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.template.defaultfilters import striptags

from linkcheck.models import Link, Url
from linkcheck.linkcheck_settings import DEFAULT_ALERT_EMAIL

EMAIL_SUBJECT = "Found invalid links"

class Command(BaseCommand):

    help = "Goes through all broken links an notifies the owner"

    def handle(self, *args, **options):
        links = Link.objects.filter(url__status=False)
        self.stdout.write("Found %s broken links." % links.count())

        if DEFAULT_ALERT_EMAIL:
            self.stdout.write("Sending report to %s with all broken links..." % DEFAULT_ALERT_EMAIL)
            self.send_report(links, to_email=DEFAULT_ALERT_EMAIL)

        self.stdout.write("Sending reports...")
        for link in links:
            links_with_same_mail = links.filter(alert_mail=link.alert_mail)
            self.send_report(links=links_with_same_mail)
            links = links.exclude(alert_mail=link.alert_mail)

        return "Finished."

    def send_report(self, links, to_email=None):
        if not to_email:
            to_email = links.first().alert_mail

        html = render_to_string('linkcheck/mail_report.html', {
            'links': links
        })
        text = striptags(html)

        msg = EmailMultiAlternatives(EMAIL_SUBJECT, text, settings.DEFAULT_FROM_EMAIL, [to_email])
        msg.attach_alternative(html, "text/html")
        msg.send()
