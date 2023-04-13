from django.contrib import admin, messages
from django.template.defaultfilters import yesno
from django.utils.translation import gettext_lazy as _

from ..models import Link, Url
from ..templatetags.linkcheck_admin_tags import (
    linkcheck_actions,
    linkcheck_source,
    linkcheck_status_icon,
    linkcheck_url,
    linkcheck_wrap_in_div,
)


class LinkAdmin(admin.ModelAdmin):
    list_display = [
        'list_url',
        'list_status',
        'list_text',
        'list_content_object',
        'content_type',
        'list_field',
        'list_ignore',
        'list_actions',
    ]
    actions = ['recheck', 'ignore', 'unignore']
    list_per_page = 15

    @admin.display(ordering='url', description=Url._meta.get_field('url').verbose_name)
    def list_url(self, link):
        return linkcheck_url(link.url)

    @admin.display(ordering='url__status', description=Url._meta.get_field('status').verbose_name)
    def list_status(self, link):
        return linkcheck_status_icon(link.url)

    @admin.display(description=_('link text'))
    def list_text(self, link):
        return linkcheck_wrap_in_div(link.text)

    @admin.display(ordering='object_id', description=_('source'))
    def list_content_object(self, link):
        return linkcheck_source(link)

    @admin.display(ordering='field', description=Link._meta.get_field('field').verbose_name)
    def list_field(self, link):
        return type(link.content_object)._meta.get_field(link.field).verbose_name

    @admin.display(ordering='ignore', description=Link._meta.get_field('ignore').verbose_name)
    def list_ignore(self, link):
        return yesno(link.ignore)

    @admin.display(description=_('Actions'))
    def list_actions(self, link):
        return linkcheck_actions(link.url, obj=link)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description=_('Recheck selected links'))
    def recheck(self, request, queryset):
        for link in queryset:
            link.url.check_url(external_recheck_interval=0)
        if len(queryset) == 1:
            messages.success(
                request,
                _('The link "{}" was rechecked.').format(queryset[0].url),
            )
        else:
            messages.success(
                request,
                _('The selected links were rechecked.'),
            )

    @admin.action(description=_('Ignore selected links'))
    def ignore(self, request, queryset):
        queryset.update(ignore=True)
        if len(queryset) == 1:
            messages.success(
                request,
                _('The link "{}" is now ignored.').format(queryset[0].url),
            )
        else:
            messages.success(
                request,
                _('The selected links are now ignored.'),
            )

    @admin.action(description=_('No longer ignore selected links'))
    def unignore(self, request, queryset):
        queryset.update(ignore=False)
        if len(queryset) == 1:
            messages.success(
                request,
                _('The link "{}" is no longer ignored.').format(queryset[0].url),
            )
        else:
            messages.success(
                request,
                _('The selected links are no longer ignored.'),
            )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if request.GET.get('ignore__exact') == '1':
            title = _('Ignored links')
        elif request.GET.get('ignore__exact') == '0':
            title = _('Not ignored links')
        else:
            title = _('Links')
        extra_context['title'] = title
        return super().changelist_view(request, extra_context=extra_context)

    class Media:
        css = {
            'all': ['linkcheck/css/style.css'],
        }
        js = ['linkcheck/js/actions.js']
