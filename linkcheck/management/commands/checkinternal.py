from django.core.management.base import BaseCommand

from linkcheck.utils import check_links
from linkcheck.linkcheck_settings import MAX_CHECKS_PER_RUN


class Command(BaseCommand):

    help = 'Check and record internal link status'

    def add_arguments(self, parser):
        parser.add_argument('-l', '--limit', type=int,
            help='Specifies the maximum number (int) of links to be checked. '
                 'Defaults to linkcheck_config setting.  Value less than 1 will check all')

    def handle(self, *args, **options):
        limit = options.get('limit', None) or MAX_CHECKS_PER_RUN

        self.stdout.write("Checking all internal links.")
        if limit != -1:
            self.stdout.write("Will run maximum of %s checks this run." % limit)

        check_count = check_links(limit=limit, check_external=False)
        return "%s internal URLs have been checked." % (check_count)
