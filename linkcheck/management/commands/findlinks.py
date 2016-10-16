from django.core.management.base import BaseCommand

from linkcheck.utils import find_all_links


class Command(BaseCommand):

    help = "Goes through all models registered with Linkcheck and records any links found"

    def handle(self, *args, **options):
        self.stdout.write("Finding all new links...")
        results = find_all_links()
        return ("%(urls_created)s new Url object(s), %(links_created)s new Link object(s), "
                "%(urls_deleted)s Url object(s) deleted") % results
