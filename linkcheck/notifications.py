import admin_notifications

from linkcheck.models import Link
from linkcheck.listeners import still_updating

def notification():
    if still_updating:
        return "Still checking. Please refresh this page in a short while. "
    else:
        broken_links = Link.objects.filter(ignore=False, url__status=False).count()
        if broken_links:
            return "You have %s broken link%s.<br>You can view or fix them using the <a href='/admin/linkcheck/'>Link Manager</a>." % (broken_links, "s" if broken_links>1 else "")
        else:
            return ''

admin_notifications.register(notification)
