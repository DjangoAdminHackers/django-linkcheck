from optparse import make_option
from django.core.management.base import BaseCommand

from linkcheck.utils import check_links
from linkcheck.linkcheck_settings import MAX_CHECKS_PER_RUN


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--limit',
            '-l', type='int',
            help='Specifies the maximum number (int) of links to be checked. Defaults to linkcheck_config setting. '
                 'Value less than 1 will check all'
        ),
    )
    help = 'Check and record internal link status'

    def execute(self, *args, **options):
            
        if options['limit']:
            limit = options['limit']
        else:
            limit = MAX_CHECKS_PER_RUN

        print("Checking all internal links.")
        if limit != -1:
            print("Will run maximum of %s checks this run." % limit)

        return check_links(limit=limit, check_external=False)
