from django.core.management.base import BaseCommand

from linkcheck.utils import find

class Command(BaseCommand):
    help = "Something happens"
    def execute(self, *args, **options):
        return find()

