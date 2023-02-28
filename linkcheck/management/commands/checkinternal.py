from django.core.management.base import BaseCommand

from linkcheck.linkcheck_settings import MAX_CHECKS_PER_RUN
from linkcheck.utils import check_links


class Command(BaseCommand):

    help = 'Check and record internal link status'

    def add_arguments(self, parser):
        parser.add_argument(
            '-l', '--limit', type=int,
            help='Specifies the maximum number (int) of links to be checked. '
                 'Defaults to linkcheck_config setting.  Value less than 1 will check all')

    def handle(self, *args, **options):
        limit = options.get('limit', None) or MAX_CHECKS_PER_RUN

        self.stdout.write("Checking all internal links.")
        if limit != -1:
            self.stdout.write(f"Will run maximum of {limit} checks this run.")

        check_count = check_links(limit=limit, check_external=False)
        return f"{check_count} internal URLs have been checked."
