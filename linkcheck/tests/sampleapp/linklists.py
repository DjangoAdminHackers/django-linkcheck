from linkcheck import Linklist
from linkcheck.tests.sampleapp.models import Author, Book


class BookLinklist(Linklist):
    """ Class to let linkcheck app discover fields containing links """
    model = Book
    object_filter = {}
    html_fields = ['description']
    alert_mail_field = 'author.mail'

class AuthorLinklist(Linklist):
    """ Class to let linkcheck app discover fields containing links """
    model = Author
    object_filter = {}
    url_fields = ['website']
    alert_mail_field = 'mail'



linklists = {
    'Books': BookLinklist,
    'Authors': AuthorLinklist,
}
