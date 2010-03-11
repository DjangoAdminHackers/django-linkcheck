import re
import imp
from datetime import datetime

from django.conf import settings
from django.utils.importlib import import_module
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import signals as model_signals


EXTERNAL_REGEX = re.compile(r'^https?://')

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
        elif self.url.startswith('/media/'): #TODO this needs to be configurable. Can't use MEDIA_URL as it might include the server
            return 'other media'
        else:
            return 'unknown'

    @property
    def get_message(self):
        if self.last_checked:
            return self.message
        else:
            return "URL Not Yet Checked"

    @property
    def colour(self):
        if not self.last_checked:
            return 'blue'
        elif self.status==True:
            return 'green'
        else:
            return 'red'
            
    def __unicode__(self):
        return self.url

    def check(self):
        from utils import UrlValidator
        external = EXTERNAL_REGEX.match(self.url)
        if external:
            uv = UrlValidator(self.url).verify_external()
        else:
            uv = UrlValidator(self.url).verify_internal()
        self.status        = uv.status
        self.message       = uv.message
        self.last_checked  = datetime.now()
        self.save()
        return self.status

class Link(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    field = models.CharField(max_length=128)
    url = models.ForeignKey(Url, related_name="links")
    text = models.CharField(max_length=256, default='')
    # ALTER TABLE `linkcheck_link` ADD `text` VARCHAR( 256 ) NOT NULL DEFAULT 'empty'

def link_post_delete(sender, instance, **kwargs):
    url = instance.url
    count = url.links.all().count()
    if count == 0:
        url.delete()
model_signals.post_delete.connect(link_post_delete, sender=Link)


#-------------------------auto discover of LinkLists-------------------------

class AlreadyRegistered(Exception):
    pass

all_linklists = {}

for app in settings.INSTALLED_APPS:
    try:
        app_path = import_module(app).__path__
    except AttributeError:
        continue
    try:
        imp.find_module('linklists', app_path)
    except ImportError:
        continue
    the_module = import_module("%s.linklists" % app)
    try:
        for k in the_module.linklists.keys():
            if k in all_linklists.keys():
                raise AlreadyRegistered('The key %s is already registered in all_linklists' % k)
        
        for l in the_module.linklists.values():
            for l2 in all_linklists.values():
                if l.model == l2.model:
                    raise AlreadyRegistered('The LinkList %s is already registered in all_linklists' % l)
        all_linklists.update(the_module.linklists)
    except AttributeError:
        pass

#-------------------------register listeners-------------------------
import listeners
