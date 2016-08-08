from django.conf.urls import url

from . import views

urlpatterns = [
   url(r'^coverage/$', views.coverage, name='linkcheck_coverage'),
   url(r'^.*$', views.report, name='linkcheck_report'),
]
