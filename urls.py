from django.conf.urls.defaults import *

urlpatterns = patterns('linkcheck.views',
   (r'^$', 'report'),
)