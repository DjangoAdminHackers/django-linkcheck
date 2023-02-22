from django import http
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from linkcheck.tests.sampleapp import views


def handler404(*args, **kwargs):
    return http.HttpResponseNotFound("")


urlpatterns = [
    path('admin/linkcheck/', include('linkcheck.urls')),
    path('admin/', admin.site.urls),
    path('public/', views.http_response, {'code': '200'}),
    path('http/<int:code>/', views.http_response),
    path('http/<int:code>/rückmeldung/', views.http_response),
    path('http/getonly/<int:code>/', views.http_response_get_only),
    path('http/block-user-agent/', views.http_block_user_agent),
    path('http/block-user-agent/block-head/', views.http_block_user_agent, {'block_head': True}),
    path('http/redirect/<int:code>/', views.http_redirect),
    path('http/redirect_to_404/', views.http_redirect_to_404),
    path('http/redirect_to_anchor/', views.http_redirect_to_anchor),
    path('http/brokenredirect/', RedirectView.as_view(url='/non-existent/')),
    path('http/anchor/', views.http_response_with_anchor),
    path('timeout/', views.timeout),
    path('static-files/video.mp4', views.static_video),
    path('static-files/fake-video.mp4', views.static_video_forged_content_type),
]
