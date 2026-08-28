from celery import shared_task
from django.apps import apps

from .worker_tasks import do_check_instance_links, do_instance_post_save


@shared_task
def do_check_link(app: str, model: str, id: int, **kwargs):
    sender = apps.get_app_config(app).get_model(model)

    linklist_cls = sender._linklist

    instance = sender.objects.get(id=id)

    do_check_instance_links(sender, instance, linklist_cls)


@shared_task
def do_post_save(app: str, model: str, id: int, **kwargs):
    sender = apps.get_app_config(app).get_model(model)

    linklist_cls = sender._linklist

    instance = sender.objects.get(id=id)

    do_instance_post_save(sender, instance, linklist_cls, **kwargs)
