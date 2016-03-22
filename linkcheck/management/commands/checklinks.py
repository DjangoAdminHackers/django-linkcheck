from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from linkcheck.linkcheck_settings import EXTERNAL_RECHECK_INTERVAL, MAX_CHECKS_PER_RUN
from linkcheck.utils import check_links


class Command(BaseCommand):
    
    option_list = BaseCommand.option_list + (
        make_option('--externalinterval', '-e', type='int',
            help='Specifies the length of time in minutes until external links are rechecked. '
                 'Defaults to linkcheck_config setting'
        ),
        make_option('--limit', '-l', type='int',
            help='Specifies the maximum number (int) of links to be checked. '
                 'Defaults to linkcheck_config setting.  Value less than 1 will check all'
        ),
    )
    help = 'Check and record internal and external link status'

    def handle(self, *args, **options):
        externalinterval = options['externalinterval'] or EXTERNAL_RECHECK_INTERVAL
        limit = options['limit'] or MAX_CHECKS_PER_RUN

        self.stdout.write("Checking all links that haven't been tested for %s minutes." % externalinterval)
        if limit != -1:
            self.stdout.write("Will run maximum of %s checks this run." % limit)

        internal_checked = check_links(limit=limit, check_external=False)
        external_checked = check_links(external_recheck_interval=externalinterval, limit=limit, check_internal=False)
        return "%s internal URLs and %s external URLs have been checked." % (internal_checked, external_checked)
