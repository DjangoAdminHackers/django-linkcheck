import logging
from datetime import timedelta

from django.apps import apps
from django.db import models
from django.test.client import ClientHandler
from django.utils import timezone

from .linkcheck_settings import (
    HTML_FIELD_CLASSES,
    IMAGE_FIELD_CLASSES,
    MAX_URL_LENGTH,
    URL_FIELD_CLASSES,
)
from .models import Link, Url

logger = logging.getLogger(__name__)


class LinkCheckHandler(ClientHandler):

    # Customize the ClientHandler to allow us removing some middlewares

    def load_middleware(self):
        self.ignore_keywords = ['reversion.middleware', 'MaintenanceModeMiddleware', 'raven_compat']
        super().load_middleware()
        new_request_middleware = []

        ####################################################
        # _request_middleware (is removed in newer django) #
        ####################################################
        if getattr(self, "_request_middleware", None):
            for method in self._request_middleware:
                ignored = False
                for keyword in self.ignore_keywords:
                    if method.__str__().count(keyword):
                        ignored = True
                        break
                if not ignored:
                    new_request_middleware.append(method)
            self._request_middleware = new_request_middleware

        ####################
        # _view_middleware #
        ####################
        new_view_middleware = []
        for method in self._view_middleware:
            ignored = False
            for keyword in self.ignore_keywords:
                if method.__str__().count(keyword):
                    ignored = True
                    break
            if not ignored:
                new_view_middleware.append(method)
        self._view_middleware = new_view_middleware

        ##########################
        # _response_middleware## #
        ##########################
        if getattr(self, "_response_middleware", None):
            new_response_middleware = []
            for method in self._response_middleware:
                ignored = False
                for keyword in self.ignore_keywords:
                    if method.__str__().count(keyword):
                        ignored = True
                        break
                if not ignored:
                    new_response_middleware.append(method)
            self._response_middleware = new_response_middleware

        #################################
        # _template_response_middleware #
        #################################
        if getattr(self, "_template_response_middleware", None):
            new_template_response_middleware = []
            for method in self._template_response_middleware:
                ignored = False
                for keyword in self.ignore_keywords:
                    if method.__str__().count(keyword):
                        ignored = True
                        break
                if not ignored:
                    new_template_response_middleware.append(method)
            self._template_response_middleware = new_template_response_middleware

        #########################
        # _exception_middleware #
        #########################
        new_exception_middleware = []
        for method in self._exception_middleware:
            ignored = False
            for keyword in self.ignore_keywords:
                if method.__str__().count(keyword):
                    ignored = True
                    break
            if not ignored:
                new_exception_middleware.append(method)
        self._exception_middleware = new_exception_middleware


def check_links(external_recheck_interval=10080, limit=-1, check_internal=True, check_external=True):
    """
    Return the number of links effectively checked.
    """

    urls = Url.objects.all()

    # An optimization for when check_internal is False
    if not check_internal:
        recheck_datetime = timezone.now() - timedelta(minutes=external_recheck_interval)
        urls = urls.exclude(last_checked__gt=recheck_datetime)

    check_count = 0
    for u in urls:
        status = u.check_url(check_internal=check_internal, check_external=check_external)
        check_count += 1 if status is not None else 0
        if -1 < limit <= check_count:
            break

    return check_count


def update_urls(urls, content_type, object_id):

    # Structure of urls param is [(field, link text, url), ... ]

    urls_created = links_created = 0
    new_url_ids = set()
    new_link_ids = set()

    for field, link_text, url in urls:

        if url is not None and url.startswith('#'):
            instance = content_type.get_object_for_this_type(id=object_id)
            url = instance.get_absolute_url() + url

        if len(url) > MAX_URL_LENGTH:
            # We cannot handle url longer than MAX_URL_LENGTH at the moment
            logger.warning('URL exceeding max length will be skipped: %s', url)
            continue

        url, url_created = Url.objects.get_or_create(url=url)

        link, link_created = Link.objects.get_or_create(
            url=url,
            field=field,
            text=link_text,
            content_type=content_type,
            object_id=object_id,
        )

        # Keep track of how many objects were created
        urls_created += url_created
        links_created += link_created

        # Keep track of object ids (no matter if created or existing)
        new_url_ids.add(url.id)
        new_link_ids.add(link.id)

    return {
        "urls": {
            "created": urls_created,
            "ids": new_url_ids,
        },
        "links": {
            "created": links_created,
            "ids": new_link_ids,
        },
    }


def find_all_links(linklists=None):

    if linklists is None:
        linklists = apps.get_app_config('linkcheck').all_linklists

    urls_created = links_created = 0
    new_url_ids = set()
    new_link_ids = set()

    urls_before = Url.objects.count()
    links_before = Link.objects.count()

    for linklist_name, linklist_cls in linklists.items():

        content_type = linklist_cls.content_type()
        linklists = linklist_cls().get_linklist()

        for linklist in linklists:
            object_id = linklist['object'].id
            urls = linklist['urls'] + linklist['images']
            if urls:
                new = update_urls(urls, content_type, object_id)

                urls_created += new["urls"]["created"]
                links_created += new["links"]["created"]

                new_url_ids.update(new["urls"]["ids"])
                new_link_ids.update(new["links"]["ids"])

    # Delete all urls and links which are no longer part of the link lists
    Url.objects.all().exclude(id__in=new_url_ids).delete()
    Link.objects.all().exclude(id__in=new_link_ids).delete()

    # Calculate diff
    urls_after = Url.objects.count()
    links_after = Link.objects.count()

    return {
        "urls": {
            "created": urls_created,
            "deleted": urls_before + urls_created - urls_after,
            "unchanged": urls_after - urls_created,
        },
        "links": {
            "created": links_created,
            "deleted": links_before + links_created - links_after,
            "unchanged": links_after - links_created,
        },
    }


def unignore():
    Link.objects.update(ignore=False)


# Utilities for testing models coverage

def is_interesting_field(field):
    return is_url_field(field) or is_image_field(field) or is_html_field(field)


def is_url_field(field):
    return any(isinstance(field, cls) for cls in URL_FIELD_CLASSES)


def is_image_field(field):
    return any(isinstance(field, cls) for cls in IMAGE_FIELD_CLASSES)


def is_html_field(field):
    return any(isinstance(field, cls) for cls in HTML_FIELD_CLASSES)


def has_active_field(klass):
    return any(
        field.name == 'active' and isinstance(field, models.BooleanField)
        for field in klass._meta.fields
    )


def get_ignore_empty_fields(klass):
    return [
        field
        for field in klass._meta.fields
        if is_interesting_field(field) and (field.blank or field.null)
    ]


def get_type_fields(klass, the_type):
    check_funcs = {
        'html': is_html_field,
        'url': is_url_field,
        'image': is_image_field,
    }
    check_func = check_funcs[the_type]
    return [field for field in klass._meta.fields if check_func(field)]


def is_model_covered(klass):
    app = apps.get_app_config('linkcheck')
    return any(linklist[1].model == klass for linklist in app.all_linklists.items())


def format_config(meta, active_field, html_fields, image_fields, url_fields, ignore_empty_fields):
    config = f'from { meta.app_label }.models import { meta.object_name }\n\n'
    config += f'class { meta.object_name }Linklist(Linklist):\n'
    config += f'    model = { meta.object_name }\n'
    if html_fields:
        config += f'    html_fields = [{", ".join(map(str, html_fields))}]\n'
    if image_fields:
        config += f'    image_fields = [{", ".join(map(str, image_fields))}]\n'
    if url_fields:
        config += f'    url_fields = [{", ".join(map(str, url_fields))}]\n'
    if ignore_empty_fields:
        config += f'    ignore_empty = [{", ".join(map(str, ignore_empty_fields))}]\n'
    if active_field:
        config += '    object_filter = {"active": True}\n'
    config += f'\nlinklists = {{\n    "{ meta.object_name }": { meta.object_name }Linklist,\n}}\n'
    return config


def get_suggested_linklist_config(klass):
    meta = klass._meta
    html_fields = get_type_fields(klass, 'html')
    url_fields = get_type_fields(klass, 'url')
    image_fields = get_type_fields(klass, 'image')
    active_field = has_active_field(klass)
    ignore_empty_fields = get_ignore_empty_fields(klass)
    return format_config(**{
        'meta': meta,
        'html_fields': html_fields,
        'url_fields': url_fields,
        'image_fields': image_fields,
        'active_field': active_field,
        'ignore_empty_fields': ignore_empty_fields,
    })


def get_coverage_data():
    """
    Check which models are covered by linkcheck
    This view assumes the key for link
    """
    covered = []
    uncovered = []
    for app in apps.get_app_configs():
        for model in app.get_models():
            should_append = False
            if getattr(model, 'get_absolute_url', None):
                should_append = True
            else:
                for field in model._meta.fields:
                    if is_interesting_field(field):
                        should_append = True
                        break
            if should_append:
                if is_model_covered(model):
                    covered.append(f'{model._meta.app_label}.{model._meta.object_name}')
                else:
                    uncovered.append((
                        f'{model._meta.app_label}.{model._meta.object_name}',
                        get_suggested_linklist_config(model),
                    ))

    return covered, uncovered
