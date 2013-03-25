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
from django import forms
from django.conf import settings

from linkcheck.linkcheck_settings import RESULTS_PER_PAGE
from linkcheck.models import Link

try:
    from django.contrib.admin.templatetags.adminmedia import admin_media_prefix
    # For backwards compatibility allow either of these but prefer admin_media_prefix
    admin_static = admin_media_prefix() or settings.STATIC_URL
except ImportError:
    # However - admin_media_prefix was removed in Django 1.5
    admin_static = settings.STATIC_URL


@staff_member_required
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
