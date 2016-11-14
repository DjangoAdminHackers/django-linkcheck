#!/usr/bin/python
# -*- coding: utf8 -*-

from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.template.defaultfilters import striptags

from linkcheck.models import Link, Url

EMAIL_SUBJECT = "Found invalid links"

class Command(BaseCommand):

    help = "Goes through all broken links an notifies the owner"

    def handle(self, *args, **options):
        self.stdout.write("Sending reports...")
        links = Link.objects.filter(url__status=False)
        for link in links:
            links_with_same_mail = links.filter(alert_mail=link.alert_mail)

            from_email = settings.DEFAULT_FROM_EMAIL
            to_email = link.alert_mail
            subject = EMAIL_SUBJECT
            html = render_to_string('linkcheck/mail_report.html', {
                'links': links_with_same_mail
            })
            text = striptags(html)

            msg = EmailMultiAlternatives(subject, text, from_email, [to_email])
            msg.attach_alternative(html, "text/html")
            msg.send()

            links = links.exclude(alert_mail=link.alert_mail)

        return "Finished"