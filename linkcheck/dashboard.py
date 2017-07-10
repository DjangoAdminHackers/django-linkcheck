from admin_tools.dashboard import modules
from linkcheck.views import get_status_message

try:
    from django.urls import reverse
except ImportError:  # Django < 1.10
    from django.core.urlresolvers import reverse


linkcheck_dashboard_module = modules.LinkList(
    title="Linkchecker",
    pre_content=get_status_message,
    children=(
        {'title': 'Valid links', 'url': reverse('linkcheck_report') + '?filters=show_valid'},
        {'title': 'Broken links', 'url': reverse('linkcheck_report')},
        {'title': 'Untested links', 'url': reverse('linkcheck_report') + '?filters=show_unchecked'},
        {'title': 'Ignored links', 'url': reverse('linkcheck_report') + '?filters=ignored'},
    )
)