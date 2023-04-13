from django.contrib import admin, messages
from django.db.models import Count, Exists, OuterRef
from django.template.defaultfilters import yesno
from django.utils.translation import gettext_lazy as _

from ..models import TYPE_CHOICES, Link, Url
from ..templatetags.linkcheck_admin_tags import (
    linkcheck_actions,
    linkcheck_anchor_icon,
    linkcheck_links,
    linkcheck_ssl_icon,
    linkcheck_status_code,
    linkcheck_status_icon,
    linkcheck_url,
    linkcheck_wrap_in_div,
)


class StatusFilter(admin.BooleanFieldListFilter):
    """
    A custom status filter to include the ignore-status of links
    """
    title = _('status')
    parameter_name = 'status'
    ignore_kwarg = 'ignore'

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.ignore_val = params.get(self.ignore_kwarg)
        super().__init__(field, request, params, model, model_admin, field_path)

    def expected_parameters(self):
        return super().expected_parameters() + [self.ignore_kwarg]

    def choices(self, changelist):
        qs = Url.objects.annotate(
            ignore=Exists(Link.objects.filter(url=OuterRef('pk'), ignore=True))
        )
        field_choices = dict(self.field.flatchoices)
        return [
            {
                'selected': self.lookup_val is None and self.ignore_val is None and not self.lookup_val2,
                'query_string': changelist.get_query_string(
                    {self.lookup_kwarg: None},
                    [self.lookup_kwarg2, self.ignore_kwarg]
                ),
                'display': _('All') + f' ({Url.objects.count()})',
            },
            {
                'selected': self.lookup_val == '1' and self.ignore_val == 'False' and not self.lookup_val2,
                'query_string': changelist.get_query_string(
                    {self.lookup_kwarg: '1', self.ignore_kwarg: 'False'},
                    [self.lookup_kwarg2]
                ),
                'display': field_choices.get(True) + f' ({qs.filter(status=True, ignore=False).count()})',
            },
            {
                'selected': self.lookup_val == '0' and self.ignore_val == 'False' and not self.lookup_val2,
                'query_string': changelist.get_query_string(
                    {self.lookup_kwarg: '0', self.ignore_kwarg: 'False'},
                    [self.lookup_kwarg2]
                ),
                'display': field_choices.get(False) + f' ({qs.filter(status=False, ignore=False).count()})',
            },
            {
                'selected': self.lookup_val2 == 'True' and self.ignore_val == 'False' and not self.lookup_val,
                'query_string': changelist.get_query_string(
                    {self.lookup_kwarg2: 'True', self.ignore_kwarg: 'False'},
                    [self.lookup_kwarg]
                ),
                'display': field_choices.get(None) + f' ({qs.filter(status=None, ignore=False).count()})',
            },
            {
                'selected': self.ignore_val == 'True' and not self.lookup_val and not self.lookup_val2,
                'query_string': changelist.get_query_string(
                    {self.ignore_kwarg: 'True'},
                    [self.lookup_kwarg, self.lookup_kwarg2]
                ),
                'display': _('Ignored') + f' ({qs.filter(ignore=True).count()})',
            }
        ]


class TypeFilter(admin.SimpleListFilter):
    title = _('type')
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return TYPE_CHOICES

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        urls = [url.pk for url in queryset if url.type == self.value()]
        return queryset.filter(pk__in=urls)


class UrlAdmin(admin.ModelAdmin):
    list_display = [
        'list_url',
        'list_status',
        'list_ssl_status',
        'list_anchor_status',
        'list_status_code',
        'list_get_message',
        'list_type',
        'list_links',
        'list_ignore',
        'list_actions',
    ]
    list_filter = [('status', StatusFilter), TypeFilter]
    sortable_by = [
        'list_url',
        'list_status',
        'list_ssl_status',
        'list_anchor_status',
        'list_status_code',
        'list_links',
    ]
    actions = ['recheck', 'ignore', 'unignore']
    empty_value_display = ''
    list_per_page = 15

    @admin.display(ordering='url', description=Url._meta.get_field('url').verbose_name)
    def list_url(self, url):
        return linkcheck_url(url)

    @admin.display(ordering='status', description=Url._meta.get_field('status').verbose_name)
    def list_status(self, url):
        return linkcheck_status_icon(url)

    @admin.display(ordering='ssl_status', description=_('SSL'))
    def list_ssl_status(self, url):
        return linkcheck_ssl_icon(url)

    @admin.display(ordering='anchor_status', description=_('Anchor'))
    def list_anchor_status(self, url):
        return linkcheck_anchor_icon(url)

    @admin.display(ordering='status_code', description=Url._meta.get_field('status_code').verbose_name)
    def list_status_code(self, url):
        return linkcheck_status_code(url)

    @admin.display(description=_('message'))
    def list_get_message(self, url):
        return linkcheck_wrap_in_div(url.get_message)

    @admin.display(ordering='type', description=_('type'))
    def list_type(self, url):
        return url.get_type_display()

    @admin.display(ordering='links__count', description=Link._meta.verbose_name_plural)
    def list_links(self, url):
        return linkcheck_links(url)

    @admin.display(description=Link._meta.get_field('ignore').verbose_name)
    def list_ignore(self, url):
        return yesno(url.ignore)

    @admin.display(description=_('Actions'))
    def list_actions(self, url):
        return linkcheck_actions(url)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description=_('Recheck selected URLs'))
    def recheck(self, request, queryset):
        for url in queryset:
            url.check_url(external_recheck_interval=0)
        if len(queryset) == 1:
            messages.success(
                request,
                _('The URL "{}" was rechecked.').format(queryset[0]),
            )
        else:
            messages.success(
                request,
                _('The selected URLs were rechecked.'),
            )

    @admin.action(description=_('Ignore selected URLs'))
    def ignore(self, request, queryset):
        Link.objects.filter(url__in=queryset).update(ignore=True)
        if len(queryset) == 1:
            messages.success(
                request,
                _('The URL "{}" is now ignored.').format(queryset[0]),
            )
        else:
            messages.success(
                request,
                _('The selected URLs are now ignored.'),
            )

    @admin.action(description=_('No longer ignore selected URLs'))
    def unignore(self, request, queryset):
        Link.objects.filter(url__in=queryset).update(ignore=False)
        if len(queryset) == 1:
            messages.success(
                request,
                _('The URL "{}" is no longer ignored.').format(queryset[0]),
            )
        else:
            messages.success(
                request,
                _('The selected URLs are no longer ignored.'),
            )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            Count('links'),
            ignore=Exists(Link.objects.filter(url=OuterRef('pk'), ignore=True))
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if request.GET.get('status__exact') == '1':
            title = _('Valid URLs')
        elif request.GET.get('status__exact') == '0':
            title = _('Invalid URLs')
        elif request.GET.get('status__isnull') == 'True':
            title = _('Unchecked URLs')
        elif request.GET.get('ignore') == 'True':
            title = _('Ignored URLs')
        else:
            title = _('URLs')
        extra_context['title'] = title
        return super().changelist_view(request, extra_context=extra_context)

    class Media:
        css = {
            'all': ['linkcheck/css/style.css'],
        }
        js = ['linkcheck/js/actions.js']
