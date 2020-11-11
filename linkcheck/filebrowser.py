"""Integrate with django-filebrowser if present."""
import os.path

from django.conf import settings
from django.contrib import messages

try:
    from filebrowser.views import filebrowser_post_upload
    from filebrowser.views import filebrowser_post_rename
    from filebrowser.views import filebrowser_post_delete
    from filebrowser.settings import DIRECTORY
    FILEBROWSER_PRESENT = True
except ImportError:
    FILEBROWSER_PRESENT = False

from linkcheck.models import Url


def get_relative_media_url():
    if settings.MEDIA_URL.startswith('http'):
        relative_media_url = ('/'+'/'.join(settings.MEDIA_URL.split('/')[3:]))[:-1]
    else:
        relative_media_url = settings.MEDIA_URL
    return relative_media_url


def handle_upload(sender, path=None, **kwargs):
    url = os.path.join(get_relative_media_url(), kwargs['file'].url_relative)
    url_qs = Url.objects.filter(url=url).filter(status=False)
    count = url_qs.count()
    if count:
        url_qs.update(status=True, message='Working document link')
        msg = "Please note. Uploading %s has corrected %s broken link%s. See the Link Manager for more details" % (url, count, count > 1 and 's' or '')
        messages.info(sender, msg)


def handle_rename(sender, path=None, **kwargs):

    def isdir(filename):
        if filename.count('.'):
            return False
        else:
            return True

    old_url = os.path.join(get_relative_media_url(), DIRECTORY, path, kwargs['filename'])
    new_url = os.path.join(get_relative_media_url(), DIRECTORY, path, kwargs['new_filename'])
    # Renaming a file will cause it's urls to become invalid
    # Renaming a directory will cause the urls of all it's contents to become invalid
    old_url_qs = Url.objects.filter(url=old_url).filter(status=True)
    if isdir(kwargs['filename']):
        old_url_qs = Url.objects.filter(url__startswith=old_url).filter(status=True)
    old_count = old_url_qs.count()
    if old_count:
        old_url_qs.update(status=False, message='Missing Document')
        msg = "Warning. Renaming %s has caused %s link%s to break. Please use the Link Manager to fix them" % (old_url, old_count, old_count > 1 and 's' or '')
        messages.info(sender, msg)

    # The new directory may fix some invalid links, so we also check for that
    if isdir(kwargs['new_filename']):
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
        msg = "Please note. Renaming %s has corrected %s broken link%s. See the Link Manager for more details" % (new_url, new_count, new_count > 1 and 's' or '')
        messages.info(sender, msg)


def handle_delete(sender, path=None, **kwargs):

    url = os.path.join(get_relative_media_url(), DIRECTORY, path, kwargs['filename'])
    url_qs = Url.objects.filter(url=url).filter(status=True)
    count = url_qs.count()
    if count:
        url_qs.update(status=False, message='Missing Document')
        msg = "Warning. Deleting %s has caused %s link%s to break. Please use the Link Manager to fix them" % (url, count, count > 1 and 's' or '')
        messages.info(sender, msg)


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
