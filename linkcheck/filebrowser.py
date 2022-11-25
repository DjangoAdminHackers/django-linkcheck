"""Integrate with django-filebrowser if present."""
import logging
import os.path

from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

try:
    from filebrowser.settings import DIRECTORY
    from filebrowser.signals import (
        filebrowser_post_delete,
        filebrowser_post_rename,
        filebrowser_post_upload,
    )
    FILEBROWSER_PRESENT = True
except ImportError:
    FILEBROWSER_PRESENT = False

from linkcheck.models import Url

logger = logging.getLogger(__name__)


def get_relative_media_url():
    if settings.MEDIA_URL.startswith('http'):
        relative_media_url = ('/'+'/'.join(settings.MEDIA_URL.split('/')[3:]))[:-1]
    else:
        relative_media_url = settings.MEDIA_URL
    return relative_media_url


def handle_upload(sender, path=None, **kwargs):
    logger.debug('uploaded path %s with kwargs %r', path, kwargs)

    url = os.path.join(get_relative_media_url(), kwargs['file'].url)
    url_qs = Url.objects.filter(url=url).filter(status=False)
    count = url_qs.count()
    if count:
        url_qs.update(status=True, message="Working document link")
        msg = ngettext(
            "Uploading {} has corrected {} broken link.",
            "Uploading {} has corrected {} broken links.",
            count,
        ).format(url, count)
        messages.success(sender, '{}: {} {}'.format(
            _('Please note'),
            msg,
            _('See the Link Checker for more details.')
        ))


def handle_rename(sender, path=None, **kwargs):
    logger.debug('renamed path %s with kwargs %r', path, kwargs)

    def isdir(filename):
        if filename.count('.'):
            return False
        else:
            return True

    old_url = os.path.join(get_relative_media_url(), DIRECTORY, path)
    new_url = os.path.join(get_relative_media_url(), DIRECTORY, path.replace(kwargs['name'], kwargs['new_name']))
    # Renaming a file will cause it's urls to become invalid
    # Renaming a directory will cause the urls of all it's contents to become invalid
    old_url_qs = Url.objects.filter(url=old_url).filter(status=True)
    if isdir(kwargs['name']):
        old_url_qs = Url.objects.filter(url__startswith=old_url).filter(status=True)
    old_count = old_url_qs.count()
    if old_count:
        old_url_qs.update(status=False, message="Missing Document")
        msg = ngettext(
            "Renaming {} has caused {} link to break.",
            "Renaming {} has caused {} links to break.",
            old_count,
        ).format(old_url, old_count)
        messages.warning(sender, '{}: {} {}'.format(
            _('Warning'),
            msg,
            _('Please use the Link Checker to fix them.')
        ))

    # The new directory may fix some invalid links, so we also check for that
    if isdir(kwargs['new_name']):
        new_count = 0
        new_url_qs = Url.objects.filter(url__startswith=new_url).filter(status=False)
        for url in new_url_qs:
            if url.check_url():
                new_count += 1
    else:
        new_url_qs = Url.objects.filter(url=new_url).filter(status=False)
        new_count = new_url_qs.count()
        if new_count:
            new_url_qs.update(status=True, message='Working document link')
    if new_count:
        msg = ngettext(
            "Renaming {} has corrected {} broken link.",
            "Renaming {} has corrected {} broken links.",
            new_count,
        ).format(new_url, new_count)
        messages.success(sender, '{}: {} {}'.format(
            _('Please note'),
            msg,
            _('See the Link Checker for more details.')
        ))


def handle_delete(sender, path=None, **kwargs):
    logger.debug('deleted path %s with kwargs %r', path, kwargs)

    url = os.path.join(get_relative_media_url(), DIRECTORY, path)
    url_qs = Url.objects.filter(url=url).filter(status=True)
    count = url_qs.count()
    if count:
        url_qs.update(status=False, message="Missing Document")
        msg = ngettext(
            "Deleting {} has caused {} link to break.",
            "Deleting {} has caused {} links to break.",
            count,
        ).format(url, count)
        messages.warning(sender, '{}: {} {}'.format(
            _('Warning'),
            msg,
            _('Please use the Link Checker to fix them.')
        ))


def register_listeners():
    if FILEBROWSER_PRESENT:
        filebrowser_post_upload.connect(handle_upload)
        filebrowser_post_rename.connect(handle_rename)
        filebrowser_post_delete.connect(handle_delete)


def unregister_listeners():
    if FILEBROWSER_PRESENT:
        filebrowser_post_upload.disconnect(handle_upload)
        filebrowser_post_rename.disconnect(handle_rename)
        filebrowser_post_delete.disconnect(handle_delete)
