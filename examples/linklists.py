from linkcheck import Linklist
from cms.models import Page


class PageLinklist(Linklist):

    model = Page
    object_filter = {'active': True}
    html_fields = ['content', 'extra_content']

linklists = {'Pages': PageLinklist}
