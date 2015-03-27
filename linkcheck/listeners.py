import os.path
import sys
from threading import Thread

from django.conf import settings
from django.db.models import signals as model_signals

try:
    from filebrowser.views import filebrowser_post_upload
    from filebrowser.views import filebrowser_post_rename
    from filebrowser.views import filebrowser_post_delete
    from filebrowser.settings import DIRECTORY
    FILEBROWSER_PRESENT = True
except ImportError:
    FILEBROWSER_PRESENT = False

from linkcheck.models import all_linklists, Url, Link

listeners = []
# a global variable, showing whether linkcheck is still working
still_updating = False

#1, register listeners for the objects that contain Links
for linklist_name, linklist_cls in all_linklists.items():
    
    def check_instance_links(sender, instance, linklist_cls=linklist_cls, **kwargs):
        '''
        When an object is saved:
            new Link/Urls are created, checked
        When an object is modified:
            new Link/Urls are created, checked
            existing Link/Urls are checked
            disappering Links are deleted
        '''
        def do_check_instance_links(sender, instance, linklist_cls=linklist_cls):

            try:
                still_updating = True
                content_type = linklist_cls.content_type()
                new_links = []
                old_links = Link.objects.filter(content_type=content_type, object_id=instance.pk)

                linklists = linklist_cls().get_linklist(extra_filter={'pk':instance.pk,})

                if not linklists:
                    # This object is no longer watched by linkcheck according to object_filter
                    links = []
                else:
                    linklist = linklists[0]
                    links = linklist['urls']+linklist['images']
                    
                for link in links:
                    # url structure = (field, link text, url)
                    url = link[2]
                    internal_hash = False
                    if url.startswith('#'):
                        internal_hash = url
                        url = instance.get_absolute_url() + url
                    u, created = Url.objects.get_or_create(url=url)
                    l, created = Link.objects.get_or_create(url=u, field=link[0], text=link[1], content_type=content_type, object_id=instance.pk)
                    new_links.append(l.id)
                    u.still_exists = True
                    if internal_hash:
                        setattr(u, '_internal_hash', internal_hash)
                        setattr(u, '_instance', instance)
                    u.check()
                    
                gone_links = old_links.exclude(id__in=new_links)
                gone_links.delete()
                
            finally:
                still_updating = False

        # Don't run in a separate thread if we are running tests
        if len(sys.argv)>1 and sys.argv[1] == 'test' or sys.argv[0] == 'runtests.py':
            do_check_instance_links(sender, instance, linklist_cls,)
        else:
            t = Thread(target=do_check_instance_links, args=(sender, instance, linklist_cls,))
            t.start()

    listeners.append(check_instance_links)
    model_signals.post_save.connect(listeners[-1], sender=linklist_cls.model)

    def delete_instance_links(sender, instance, linklist_cls=linklist_cls, **kwargs):
        '''delete all its links when an object is deleted'''
        content_type = linklist_cls.content_type()
        old_links = Link.objects.filter(content_type=content_type, object_id=instance.pk)
        old_links.delete()
    listeners.append(delete_instance_links)
    model_signals.post_delete.connect(listeners[-1], sender=linklist_cls.model)

#2, register listeners for the objects that are targets of Links, only when get_absolute_url() is defined for the model. 
    if getattr(linklist_cls.model, 'get_absolute_url', None):
        def instance_pre_save(sender, instance, ModelCls=linklist_cls.model, **kwargs):
            current_url = instance.get_absolute_url()
            try:
                previous = ModelCls.objects.get(pk=instance.pk)
                #log.debug('instance exists modifying')
                previous_url = previous.get_absolute_url()
                setattr(instance, '__previous_url', previous_url)
                if previous_url == current_url:
                    #log.debug('url did not change, return')
                    return
                else:
                    #log.debug('url changed')
                    old_urls = Url.objects.filter(url__startswith=previous_url)
                    if old_urls:
                        old_urls.update(status=False, message='Broken internal link')
                    new_urls = Url.objects.filter(url__startswith=current_url)
                    if new_urls:
                        # mark these urls' status as False, so that post_save will check them
                        new_urls.update(status=False, message='Should be checked now!')
            except:
                #log.debug('new instance, post_save is in charge of this')
                pass
    
        listeners.append(instance_pre_save)
        model_signals.pre_save.connect(listeners[-1], sender=linklist_cls.model)
    
    
        def instance_post_save(sender, instance, ModelCls=linklist_cls.model, linklist=linklist_cls, **kwargs):
            def do_instance_post_save(sender, instance, ModelCls=ModelCls, linklist=linklist_cls, **kwargs):
                current_url = instance.get_absolute_url()
                previous_url = getattr(instance, '__previous_url', None)
                # We assume returning None from get_absolute_url means that this instance doesn't have a URL
                # Not sure if we should do the same for '' as this could refer to '/'
                if current_url!=None and current_url != previous_url:
        
                    active = linklist.objects().filter(pk=instance.pk).count()
        
                    if kwargs['created'] or (not active):
                        new_urls = Url.objects.filter(url__startswith=current_url)
                    else:
                        new_urls = Url.objects.filter(status=False).filter(url__startswith=current_url)
        
                    if new_urls:
                        for url in new_urls:
                            url.check()
            if len(sys.argv)>1 and sys.argv[1] == 'test' or sys.argv[0] == 'runtests.py':
                do_instance_post_save(sender, instance, ModelCls, **kwargs)
            else:
                t = Thread(target=do_instance_post_save, args=(sender, instance, ModelCls,), kwargs=kwargs)
                t.start()
    
        listeners.append(instance_post_save)
        model_signals.post_save.connect(listeners[-1], sender=linklist_cls.model)
    
    
        def instance_pre_delete(sender, instance, ModelCls=linklist_cls.model,  **kwargs):
            instance.linkcheck_deleting = True
            deleted_url = instance.get_absolute_url()
            if deleted_url:
                old_urls = Url.objects.filter(url__startswith=deleted_url).exclude(status=False)
                if old_urls:
                    old_urls.update(status=False, message='Broken internal link')
        listeners.append(instance_pre_delete)
        model_signals.pre_delete.connect(listeners[-1], sender=linklist_cls.model)


################################################
# Integrate with django-filebrowser if present #
################################################

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
        msg = "Please note. Uploading %s has corrected %s broken link%s. See the Link Manager for more details" % (url, count, count>1 and 's' or '')
        sender.user.message_set.create(message=msg)


def handle_rename(sender, path=None, **kwargs):
    old_url = os.path.join(get_relative_media_url(), DIRECTORY, path, kwargs['filename'])
    new_url = os.path.join(get_relative_media_url(), DIRECTORY, path, kwargs['new_filename'])
    # rename a file will cause the urls to it invalid
    # rename a directory will cause the urls to its files invalid
    old_url_qs = Url.objects.filter(url=old_url).filter(status=True)
    if isdir(kwargs['filename']):
        old_url_qs = Url.objects.filter(url__startswith=old_url).filter(status=True)
    old_count = old_url_qs.count()
    if old_count:
        old_url_qs.update(status=False, message='Missing Document')
        msg = "Warning. Renaming %s has caused %s link%s to break. Please use the Link Manager to fix them" % (old_url, old_count, old_count>1 and 's' or '')
        sender.user.message_set.create(message=msg)
        
    # the new directory may fix some invalid links, so we make a check here.
    if isdir(kwargs['new_filename']):
        new_count = 0
        new_url_qs = Url.objects.filter(url__startswith=new_url).filter(status=False)
        for url in new_url_qs:
            if url.check():
                new_count += 1
    else:
        new_url_qs = Url.objects.filter(url=new_url).filter(status=False)
        new_count = new_url_qs.count()
        if new_count:
            new_url_qs.update(status=True, message='Working document link')
    if new_count:
        msg = "Please note. Renaming %s has corrected %s broken link%s. See the Link Manager for more details" % (new_url, new_count, new_count>1 and 's' or '')
        sender.user.message_set.create(message=msg)


def handle_delete(sender, path=None, **kwargs):
    url = os.path.join(get_relative_media_url(), DIRECTORY, path, kwargs['filename'])
    url_qs = Url.objects.filter(url=url).filter(status=True)
    count = url_qs.count()
    if count:
        url_qs.update(status=False, message='Missing Document')
        msg = "Warning. Deleting %s has caused %s link%s to break. Please use the Link Manager to fix them" % (url, count, count>1 and 's' or '')
        sender.user.message_set.create(message=msg)


if FILEBROWSER_PRESENT:
    filebrowser_post_upload.connect(handle_upload)
    filebrowser_post_rename.connect(handle_rename)
    filebrowser_post_delete.connect(handle_delete)


def isdir(filename):
    '''!!!only used for filebrowser'''
    if filename.count('.'):
        return False
    else:
        return True
