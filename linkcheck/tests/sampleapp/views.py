from django.http import HttpResponse, HttpResponseRedirect


def http_response(request, code):
    return HttpResponse("", status=int(code))


def http_redirect(request, code):
    return HttpResponseRedirect("/http/200/", status=int(code))
