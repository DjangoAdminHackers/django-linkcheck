from optparse import make_option
from django.core.management.base import BaseCommand

from linkcheck.utils import check_external_links
from linkcheck.settings import EXTERNAL_RECHECK_INTERVAL
from linkcheck.settings import MAX_CHECKS_PER_RUN

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--externalinterval', '-e', type='int',
            help='Specifies the length of time in seconds until external links are rechecked. Defaults to linkcheck_config setting'),
        make_option('--limit', '-l', type='int',
            help='Specifies the maximum number (int) of links to be checked. Defaults to linkcheck_config setting.  Value less than 1 will check all'),
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
        print "Checking external links that haven't run for %s seconds. Will run maximum of %s checks this run." % (externalinterval, limit)
        return check_external_links(externalinterval, limit)

