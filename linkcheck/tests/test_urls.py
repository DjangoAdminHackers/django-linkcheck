from django.conf.urls.defaults import *
from django.contrib import admin
from django import http

handler404 = lambda x: http.HttpResponseNotFound('')

urlpatterns = patterns('',
    (r'^admin/linkcheck/', include('linkcheck.urls')),
    (r'^admin/', include(admin.site.urls)),
)
