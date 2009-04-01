from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST

from cms.models import Page
from linkcheck.models import Link

from forms import FindForm

from utils import check_internal
from utils import find


@staff_member_required
def report(request):
    #find()
    #check_internal()

    from operator import itemgetter
    from itertools import groupby
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
            objects.append({
                'object': content_type.model_class().objects.get(pk=ok),
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

@staff_member_required
def fix(request):  #TODO This whole thing is temporary
    assert False
    results = find()
    output = []
    for k, v in results.items():
        for i, item in enumerate(results[k]):
            if item['images']:
                output.append('<h3>' + item['object'].name + '</h3><a href="' + item['object'].get_absolute_url() + '">' + item['object'].get_absolute_url() + '</a>')
            for url in item['urls']:
                newurl = None
                if url.startswith('/') or url.startswith('http') or url.startswith('mailto') or url.startswith('#'):
                    pass
                else:
                    if url.endswith('.html'):
                        try:
                            newurl = Page.objects.get(name=url[:-5]).get_absolute_url()
                            output.append(url + ' > ' + newurl)
                        except Page.DoesNotExist:
                            output.append('Not found: ' + url)
                    elif url.startswith('www.'):
                        newurl = 'http://' + url
                        output.append(url + ' > ' + newurl)
                    elif url.endswith('.pdf') or url.endswith('.doc') or url.endswith('.ppt'):
                        newurl = '/media/documents/' + url.replace('\\', '/')[7:]
                        output.append(url + ' > ' + newurl)
                    else:
                        output.append('Not changed: ' + url)
                    if newurl:
                        url = 'href="' + url + '"'
                        newurl = 'href="' + newurl + '"'
                        item['object'].content = item['object'].content.replace(url, newurl)
                        #item['object'].save()
            for url in item['images']:
                newurl = None
                if url.startswith('/'):
                    pass
                else:
                    if url.startswith('images/logos/') and url.endswith('.jpg') or url.endswith('.gif') or url.endswith('.png'):
                        newurl = '/media/' + url.replace('\\', '/')[7:]
                        output.append(url + ' > ' + newurl)
                    elif url.startswith('images') and url.endswith('.jpg') or url.endswith('.gif') or url.endswith('.png'):
                        newurl = '/media/documents/' + url.replace('\\', '/')
                        output.append(url + ' > ' + newurl)
                    else:
                        output.append('Not changed: ' + url)
                    if newurl:
                        url = 'src="' + url + '"'
                        newurl = 'src="' + newurl + '"'
                        item['object'].content = item['object'].content.replace(url, newurl)
                        item['object'].save()
    output = u'<hr>'.join(output)
    return render_to_response(
        'fix.html',
        {
            'output': output,
        },
        RequestContext(request),
    )

@staff_member_required
def tidy(request):
    from  django.utils.html import escape 
    #global tidy_options
    #tempfilename = os.getcwd()+'/tidytemp.txt'
    output = []
    for p in Page.objects.all():
        t = p.content.strip().lower()
        if t.startswith('<h'):
            start = t.find('>') + 1
            end = t.find('</h')
            output.append('<h2><a href="' + p.admin_url + '" target="_blank">' + p.title + '</a></h2>')
            output.append(str(end))
            p.long_title = p.content[start:end]
            p.content = p.content[end + 5:]
            #p.save()
        r = False
        if r:
            pass
            #output.append(escape(str(r.group())))
        else:
            pass
            #output.append('<i style="color: #999">'+escape(p.content[:100])+'</i>')
        #p.save()
        #p.content = p.content.replace('fixed_bound="true"', '')
        #p.extra_content = p.extra_content.replace('fixed_bound="true"', '')
        #temp = open(tempfilename,'w')
        #temp.write(c)
        #temp.close()
        #p.content = ''
        #p.content = c2
        
    output = u'<hr><hr><hr><hr><hr>'.join(output)
    return render_to_response(
        'tidy.html',
        {
            'output': output,
        },
        RequestContext(request),
    )

@staff_member_required
def replace(request, linklists):
    form = FindForm()
    
    return render_to_response(
        'replace.html',
        {
            'form': form,
        },
        RequestContext(request),
    )
    
@staff_member_required
def index(request):
    return render_to_response(
        'index.html',
        {
            
        },
        RequestContext(request),
    )