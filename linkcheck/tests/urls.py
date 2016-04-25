# -*- encoding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import include, url
from django.contrib import admin
from django import http

from linkcheck.tests.sampleapp import views

handler404 = lambda x: http.HttpResponseNotFound('')

urlpatterns = [
    url(r'^admin/linkcheck/', include('linkcheck.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^public/', views.http_response, {'code': '200'}),
    url(r'^http/(?P<code>\d+)/$', views.http_response),
    url(r'^http/(?P<code>\d+)/rückmeldung/$', views.http_response),
    url(r'^http/redirect/(?P<code>\d+)/$', views.http_redirect),
]
