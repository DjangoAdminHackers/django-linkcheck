from django.core.management.base import BaseCommand

from linkcheck.utils import unignore


class Command(BaseCommand):

    help = "Updates the `ignore` status of all links to `False`"

    def execute(self, *args, **options):
        print("Unignoring all links")
        unignore()
