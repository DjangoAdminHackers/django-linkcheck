from django.core.management.base import BaseCommand

from linkcheck.utils import find_all_links

from linkcheck.models import all_linklists

class Command(BaseCommand):
    help = "Goes through all models registered with Linkcheck and records any links found"
    def execute(self, *args, **options):
        print "Finding all new links"
        find_all_links(all_linklists)

