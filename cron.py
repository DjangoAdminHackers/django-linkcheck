# This file works with django-cron.
# It's use is optional.
# Use any means you like to run scheduled jobs.
# Note - you only need to run scheduled jobs if you want to check external links are still working
# Internal links are handled automatically via signals.

from django_cron import cronScheduler
from django_cron import Job

from linkcheck.utils import check_internal_links
from linkcheck.utils import check_external_links
from linkcheck.utils import find_all_links

from linkcheck.models import all_linklists

class RunLinkCheckFind(Job):
        run_every = 86400
        def job(self):  
            find_all_links(all_linklists)
cronScheduler.register(RunLinkCheckFind)

class RunLinkCheckInternal(Job):
        run_every = 86400
        def job(self):
            check_internal_links()
cronScheduler.register(RunLinkCheckInternal)

class RunLinkCheckExternal(Job):
        run_every = 86400
        def job(self):  
            check_external_links()
cronScheduler.register(RunLinkCheckExternal)

