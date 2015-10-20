try:
    from django.conf.urls.defaults import *
except:
    from django.conf.urls import *

urlpatterns = patterns('linkcheck.views',
   url(r'^coverage/$', 'coverage', name='linkcheck_coverage'),
   url(r'^.*$', 'report', name='linkcheck_report'),
)