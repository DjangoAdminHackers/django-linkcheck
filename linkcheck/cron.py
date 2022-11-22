# This file works with our fork of django-cron.
# It's use is optional
# Use any means you like to run scheduled jobs.
#
# Note - you only need to run scheduled jobs if you want to check external links
# that may have died since the link was last edited
#
# Links are checked via signals any time a link-containing object is saved by Django

from django_cron import WEEK, Job, cronScheduler

from linkcheck.linkcheck_settings import (
    EXTERNAL_RECHECK_INTERVAL,
    MAX_CHECKS_PER_RUN,
)
from linkcheck.utils import check_links, find_all_links


class RunLinkCheckFind(Job):

    run_every = WEEK

    def job(self):
        find_all_links()


cronScheduler.register(RunLinkCheckFind)


class RunLinkCheckInternal(Job):

    run_every = WEEK

    def job(self):
        check_links(limit=MAX_CHECKS_PER_RUN, check_external=False)


cronScheduler.register(RunLinkCheckInternal)


class RunLinkCheckExternal(Job):

    run_every = WEEK

    def job(self):
        check_links(
            external_recheck_interval=EXTERNAL_RECHECK_INTERVAL,
            limit=MAX_CHECKS_PER_RUN,
            check_internal=False,
        )


cronScheduler.register(RunLinkCheckExternal)
