from sgmllib import SGMLParser
from HTMLParser import HTMLParser

from django.contrib.contenttypes.models import ContentType


class Lister(SGMLParser):
    def reset(self):
        SGMLParser.reset(self)
        self.urls = []


class URLLister(Lister):
    def __init__(self):
        self.in_a = False
        #self.in_img = False
        self.text = ''
        self.url = ''
        SGMLParser.__init__(self)
    def start_a(self, attrs):
        self.in_a = True
        href = [v for k, v in attrs if k=='href']
        if href:
            self.url = href[0]
    def start_img(self, attrs):
        if self.in_a:
            src = [v for k, v in attrs if k=='src']
            if src:
                self.text += ' [image:%s] ' % src[0]
    def handle_data(self, data):
        if self.in_a:
            self.text += data
    def end_a(self):
        if self.url:
            self.urls.append((self.text[:256], self.url))
        self.in_a = False
        self.text = ''
        self.url = ''


class ImageLister(Lister):
    def start_img(self, attrs):                     
        src = [v for k, v in attrs if k=='src'] 
        if src:
            self.urls.append(('', src[0]))


class AnchorLister(HTMLParser):
    def __init__(self):
        self.names = []
        HTMLParser.__init__(self)
    def reset(self):
        HTMLParser.reset(self)
        self.names = []
    def handle_starttag(self, tag, attributes):
        name = [v for k, v in attributes if k=='id']
        if name:
            self.names.append(name[0])
        if tag == 'a':
            name = [v for k, v in attributes if k=='name']
            if name:
                self.names.append(name[0])


def parse(obj, field, parser):
    html = getattr(obj,field)
    if html:
        parser.feed(html)
        parser.close()
        return parser.urls
    else:
        return []


def parse_urls(obj, field):
    parser = URLLister()
    return parse(obj, field, parser)


def parse_images(obj, field):
    parser = ImageLister()
    return parse(obj, field, parser)


def parse_anchors(content):
    parser = AnchorLister()
    parser.feed(content)
    parser.close()
    return parser.names


class Linklist(object):

    html_fields = []
    url_fields = []
    image_fields = []
    object_filter = None
    object_exclude = None

    def __get(self, name, obj, default=None):
        try:
            attr = getattr(self, name)
        except AttributeError:
            return default
        if callable(attr):
            return attr(obj)
        return attr

    def urls(self, obj):
        urls = []

        # Look for HREFS in HTML fields
        for field in self.html_fields:
            urls += [(field, text, url) for text, url in parse_urls(obj,field)]

        # Now add in the URL fields
        for field in self.url_fields:
            urls.append((field, '', getattr(obj ,field)))
            
        return urls

    def images(self, obj):
        from django.conf import settings
        urls = []
        host_index = settings.MEDIA_URL[:-1].rfind('/')
        
        # Look for IMGs in HTML fields
        for field in self.html_fields:
            urls += [(field, text, url) for text, url in parse_images(obj,field)]

        # Now add in the image fields
        for field in self.image_fields:
            try:
                urls.append((field, '', getattr(obj,field).url[host_index:]))
            except ValueError: # No image attached
                pass
            
        return urls

    @classmethod
    def objects(cls):
        objects = cls.model.objects.all()
        if cls.object_filter:
            objects = objects.filter(**cls.object_filter).distinct()
        if cls.object_exclude:
            objects = objects.exclude(**cls.object_exclude).distinct()
        return objects
    
    def get_linklist(self, extra_filter={}):
        linklist = []
        objects = self.objects()
        if extra_filter:
            objects = objects.filter(**extra_filter)
        for object in objects:
            linklist.append({
                'object': object,
                'urls': self.urls(object),
                'images': self.images(object),
            })
        return linklist
    
    @classmethod
    def content_type(cls):
        return ContentType.objects.get_for_model(cls.model)