import time
from django.http import HttpResponse, HttpResponsePermanentRedirect, HttpResponseRedirect


def http_response(request, code):
    return HttpResponse("", status=int(code))


def http_response_get_only(request, code):
    status = int(code) if request.method == 'HEAD' else 200
    return HttpResponse("", status=status)


def http_redirect(request, code):
    return HttpResponseRedirect("/http/200/", status=int(code))


def http_redirect_to_404(request):
    return HttpResponsePermanentRedirect("/http/404/")


def timeout(request):
    time.sleep(2)
    return HttpResponse("")
