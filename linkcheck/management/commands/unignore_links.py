from django.core.management.base import BaseCommand

from linkcheck.utils import unignore


class Command(BaseCommand):

    help = "Goes through all models registered with Linkcheck and records any links found"

    def execute(self, *args, **options):
        print("Unignoring all links")
        unignore()
