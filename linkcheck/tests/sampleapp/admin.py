from django.contrib import admin

from linkcheck.admin import LinkAdmin, UrlAdmin
from linkcheck.models import Link, Url

admin.site.register(Url, UrlAdmin)
admin.site.register(Link, LinkAdmin)
