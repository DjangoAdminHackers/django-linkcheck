from django.views.decorators.csrf import csrf_exempt

from itertools import groupby
from operator import itemgetter

try:
    import simplejson
except:
    from django.utils import simplejson
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.loader import render_to_string
from django import forms
from django.conf import settings
from django.db import models

from linkcheck.linkcheck_settings import RESULTS_PER_PAGE
from linkcheck.models import Link, all_linklists
try:
    from sorl.thumbnail import ImageField
except:
    ImageField = None
try:
    from mcefield.custom_fields import MCEField
except:
    MCEField = None

try:
    from django.contrib.admin.templatetags.adminmedia import admin_media_prefix
    # For backwards compatibility allow either of these but prefer admin_media_prefix
    admin_static = admin_media_prefix() or settings.STATIC_URL
except ImportError:
    # However - admin_media_prefix was removed in Django 1.5
    admin_static = settings.STATIC_URL

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

@staff_member_required
def coverage(request):
    '''
    Check which models are covered by linkcheck
    This view assumes the key for link
    '''
    all_model_list = []
    for app in models.get_apps():
        model_list = models.get_models(app)
        for model in model_list:
            should_append = False
            for field in model._meta.fields:                    
                if is_intresting_field(field):
                    should_append=True
            if should_append:
                all_model_list.append(
                    (
                     '%s.%s' % (model._meta.app_label, model._meta.object_name), 
                     is_model_covered(model),
                     get_suggested_linklist(model),
                    )
                )
    return render_to_response('linkcheck/coverage.html',{
            'all_model_list': all_model_list, 
        },
        RequestContext(request),
    )


@staff_member_required
@csrf_exempt
def report(request):
    
    outerkeyfunc = itemgetter('content_type_id')
    content_types_list = []

    if request.method == 'POST':
        
        ignore_link_id = request.GET.get('ignore', None)
        if ignore_link_id != None:
            link = Link.objects.get(id=ignore_link_id)
            link.ignore = True
            link.save()
            if request.is_ajax():
                json = simplejson.dumps({'link': ignore_link_id})
                return HttpResponse(json, mimetype='application/javascript')
        
        unignore_link_id = request.GET.get('unignore', None)
        if unignore_link_id != None:
            link = Link.objects.get(id=unignore_link_id)
            link.ignore = False
            link.save()
            if request.is_ajax():
                json = simplejson.dumps({'link': unignore_link_id})
                return HttpResponse(json, mimetype='application/javascript')
            
        recheck_link_id = request.GET.get('recheck', None)
        if recheck_link_id != None:
            link = Link.objects.get(id=recheck_link_id)
            url = link.url 
            url.check(external_recheck_interval=0)
            links = [x[0] for x in url.links.values_list('id')]
            if request.is_ajax():
                json = simplejson.dumps({
                    'links': links,
                    'message': url.message,
                    'colour': url.colour,
                })
                return HttpResponse(json, mimetype='application/javascript')

    link_filter = request.GET.get('filters', 'show_invalid')

    if link_filter == 'show_valid':
        qset = Link.objects.filter(ignore=False, url__status__exact=True)
        report_type = 'Good Links'
    elif link_filter == 'show_unchecked':
        qset = Link.objects.filter(ignore=False, url__last_checked__exact=None)
        report_type = 'Untested Links'
    elif link_filter == 'ignored':
        qset = Link.objects.filter(ignore=True)
        report_type = 'Ignored Links'
    else:
        qset = Link.objects.filter(ignore=False, url__status__exact=False)
        report_type = 'Broken Links'
    
    paginated_links = Paginator(qset, RESULTS_PER_PAGE, 0, True)

    try:
        page = int(request.GET.get('page', '1'))
    except:
        page = 0
    # offset = (page - 1) * RESULTS_PER_PAGE
    links = paginated_links.page(page)

    # This code groups links into nested lists by content type and object id   
    # It's a bit nasty but we can't use groupby unless be get values() instead of a queryset because of the 'Object is not subscriptable' error
    
    t = sorted(links.object_list.values(), key=outerkeyfunc)
    for tk, tg in groupby(t, outerkeyfunc):
        innerkeyfunc = itemgetter('object_id')
        objects = []
        tg = sorted(tg, key=innerkeyfunc)
        for ok, og in groupby(tg, innerkeyfunc):
            content_type = ContentType.objects.get(pk=tk)
            og = list(og)
            try:
                object = content_type.model_class().objects.get(pk=ok)
            except content_type.model_class().DoesNotExist:
                object = None
            try:
                admin_url = object.get_admin_url()
            except AttributeError:
                admin_url = '%s%s/%s/%s/' % (reverse('admin:index'), content_type.app_label, content_type.model, ok)
            objects.append({
                'object': object,
                'link_list': Link.objects.in_bulk([x['id'] for x in og]).values(), # convert values_list back to queryset. Do we need to get values() or do we just need a list of ids?
                'admin_url': admin_url,
            })
        content_types_list.append({
            'content_type': content_type,
            'object_list': objects
        })

    #pass any querystring data back to the form minus page
    rqst = request.GET.copy()
    if ('page' in rqst):
        del rqst['page']


    return render_to_response(
        'linkcheck/report.html',
            {'content_types_list': content_types_list,
            'pages': links,
            'filter': link_filter,
            'media':  forms.Media(js=['%s%s' % (admin_static, 'js/jquery.min.js')]),
            'qry_data': rqst.urlencode(),
            'report_type': report_type,
            'ignored_count': Link.objects.filter(ignore=True).count(),
        },
        RequestContext(request),
    )
