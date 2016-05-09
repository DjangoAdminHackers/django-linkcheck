from optparse import make_option
from django.core.management.base import BaseCommand

from linkcheck.utils import check_links
from linkcheck.linkcheck_settings import EXTERNAL_RECHECK_INTERVAL
from linkcheck.linkcheck_settings import MAX_CHECKS_PER_RUN


class Command(BaseCommand):
    
    option_list = BaseCommand.option_list + (
        make_option('--externalinterval', '-e', type='int',
            help='Specifies the length of time in minutes until external links are rechecked. '
                 'Defaults to linkcheck_config setting'),
        make_option('--limit', '-l', type='int',
            help='Specifies the maximum number (int) of links to be checked. '
                 'Defaults to linkcheck_config setting.  Value less than 1 will check all'),
    )
    help = 'Check and record external link status'

    def execute(self, *args, **options):
        if options['externalinterval']:
            externalinterval = options['externalinterval']
        else:
            externalinterval = EXTERNAL_RECHECK_INTERVAL
            
        if options['limit']:
            limit = options['limit']
        else:
            limit = MAX_CHECKS_PER_RUN

        print("Checking all external links that haven't been tested for %s minutes." % externalinterval)
        if limit!=-1:
            print("Will run maximum of %s checks this run." % limit)

        return check_links(external_recheck_interval=externalinterval, limit=limit, check_internal=False)

