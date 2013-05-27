from django.db import models
from django.test.client import ClientHandler
from django.template.loader import render_to_string

from datetime import datetime
from datetime import timedelta

from linkcheck.models import Link
from linkcheck.models import Url
from linkcheck_settings import MAX_URL_LENGTH
from linkcheck.models import  all_linklists

try:
    from sorl.thumbnail import ImageField
except:
    ImageField = None
try:
    from mcefield.custom_fields import MCEField
except:
    MCEField = None

class LinkCheckHandler(ClientHandler):
    #customize the ClientHandler to allow us removing some middlewares

    def load_middleware(self):
        self.ignore_keywords = ['reversion.middleware','MaintenanceModeMiddleware']
        super(LinkCheckHandler, self).load_middleware()
        new_request_middleware = []

        #############################_request_middleware#################################
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
        print 'reversion' in str(self._request_middleware)
        print 'reversion' in str(self._view_middleware)
        print 'reversion' in str(self._response_middleware)
        print 'reversion' in str(self._exception_middleware)

def check_links(external_recheck_interval=10080, limit=-1, check_internal=True, check_external=True):

    recheck_datetime = datetime.now() - timedelta(minutes=external_recheck_interval)
    
    urls = Url.objects.filter(still_exists__exact='TRUE').exclude(last_checked__gt=recheck_datetime)

    #if limit is specified set the limit
    if limit and limit > -1:
        urls = urls[:limit]

    for u in urls:
        u.check(check_internal=check_internal, check_external=check_external)

def update_urls(urls, content_type, object_id):
    # url structure = (field, link text, url)
    for field, link_text, url in urls:
        if url is not None and url.startswith('#'):
            instance = content_type.get_object_for_this_type(id=object_id)
            url = instance.get_absolute_url() + url
        if len(url)>MAX_URL_LENGTH: #we cannot handle url longer than MAX_URL_LENGTH at the moment
            continue
        u, created = Url.objects.get_or_create(url=url)
        l, created = Link.objects.get_or_create(url=u, field=field, text=link_text, content_type=content_type, object_id=object_id)
        u.still_exists = True
        u.save()

def find_all_links(all_linklists):
    all_links_dict = {}
    Url.objects.all().update(still_exists=False)
    for linklist_name, linklist_cls in all_linklists.items():
        content_type = linklist_cls.content_type()
        linklists = linklist_cls().get_linklist()
        for linklist in linklists:
            object_id = linklist['object'].id
            urls = linklist['urls']+linklist['images']
            if urls:
                update_urls(urls, content_type, object_id)
        all_links_dict[linklist_name] = linklists
    Url.objects.filter(still_exists=False).delete()

def unignore():
    Link.objects.update(ignore=False)


##Utilities for testing models coverage
def is_intresting_field(field):
    ''' linkcheck checks URLField, MCEField, ImageField'''
    if is_url_field(field) or is_image_field(field) or is_mce_field(field):
        return True
    return False

def is_url_field(field):
    if isinstance(field, models.URLField):
        return True

def is_image_field(field):
    if isinstance(field, models.ImageField):
        return True
    if ImageField and isinstance(field, ImageField):
        return True

def is_mce_field(field):
    if MCEField and isinstance(field, MCEField):
        return True

def has_active_field(klass):
    for field in klass._meta.fields:
        if field.name=='active' and isinstance(field, models.BooleanField):
            return True

def get_type_fields(klass, the_type):
    check_funcs = {
        'mce': is_mce_field, 
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
    for linklist in all_linklists.items():
        if linklist[1].model == klass:
            return True
    return False

def get_suggested_linklist(klass):
    meta = klass._meta
    is_target = bool(getattr(klass, 'get_absolute_url', False))
    html_fields = get_type_fields(klass, 'mce')
    url_fields = get_type_fields(klass, 'url')
    image_fields = get_type_fields(klass, 'image')
    active_field = has_active_field(klass)
    context = {
        'is_target': is_target, 
        'meta': meta, 
        'html_fields': html_fields, 
        'url_fields': url_fields, 
        'image_fields': image_fields, 
        'active_field': active_field, 
    }
    return render_to_string('linkcheck/suggested_linklist.html', context)

def get_coverage_data():
    '''
    Check which models are covered by linkcheck
    This view assumes the key for link
    '''
    all_model_list = []
    for app in models.get_apps():
        model_list = models.get_models(app)
        for model in model_list:
            should_append = False
            if getattr(model, 'get_absolute_url', None):
                should_append = True
            else:
                for field in model._meta.fields:                    
                    if is_intresting_field(field):
                        should_append=True
                        break
            if should_append:
                all_model_list.append(
                    (
                     '%s.%s' % (model._meta.app_label, model._meta.object_name), 
                     is_model_covered(model),
                     get_suggested_linklist(model),
                    )
                )
    return all_model_list

