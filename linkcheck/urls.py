try:
    from django.conf.urls.defaults import *
except:
    from django.conf.urls import *

urlpatterns = patterns('linkcheck.views',
   (r'^coverage/$', 'coverage'),
   (r'^.*$', 'report'),
)