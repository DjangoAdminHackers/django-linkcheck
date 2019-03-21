from django.conf import settings
from django.db import models

# Used for coverage view

DEFAULT_HTML_FIELD_CLASSES = []
DEFAULT_IMAGE_FIELD_CLASSES = [models.ImageField]
DEFAULT_URL_FIELD_CLASSES = [models.FileField]


# The coverage view warns you if you use any fields that haven't been registered with Linkcheck when they should have
# Let's add a few likely candidates. You can add your own via the LINKCHECK_EXTRA_xxx_FIELD_CLASSES setting
# Pull requests welcome

try:
    from sorl.thumbnail import ImageField
    DEFAULT_IMAGE_FIELD_CLASSES.append(ImageField)
except ImportError:
    pass

try:
    from mcefield.custom_fields import MCEField
    DEFAULT_HTML_FIELD_CLASSES.append(MCEField)
except ImportError:
    pass

try:
    from select_url_field.fields import SelectURLField
    DEFAULT_URL_FIELD_CLASSES.append(SelectURLField)
except ImportError:
    pass

try:
    from filebrowser.fields import FileBrowseField
    DEFAULT_URL_FIELD_CLASSES.append(FileBrowseField)
except ImportError:
    pass

try:
    from browse_and_upload_field.fields import FileBrowseAndUploadField
    DEFAULT_URL_FIELD_CLASSES.append(FileBrowseAndUploadField)
except ImportError:
    pass


HTML_FIELD_CLASSES = getattr(settings, 'LINKCHECK_EXTRA_HTML_FIELD_CLASSES', []) + DEFAULT_HTML_FIELD_CLASSES
IMAGE_FIELD_CLASSES = getattr(settings, 'LINKCHECK_EXTRA_IMAGE_FIELD_CLASSES', []) + DEFAULT_IMAGE_FIELD_CLASSES
URL_FIELD_CLASSES = getattr(settings, 'LINKCHECK_EXTRA_URL_FIELD_CLASSES', []) + DEFAULT_URL_FIELD_CLASSES

# Main (non-coverage related) settings

EXTERNAL_RECHECK_INTERVAL = getattr(settings, 'LINKCHECK_EXTERNAL_RECHECK_INTERVAL', 10080)  # 1 week
EXTERNAL_REGEX_STRING = getattr(settings, 'LINKCHECK_EXTERNAL_REGEX_STRING', r'^https?://')
LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT = getattr(settings, 'LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT', 10)
MAX_CHECKS_PER_RUN = getattr(settings, 'LINKCHECK_MAX_CHECKS_PER_RUN', -1)
MAX_URL_LENGTH = getattr(settings, 'LINKCHECK_MAX_URL_LENGTH', 255)
MEDIA_PREFIX = getattr(settings, 'LINKCHECK_MEDIA_PREFIX', settings.MEDIA_URL)
RESULTS_PER_PAGE = getattr(settings, 'LINKCHECK_RESULTS_PER_PAGE', 500)
SITE_DOMAINS = getattr(settings, 'LINKCHECK_SITE_DOMAINS', [])
DISABLE_LISTENERS = getattr(settings, 'LINKCHECK_DISABLE_LISTENERS', False)
