import logging
import time

from linkcheck.models import Link, Url

from . import update_lock
from .linkcheck_settings import MAX_URL_LENGTH

logger = logging.getLogger(__name__)


def do_check_instance_links(sender, instance, linklist_cls, wait=False):
    # On some installations, this wait time might be enough for the
    # thread transaction to account for the object change (GH #41).
    # A candidate for the future post_commit signal.

    if wait:
        time.sleep(0.1)
    with update_lock:
        content_type = linklist_cls.content_type()
        new_links = []
        old_links = Link.objects.filter(content_type=content_type, object_id=instance.pk)

        linklists = linklist_cls().get_linklist(extra_filter={'pk': instance.pk})

        if not linklists:
            # This object is no longer watched by linkcheck according to object_filter
            links = []
        else:
            linklist = linklists[0]
            links = linklist['urls']+linklist['images']

        for link in links:
            # url structure = (field, link text, url)
            url = link[2]
            if url.startswith('#'):
                url = instance.get_absolute_url() + url

            if len(url) > MAX_URL_LENGTH:
                # We cannot handle url longer than MAX_URL_LENGTH at the moment
                logger.warning('URL exceeding max length will be skipped: %s', url)
                continue

            u, created = Url.objects.get_or_create(url=url)
            l, created = Link.objects.get_or_create(
                url=u, field=link[0], text=link[1], content_type=content_type, object_id=instance.pk
            )
            new_links.append(l.id)
            u.check_url()

        gone_links = old_links.exclude(id__in=new_links)
        gone_links.delete()


def do_instance_post_save(sender, instance, linklist_cls, **kwargs):
    current_url = instance.get_absolute_url()
    previous_url = getattr(instance, '__previous_url', None)
    # We assume returning None from get_absolute_url means that this instance doesn't have a URL
    # Not sure if we should do the same for '' as this could refer to '/'
    if current_url is not None and current_url != previous_url:
        linklist_cls = sender._linklist
        active = linklist_cls.objects().filter(pk=instance.pk).count()

        if kwargs['created'] or (not active):
            new_urls = Url.objects.filter(url__startswith=current_url)
        else:
            new_urls = Url.objects.filter(status=False).filter(url__startswith=current_url)

        if new_urls:
            for url in new_urls:
                url.check_url()


def do_instance_pre_delete(sender, instance, **kwargs):
    instance.linkcheck_deleting = True
    deleted_url = instance.get_absolute_url()
    if deleted_url:
        old_urls = Url.objects.filter(url__startswith=deleted_url).exclude(status=False)
        if old_urls:
            old_urls.update(status=False, message='Broken internal link')
