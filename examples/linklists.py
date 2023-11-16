from cms.models import Page

from linkcheck import Linklist


class PageLinklist(Linklist):

    model = Page
    object_filter = {'active': True}
    html_fields = ['content', 'extra_content']


linklists = {'Pages': PageLinklist}
