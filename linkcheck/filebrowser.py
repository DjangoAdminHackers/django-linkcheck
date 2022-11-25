"""Integrate with django-filebrowser if present."""
import logging
import os.path

from django.conf import settings
from django.contrib import messages

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
        msg = (
            f"Please note. Uploading {url} has corrected {count} broken link{count > 1 and 's' or ''}. "
            "See the Link Manager for more details"
        )
        messages.success(sender, msg)


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
        msg = (
            f"Warning. Renaming {old_url} has caused {old_count} link{old_count > 1 and 's' or ''} to break. "
            "Please use the Link Manager to fix them"
        )
        messages.warning(sender, msg)

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
        msg = (
            f"Please note. Renaming {new_url} has corrected {new_count} broken link{new_count > 1 and 's' or ''}. "
            "See the Link Manager for more details"
        )
        messages.success(sender, msg)


def handle_delete(sender, path=None, **kwargs):
    logger.debug('deleted path %s with kwargs %r', path, kwargs)

    url = os.path.join(get_relative_media_url(), DIRECTORY, path)
    url_qs = Url.objects.filter(url=url).filter(status=True)
    count = url_qs.count()
    if count:
        url_qs.update(status=False, message="Missing Document")
        msg = (
            f"Warning. Deleting {url} has caused {count} link{count > 1 and 's' or ''} to break. "
            "Please use the Link Manager to fix them"
        )
        messages.warning(sender, msg)


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
