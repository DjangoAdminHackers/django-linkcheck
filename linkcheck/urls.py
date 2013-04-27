from django.conf.urls.defaults import *

urlpatterns = patterns('linkcheck.views',
   (r'^coverage/$', 'coverage'),
   (r'^.*$', 'report'),
)