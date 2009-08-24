from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models

# See signals module for an example of keeping urls and links updated automatically
#import signals 

class Url(models.Model):
    url = models.CharField(max_length=255, unique=True)
    last_checked = models.DateTimeField(max_length=1024, blank=True, null=True)
    status = models.NullBooleanField()
    message = models.CharField(max_length=1024, blank=True, null=True)
    still_exists = models.BooleanField()
    @property
    def type(self):
        if self.url.startswith('http://'):
            return 'external'
        if self.url.startswith('mailto'):
            return 'mailto'
        elif str(self.url)=='#' or str(self.url)=='':
            return 'empty'
        elif self.url.startswith('#'):
            return 'anchor'
        elif self.url.startswith('/media/documents/images/'):
            return 'image'
        elif self.url.startswith('/media/documents/'):
            return 'document'
        elif self.url.startswith('/media/'): #TODO this needs to be configurable
            return 'other media'
        else:
            return 'unknown'
    @property
    def colour(self):
        if self.status==True:
            return 'green'
        elif self.status==False:
            return 'red'
        else:
            return 'blue'
    def __unicode__(self):
        return self.url
    
class Link(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    field = models.CharField(max_length=128)
    url = models.ForeignKey(Url, related_name="links")


