from django.conf import settings
try:
    from django.utils.html_parser import HTMLParser
except:
    from HTMLParser import HTMLParser


class Lister(HTMLParser):
    def reset(self):
        HTMLParser.reset(self)
        self.urls = []


class URLLister(Lister):
    def __init__(self):
        self.in_a = False
        #self.in_img = False
        self.text = ''
        self.url = ''
        HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = [v for k, v in attrs if k == 'href']
            if href:
                self.in_a = True
                self.url = href[0]
        elif tag == 'img' and self.in_a:
            src = [v for k, v in attrs if k=='src']
            if src:
                self.text += ' [image:%s] ' % src[0]

    def handle_endtag(self, tag):
        if tag == 'a' and self.in_a:
            self.urls.append((self.text[:256], self.url))
        self.text = ''
        self.url = ''

    def handle_data(self, data):
        if self.in_a:
            self.text += data


class ImageLister(Lister):
    def handle_starttag(self, tag, attrs):
        if tag == 'img':
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
    ignore_empty = []
    image_fields = []
    # You can override object_filter and object_exclude in a linklist class. Just provide a dictionary to be used as a Django lookup filter.
    # Only objects that pass the filter will be queried for links. 
    # This doesn't affect whether an object is regarded as a valid link target. Only as a source.
    # Example usage in your linklists.py:
    # object_filter = {'active':True} - Would only check active objects for links
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
            url_data = (field, '', getattr(obj ,field))
            if field in self.ignore_empty and not url_data[2]:
                continue
            urls.append(url_data)
            
        return urls

    def images(self, obj):
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
        from django.contrib.contenttypes.models import ContentType
        return ContentType.objects.get_for_model(cls.model)
