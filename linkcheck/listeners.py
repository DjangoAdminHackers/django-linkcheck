import logging
import sys
from contextlib import contextmanager
from functools import partial
from queue import Empty, LifoQueue
from threading import Thread

from django.apps import apps
from django.db import transaction
from django.db.models import signals as model_signals

from linkcheck.models import Link, Url

from . import filebrowser
from .linkcheck_settings import LINKCHECK_IN_CELERY
from .worker_tasks import (
    do_check_instance_links,
    do_instance_post_save,
    do_instance_pre_delete,
)

if LINKCHECK_IN_CELERY:
    from .celery import do_check_link, do_post_save

logger = logging.getLogger(__name__)


tasks_queue = LifoQueue()
worker_running = False
tests_running = len(sys.argv) > 1 and sys.argv[1] == 'test' or sys.argv[0].endswith('runtests.py')


def linkcheck_worker(block=True):
    global worker_running  # noqa
    while tasks_queue.not_empty:
        try:
            task = tasks_queue.get(block=block)
        except Empty:
            break
        # An error in any task should not stop the worker from continuing with the queue
        try:
            task['target'](*task['args'], **task['kwargs'])
        except Exception as e:
            logger.exception(
                "%s while running %s with args=%r and kwargs=%r: %s",
                type(e).__name__,
                task['target'].__name__,
                task['args'],
                task['kwargs'],
                e
            )
        tasks_queue.task_done()
    worker_running = False


def start_worker():
    global worker_running  # noqa
    if worker_running is False:
        worker_running = True
        t = Thread(target=linkcheck_worker)
        t.daemon = True
        t.start()


def check_instance_links(sender, instance, **kwargs):
    """
    When an object is saved:
        new Link/Urls are created, checked

    When an object is modified:
        new link/urls are created, checked
        existing link/urls are checked
        Removed links are deleted
    """
    linklist_cls = sender._linklist

    # Don't run in a separate thread if we are running tests
    if tests_running:
        do_check_instance_links(sender, instance, linklist_cls)
    elif LINKCHECK_IN_CELERY:
        # We're not working in the same db/transaction context,
        # so we need to ensure the task is only run after any transaction is committed
        transaction.on_commit(partial(
            do_check_link.apply_async,
            kwargs={
                "app": sender._meta.app_label,
                "model": sender.__name__,
                "id": instance.id,
            },
        ))
    else:
        tasks_queue.put({
            'target': do_check_instance_links,
            'args': (sender, instance, linklist_cls, True),
            'kwargs': {}
        })
        start_worker()


def delete_instance_links(sender, instance, **kwargs):
    """
    Delete all links belonging to a model instance when that instance is deleted
    """
    linklist_cls = sender._linklist
    content_type = linklist_cls.content_type()
    old_links = Link.objects.filter(content_type=content_type, object_id=instance.pk)
    old_links.delete()


def instance_pre_save(sender, instance, raw=False, **kwargs):
    if instance._state.adding or not instance.pk or raw:
        # Ignore unsaved instances or raw imports
        return
    current_url = instance.get_absolute_url()
    previous_url = sender.objects.get(pk=instance.pk).get_absolute_url()
    setattr(instance, '__previous_url', previous_url)
    if previous_url == current_url:
        return
    else:
        if previous_url is not None:
            old_urls = Url.objects.filter(url__startswith=previous_url)
            old_urls.update(status=False, message='Broken internal link')
        if current_url is not None:
            new_urls = Url.objects.filter(url__startswith=current_url)
            # Mark these urls' status as False, so that post_save will check them
            new_urls.update(status=False, message='Should be checked now!')


def instance_post_save(sender, instance, **kwargs):
    # Ignore raw imports
    if kwargs.get('raw'):
        return

    linklist_cls = sender._linklist

    if tests_running:
        do_instance_post_save(sender, instance, linklist_cls, **kwargs)
    elif LINKCHECK_IN_CELERY:
        # We're not working in the same db/transaction context,
        # so we need to ensure the task is only run after any transaction is committed
        transaction.on_commit(partial(
            do_post_save.apply_async,
            kwargs={
                "app": sender._meta.app_label,
                "model": sender.__name__,
                "id": instance.id,
            } | ({"created": kwargs["created"]} if "created" in kwargs else {}),
        ))
    else:
        tasks_queue.put({
            'target': do_instance_post_save,
            'args': (sender, instance, linklist_cls),
            'kwargs': kwargs
        })
        start_worker()


def register_listeners():
    # 1. register listeners for the objects that contain Links
    for linklist_name, linklist_cls in apps.get_app_config('linkcheck').all_linklists.items():
        model_signals.post_save.connect(check_instance_links, sender=linklist_cls.model)
        model_signals.post_delete.connect(delete_instance_links, sender=linklist_cls.model)

        # 2. register listeners for the objects that are targets of Links,
        # only when get_absolute_url() is defined for the model
        if getattr(linklist_cls.model, 'get_absolute_url', None):
            model_signals.pre_save.connect(instance_pre_save, sender=linklist_cls.model)
            model_signals.post_save.connect(instance_post_save, sender=linklist_cls.model)
            model_signals.pre_delete.connect(do_instance_pre_delete, sender=linklist_cls.model)

    filebrowser.register_listeners()


def unregister_listeners():
    # 1. register listeners for the objects that contain Links
    for linklist_name, linklist_cls in apps.get_app_config('linkcheck').all_linklists.items():
        model_signals.post_save.disconnect(check_instance_links, sender=linklist_cls.model)
        model_signals.post_delete.disconnect(delete_instance_links, sender=linklist_cls.model)

        # 2. register listeners for the objects that are targets of Links,
        # only when get_absolute_url() is defined for the model
        if getattr(linklist_cls.model, 'get_absolute_url', None):
            model_signals.pre_save.disconnect(instance_pre_save, sender=linklist_cls.model)
            model_signals.post_save.disconnect(instance_post_save, sender=linklist_cls.model)
            model_signals.pre_delete.disconnect(do_instance_pre_delete, sender=linklist_cls.model)

    filebrowser.unregister_listeners()


@contextmanager
def enable_listeners(*args, **kwargs):
    register_listeners()
    try:
        yield
    finally:
        unregister_listeners()


@contextmanager
def disable_listeners(*args, **kwargs):
    unregister_listeners()
    try:
        yield
    finally:
        register_listeners()
