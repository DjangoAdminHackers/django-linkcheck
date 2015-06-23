from django.conf.urls import include, patterns, url
from django.contrib import admin
from django import http

from linkcheck.tests.sampleapp import views

handler404 = lambda x: http.HttpResponseNotFound('')

urlpatterns = patterns('',
    url(r'^admin/linkcheck/', include('linkcheck.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^http/(?P<code>\d+)/$', views.http_response),
    url(r'^http/redirect/(?P<code>\d+)/$', views.http_redirect),
)
