from django.test.client import ClientHandler
from datetime import datetime
from datetime import timedelta

from linkcheck.models import Link
from linkcheck.models import Url

class LinkCheckHandler(ClientHandler):
    #customize the ClientHandler to allow us removing some middlewares

    def load_middleware(self):
        self.ignore_keywords = ['reversion.middleware','CommonMiddleware','MaintenanceModeMiddleware']
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

def check_links(external_recheck_interval=86400, limit=-1, check_internal=True, check_external=True):
    recheck_datetime = datetime.now() - timedelta(seconds=external_recheck_interval)
    
    urls = Url.objects.filter(still_exists__exact='TRUE').exclude(last_checked__gt=recheck_datetime)

    #if limit is specified set the limit
    if limit and limit > -1:
        urls = urls[:limit]

    for u in urls:
        u.check(check_internal=check_internal, check_external=check_external)

def update_urls(urls, content_type, object_id):
    # url structure = (field, link text, url)
    for field, link_text, url in urls:
        if url.startswith('#'):
            instance = content_type.get_object_for_this_type(id=object_id)
            url = instance.get_absolute_url() + url
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

