import django_admin_blocks

from linkcheck.views import get_status_message

"""Legacy internal helper"""


def notification():
    return get_status_message()


django_admin_blocks.register({
    'errors': (notification,),
})
