from linkcheck import Linklist
from linkcheck.tests.sampleapp.models import Book

class SampleLinklist(Linklist):
    """ Class to let linkcheck app discover fields containing links """
    model = Book
    object_filter = {}
    html_fields = ['description']

linklists = {'Books': SampleLinklist}
