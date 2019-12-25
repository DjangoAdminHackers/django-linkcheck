import json
from itertools import groupby
from operator import itemgetter

import django
from django import forms
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse, NoReverseMatch
from django.views.decorators.csrf import csrf_exempt

from linkcheck import update_lock
from linkcheck.linkcheck_settings import RESULTS_PER_PAGE
from linkcheck.models import Link
from linkcheck.utils import get_coverage_data


@staff_member_required
def coverage(request):

    coverage_data = get_coverage_data()

    if request.GET.get('config', False):
        # Just render the suggested linklist code
        template = 'linkcheck/suggested_configs.html'
        context = {'coverage_data': [x['suggested_config'] for x in coverage_data]}
    else:
        # Render a nice report
        template = 'linkcheck/coverage.html'
        context = {'coverage_data': coverage_data}

    return render(request, template, context)


@staff_member_required
@csrf_exempt
def report(request):

    outerkeyfunc = itemgetter('content_type_id')
    content_types_list = []

    if request.method == 'POST':

        ignore_link_id = request.GET.get('ignore', None)
        if ignore_link_id is not None:
            link = Link.objects.get(id=ignore_link_id)
            link.ignore = True
            link.save()
            if request.is_ajax():
                json_data = json.dumps({'link': ignore_link_id})
                return HttpResponse(json_data, content_type='application/javascript')

        unignore_link_id = request.GET.get('unignore', None)
        if unignore_link_id is not None:
            link = Link.objects.get(id=unignore_link_id)
            link.ignore = False
            link.save()
            if request.is_ajax():
                json_data = json.dumps({'link': unignore_link_id})
                return HttpResponse(json_data, content_type='application/javascript')

        recheck_link_id = request.GET.get('recheck', None)
        if recheck_link_id is not None:
            link = Link.objects.get(id=recheck_link_id)
            url = link.url
            url.check_url(external_recheck_interval=0)
            links = [x[0] for x in url.links.values_list('id')]
            if request.is_ajax():
                json_data = json.dumps({
                    'links': links,
                    'message': url.message,
                    'colour': url.colour,
                })
                return HttpResponse(json_data, content_type='application/javascript')

    link_filter = request.GET.get('filters', 'show_invalid')

    qset = Link.objects.order_by('-url__last_checked')
    if link_filter == 'show_valid':
        qset = qset.filter(ignore=False, url__status__exact=True)
        report_type = 'Good Links'
    elif link_filter == 'show_unchecked':
        qset = qset.filter(ignore=False, url__last_checked__exact=None)
        report_type = 'Untested Links'
    elif link_filter == 'ignored':
        qset = qset.filter(ignore=True)
        report_type = 'Ignored Links'
    else:
        qset = qset.filter(ignore=False, url__status__exact=False)
        report_type = 'Broken Links'

    paginated_links = Paginator(qset, RESULTS_PER_PAGE, 0, True)

    try:
        page = int(request.GET.get('page', '1'))
    except:
        page = 0
    # offset = (page - 1) * RESULTS_PER_PAGE
    links = paginated_links.page(page)

    # This code groups links into nested lists by content type and object id
    # It's a bit nasty but we can't use groupby unless be get values()
    # instead of a queryset because of the 'Object is not subscriptable' error

    t = sorted(links.object_list.values(), key=outerkeyfunc)
    for tk, tg in groupby(t, outerkeyfunc):
        innerkeyfunc = itemgetter('object_id')
        objects = []
        tg = sorted(tg, key=innerkeyfunc)
        for ok, og in groupby(tg, innerkeyfunc):
            content_type = ContentType.objects.get(pk=tk)
            og = list(og)
            try:
                object = None
                if content_type.model_class():
                    object = content_type.model_class().objects.get(pk=ok)
            except ObjectDoesNotExist:
                pass
            try:
                admin_url = object.get_admin_url()  # TODO allow method name to be configurable
            except AttributeError:
                try:
                    admin_url = reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model), args=[ok])
                except NoReverseMatch:
                    admin_url = None

            objects.append({
                'object': object,
                'link_list': Link.objects.in_bulk([x['id'] for x in og]).values(),  # Convert values_list back to queryset. Do we need to get values() or do we just need a list of ids?
                'admin_url': admin_url,
            })
        content_types_list.append({
            'content_type': content_type,
            'object_list': objects
        })

    # Pass any querystring data back to the form minus page
    rqst = request.GET.copy()
    if 'page' in rqst:
        del rqst['page']

    return render(request, 'linkcheck/report.html', {
            'content_types_list': content_types_list,
            'pages': links,
            'filter': link_filter,
            'media': forms.Media(js=[static(get_jquery_min_js())]),
            'qry_data': rqst.urlencode(),
            'report_type': report_type,
            'ignored_count': Link.objects.filter(ignore=True).count(),
        },
    )


def get_jquery_min_js():
    """
    Return the location of jquery.min.js. It's an entry point to adapt the path
    when it changes in Django.
    """
    return 'admin/js/vendor/jquery/jquery.min.js'


def get_status_message():
    if update_lock.locked():
        return "Still checking. Please refresh this page in a short while. "
    else:
        broken_links = Link.objects.filter(ignore=False, url__status=False).count()
        if broken_links:
            return (
                "<span style='color: red;'>We've found {} broken link{}.</span><br>"
                "<a href='{}'>View/fix broken links</a>".format(
                    broken_links,
                    "s" if broken_links > 1 else "",
                    reverse('linkcheck_report'),
                )
            )
        else:
            return ''
