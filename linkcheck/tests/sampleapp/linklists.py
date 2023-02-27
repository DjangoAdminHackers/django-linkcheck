from django.db.models import OuterRef, Subquery

from linkcheck import Linklist
from linkcheck.tests.sampleapp.models import Author, Book, Journal, Page


class BookLinklist(Linklist):
    """ Class to let linkcheck app discover fields containing links """
    model = Book
    object_filter = {}
    html_fields = ['description']


class PageLinklist(Linklist):
    """ Class to let linkcheck app discover fields containing links """
    model = Page


class AuthorLinklist(Linklist):
    """ Class to let linkcheck app discover fields containing links """
    model = Author
    object_filter = {}
    url_fields = ['website']


class JournalLinklist(Linklist):
    """ Class to let linkcheck app discover fields containing links """
    model = Journal
    html_fields = ['description']

    @classmethod
    def filter_callable(cls, objects):
        latest = Journal.objects.filter(title=OuterRef('title')).order_by('-version')
        return objects.filter(version=Subquery(latest.values('version')[:1]))


linklists = {
    'Books': BookLinklist,
    'Pages': PageLinklist,
    'Authors': AuthorLinklist,
    'Journals': JournalLinklist,
}
