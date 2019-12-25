from django.apps import apps
from django.db import models
from django.test.client import ClientHandler
from django.utils import timezone

from datetime import timedelta

from .models import Link, Url
from .linkcheck_settings import MAX_URL_LENGTH, HTML_FIELD_CLASSES, IMAGE_FIELD_CLASSES, URL_FIELD_CLASSES


class LinkCheckHandler(ClientHandler):

    # Customize the ClientHandler to allow us removing some middlewares

    def load_middleware(self):
        self.ignore_keywords = ['reversion.middleware','MaintenanceModeMiddleware']
        super().load_middleware()
        new_request_middleware = []
        
        #############################_request_middleware#################################
        # _request_middleware is removed in newer django.
        if getattr(self, '_request_middleware', None):
            for method in self._request_middleware:
                ignored = False
                for keyword in self.ignore_keywords:
                    if method.__str__().count(keyword):
                        ignored = True
                        break
                if not ignored:
                    new_request_middleware.append(method)
            self._request_middleware = new_request_middleware
        
        #############################_view_middleware#################################
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

        #############################_response_middleware#################################
        if getattr(self, '_response_middleware', None):
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


        #############################_template_response_middleware#################################
        if getattr(self, '_template_response_middleware', None):
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

        #############################_exception_middleware#################################
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

    urls = Url.objects.filter(still_exists=True)

    # An optimization for when check_internal is False
    if not check_internal:
        recheck_datetime = timezone.now() - timedelta(minutes=external_recheck_interval)
        urls = urls.exclude(last_checked__gt=recheck_datetime)

    check_count = 0
    for u in urls:
        status = u.check_url(check_internal=check_internal, check_external=check_external)
        check_count += 1 if status is not None else 0
        if limit > -1 and check_count >= limit:
            break

    return check_count


def update_urls(urls, content_type, object_id):

    # Structure of urls param is [(field, link text, url), ... ]

    new_urls = new_links = 0

    for field, link_text, url in urls:

        if url is not None and url.startswith('#'):
            instance = content_type.get_object_for_this_type(id=object_id)
            url = instance.get_absolute_url() + url

        if len(url) > MAX_URL_LENGTH:
            # We cannot handle url longer than MAX_URL_LENGTH at the moment
            continue

        url, url_created = Url.objects.get_or_create(url=url)

        link, link_created = Link.objects.get_or_create(
            url=url,
            field=field,
            text=link_text,
            content_type=content_type,
            object_id=object_id,
        )

        url.still_exists = True
        url.save()
        new_urls += url_created
        new_links += link_created

    return new_urls, new_links


def find_all_links(linklists=None):

    if linklists is None:
        linklists = apps.get_app_config('linkcheck').all_linklists

    all_links_dict = {}
    urls_created = links_created = 0

    Url.objects.all().update(still_exists=False)

    for linklist_name, linklist_cls in linklists.items():

        content_type = linklist_cls.content_type()
        linklists = linklist_cls().get_linklist()

        for linklist in linklists:
            object_id = linklist['object'].id
            urls = linklist['urls'] + linklist['images']
            if urls:
                new_urls, new_links = update_urls(urls, content_type, object_id)
                urls_created += new_urls
                links_created += new_links
        all_links_dict[linklist_name] = linklists

    deleted = Url.objects.filter(still_exists=False).count()

    Url.objects.filter(still_exists=False).delete()

    return {
        'urls_deleted': deleted,
        'urls_created': urls_created,
        'links_created': links_created,
    }


def unignore():
    Link.objects.update(ignore=False)


# Utilities for testing models coverage

def is_interesting_field(field):
    if is_url_field(field) or is_image_field(field) or is_html_field(field):
        return True
    return False


def is_url_field(field):
    for cls in URL_FIELD_CLASSES:
        if isinstance(field, cls):
            return True


def is_image_field(field):
    for cls in IMAGE_FIELD_CLASSES:
        if isinstance(field, cls):
            return True


def is_html_field(field):
    for cls in HTML_FIELD_CLASSES:
        if isinstance(field, cls):
            return True


def has_active_field(klass):
    for field in klass._meta.fields:
        if field.name == 'active' and isinstance(field, models.BooleanField):
            return True


def get_ignore_empty_fields(klass):
    fields = []
    for field in klass._meta.fields:
        if is_interesting_field(field) and (field.blank or field.null):
            fields.append(field)
    return fields


def get_type_fields(klass, the_type):
    check_funcs = {
        'html': is_html_field,
        'url': is_url_field,
        'image': is_image_field,
    }
    check_func = check_funcs[the_type]
    fields = []
    for field in klass._meta.fields:
        if check_func(field):
            fields.append(field)
    return fields


def is_model_covered(klass):
    app = apps.get_app_config('linkcheck')
    for linklist in app.all_linklists.items():
        if linklist[1].model == klass:
            return True
    return False


def get_suggested_linklist_config(klass):
    meta = klass._meta
    html_fields = get_type_fields(klass, 'html')
    url_fields = get_type_fields(klass, 'url')
    image_fields = get_type_fields(klass, 'image')
    active_field = has_active_field(klass)
    ignore_empty_fields = get_ignore_empty_fields(klass)
    return {
        'meta': meta,
        'html_fields': html_fields,
        'url_fields': url_fields,
        'image_fields': image_fields,
        'active_field': active_field,
        'ignore_empty_fields': ignore_empty_fields,
    }


def get_coverage_data():
    """
    Check which models are covered by linkcheck
    This view assumes the key for link
    """
    all_model_list = []
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
                all_model_list.append({
                    'name': '%s.%s' % (model._meta.app_label, model._meta.object_name),
                    'is_covered': is_model_covered(model),
                    'suggested_config': get_suggested_linklist_config(model),
                })

    return all_model_list
