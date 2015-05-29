from django.conf.urls import include, patterns
from django.contrib import admin
from django import http

handler404 = lambda x: http.HttpResponseNotFound('')

urlpatterns = patterns('',
    (r'^admin/linkcheck/', include('linkcheck.urls')),
    (r'^admin/', include(admin.site.urls)),
)
