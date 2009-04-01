from django.core.management.base import BaseCommand

from linkcheck.utils import check

class Command(BaseCommand):
    help = "Something happens"
    def execute(self, *args, **options):
        return check()

