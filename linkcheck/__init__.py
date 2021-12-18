import threading
from html.parser import HTMLParser

import django

# A global lock, showing whether linkcheck is busy
update_lock = threading.Lock()

if django.VERSION <= (3, 2):
    default_app_config = 'linkcheck.apps.LinkcheckConfig'


class Lister(HTMLParser):

    def reset(self):
        HTMLParser.reset(self)
        self.urls = []


class URLLister(Lister):

    def __init__(self):
        self.in_a = False
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
            src = [v for k, v in attrs if k == 'src']
            if src:
                self.text += ' [image:%s] ' % src[0]

    def handle_endtag(self, tag):
        if tag == 'a' and self.in_a:
            self.urls.append((self.text[:256], self.url))
            self.in_a = False
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
    if not isinstance(content, str):
        content = str(content)
    parser.feed(content)
    parser.close()
    return parser.names


class Linklist:

    html_fields = []
    url_fields = []
    ignore_empty = []
    image_fields = []

    # You can override object_filter and object_exclude in a linklist class.
    # Just provide a dictionary to be used as a Django lookup filter.
    # Only objects that pass the filter will be queried for links.
    # This doesn't affect whether an object is regarded as a valid link target. Only as a link source.
    # Example usage in your linklists.py:
    # object_filter = {'active': True} - Would only check active objects for links

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

    @staticmethod
    def extract_url_from_field(obj, field_name):
        val = getattr(obj, field_name)
        try:
            try:
                url = val.url  # FileField and ImageField have a url property
            except ValueError:  # And it throws an exception for empty fields
                url = ''
        except AttributeError:
            url = val  # Assume the field returns the url directly

        return url or ''  # Coerce None to ''

    def get_urls_from_field_list(self, obj, field_list):
        urls = []
        for field_name in field_list:
            url = self.extract_url_from_field(obj, field_name)
            if field_name in self.ignore_empty and not url:
                continue
            urls.append((field_name, '', url))
        return urls

    def urls(self, obj):

        urls = []

        # Look for HREFS in HTML fields
        for field_name in self.html_fields:
            urls += [(field_name, text, url) for text, url in parse_urls(obj, field_name)]

        # Now add in the URL fields
        urls += self.get_urls_from_field_list(obj, self.url_fields)

        return urls

    def images(self, obj):

        urls = []

        # Look for IMGs in HTML fields
        for field_name in self.html_fields:
            urls += [(field_name, text, url) for text, url in parse_images(obj, field_name)]

        # hostname_length = settings.MEDIA_URL[:-1].rfind('/')
        # url[hostname_length:]

        # Now add in the image fields
        urls += self.get_urls_from_field_list(obj, self.image_fields)

        return urls

    @classmethod
    def objects(cls):

        objects = cls.model.objects.all()

        if cls.object_filter:
            objects = objects.filter(**cls.object_filter).distinct()
        if cls.object_exclude:
            objects = objects.exclude(**cls.object_exclude).distinct()
        return objects

    def get_linklist(self, extra_filter=None):

        extra_filter = extra_filter or {}

        linklist = []
        objects = self.objects()

        if extra_filter:
            objects = objects.filter(**extra_filter)

        for obj in objects:
            linklist.append({
                'object': obj,
                'urls': self.urls(obj),
                'images': self.images(obj),
            })

        return linklist

    @classmethod
    def content_type(cls):
        from django.contrib.contenttypes.models import ContentType
        return ContentType.objects.get_for_model(cls.model)
