from datetime import datetime, timedelta
from urllib2 import urlopen, URLError

from django.conf import settings
from django.db import connection
from django.test.client import Client

from linkcheck.models import Link, Url

from linkcheck_config import linklists

from path import path

def check():
    check_internal()
    check_external()

def check_internal():
    for u in Url.objects.all():
        if u.url.startswith('mailto'):
            u.status = None
            u.message = 'Email link (not checked)'
        elif str(u.url)=='#' or str(u.url)=='':
            u.status = False
            u.message = 'Empty link'
        elif u.url.startswith('#'):
            u.status = None
            u.message = 'Link to same page (not checked)'
        else:
            if u.url.startswith('/media/'): #TODO fix hardcoded media url
                u.last_checked = datetime.now()
                if path(settings.MEDIA_ROOT+u.url[6:]).exists():
                    u.message = 'Working document link'
                    u.status = True
                else:
                    u.message = 'Missing Document'
                    u.status = False
            elif u.url.startswith('/'):
                u.last_checked = datetime.now()
                valid = False
                for k,v in linklists.items():
                    response = Client().get(u.url)
                    if response.status_code == 200:
                        valid = True
                if valid:
                    u.message = 'Working internal link'
                    u.status = True
                else:
                    u.message = 'Broken internal link'
                    u.status = False
            elif u.url.startswith('http://'):
                pass
            else:
                u.message = 'Invalid URL'
                u.status = False
        u.save()

def check_external():
    for u in Url.objects.all():
        if u.url.startswith('http://'):
            if settings.DEBUG:
                check_every = timedelta(hours=60)
            else:
                check_every = timedelta(hours=15)
            if u.last_checked==None or u.last_checked<=(datetime.now()-check_every):
                u.last_checked = datetime.now()
                try:
                    response = urlopen(u.url)
                    u.message = ' '.join([str(response.code), response.msg])
                    u.status = True
                except URLError, e:
                    if hasattr(e, 'reason'):
                        u.message = 'Unreachable: '+str(e.reason)
                    elif hasattr(e, 'code'):
                        u.message = 'Error: '+str(e.code)
                    else:
                        assert False
                    u.status = False
            else:
                pass
        u.save()

def find():
    results = {}
    Url.objects.all().update(still_exists=False)
    for k,v in linklists.items():
        results[k] = v().get_linklist()
        for item in results[k]:
            for url in (item['urls']+item['images']):
                u, created = Url.objects.get_or_create(url=url[1])
                l, created = Link.objects.get_or_create(url=u, field=url[0], content_type=v.content_type(), object_id=item['object'].id)
                u.still_exists = True
                u.save()
    Url.objects.filter(still_exists=False).delete()
    return results
