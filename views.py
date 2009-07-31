from itertools import groupby
from operator import itemgetter

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST

from linkcheck.models import Link
from linkcheck.utils import check_internal
from linkcheck.utils import find

@staff_member_required
def report(request):
    outerkeyfunc = itemgetter('content_type_id')
    content_types_list = []
    #
    # This code groups links into nested lists by content type and object id   
    # Nasty! We can't use groupby unless be get values() instead of a queryset because of the 'Object is not subscriptable' error
    #
    t = sorted(Link.objects.values(), key=outerkeyfunc)
    for tk, tg in groupby(t, outerkeyfunc):
        innerkeyfunc = itemgetter('object_id')
        objects = []
        for ok, og in groupby(tg, innerkeyfunc):
            content_type = ContentType.objects.get(pk=tk)
            og = list(og)
            try:
                object = content_type.model_class().objects.get(pk=ok)
            except content_type.model_class().DoesNotExist:
                object = None
            objects.append({
                'object': object,
                'link_list': Link.objects.in_bulk([x['id'] for x in og]).values(), # convert values_list back to queryset. Do we need to get values() or do we just need a list of ids?
                'admin_url': '/admin/%s/%s/%s/' % (content_type.app_label, content_type.model, ok)
            })
        content_types_list.append({
            'content_type': content_type,
            'object_list': objects
        })
    return render_to_response(
        'report.html',
        {
            'content_types_list': content_types_list,
        },
        RequestContext(request),
    )
