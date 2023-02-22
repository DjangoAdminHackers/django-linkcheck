import time

from django.core.exceptions import PermissionDenied
from django.http import (
    HttpResponse,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
)


def http_response(request, code):
    return HttpResponse("", status=int(code))


def http_response_get_only(request, code):
    status = int(code) if request.method == 'HEAD' else 200
    return HttpResponse("", status=status)


def http_block_user_agent(request, block_head=False):
    if block_head and request.method == 'HEAD':
        return HttpResponse('', status=405)
    if 'Linkchecker' in request.headers.get('User-Agent', ''):
        raise PermissionDenied()
    return HttpResponse('')


def http_redirect(request, code):
    return HttpResponseRedirect("/http/200/", status=int(code))


def http_redirect_to_404(request):
    return HttpResponsePermanentRedirect("/http/404/")


def timeout(request):
    time.sleep(2)
    return HttpResponse("")


def http_response_with_anchor(request):
    return HttpResponse("<html><body><h1 id='anchor'>Anchor</h1></body></html>")


def http_redirect_to_anchor(request):
    return HttpResponseRedirect("/http/anchor/")


def static_video(request):
    return HttpResponse(b'', content_type='video/mp4')


def static_video_forged_content_type(request):
    return HttpResponse(b'<![x02\x00\xa0\xcc', content_type='text/html')
