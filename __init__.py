from sgmllib import SGMLParser

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

class Lister(SGMLParser):
    def reset(self):                              
        SGMLParser.reset(self)
        self.urls = []
class URLLister(Lister):
    def start_a(self, attrs):                     
        href = [v for k, v in attrs if k=='href'] 
        if href:
            self.urls.extend(href)
class ImageLister(Lister):
    def start_img(self, attrs):                     
        src = [v for k, v in attrs if k=='src'] 
        if src:
            self.urls.extend(src)

def parse(obj, field, parser):
    urls=[]
    parser.feed(getattr(obj,field))
    parser.close()
    return parser.urls

def parse_urls(obj, field):
    parser = URLLister()
    return parse(obj, field, parser)

def parse_images(obj, field):
    parser = ImageLister()
    return parse(obj, field, parser)

class Linklist(object):
    html_fields = []
    url_fields = []
    image_fields = []
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
        for field in self.html_fields:
            urls += [(field, url) for url in parse_urls(obj,field)]
        for field in self.url_fields:
            urls.append((field, getattr(obj ,field)))
        return urls
    def images(self, obj):
        urls = []
        host_index = settings.MEDIA_URL[:-1].rfind('/')
        for field in self.html_fields:
            urls += [(field, url) for url in parse_images(obj,field)]
        for field in self.image_fields:
            urls.append((field, getattr(obj,field).url[host_index:]))
        return urls
    @classmethod
    def objects(cls):
        return cls.model.objects.all()
    def get_linklist(self):
        linklist = []
        for object in self.objects():
            linklist.append({
                'object': object,
                'urls': self.urls(object),
                'images': self.images(object),
            })
        return linklist
    @classmethod
    def content_type(cls):
        return ContentType.objects.get_for_model(cls.model)