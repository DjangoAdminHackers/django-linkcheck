from django import template
from django.contrib.admin.utils import display_for_value
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html, mark_safe
from django.utils.text import Truncator
from django.utils.translation import gettext as _

register = template.Library()

MAX_URL_CHARS = 100


@register.simple_tag
def linkcheck_url(url):
    url_tag = format_html(
        '<div><a href="{}" target="_blank" rel="noopener noreferrer" class="">{}</a></div>',
        url.url,
        Truncator(url.url).chars(MAX_URL_CHARS),
    )
    if url.redirect_to:
        url_tag += format_html(
            '<div>↪&nbsp;<a href="{}" target="_blank" rel="noopener noreferrer" class="">{}</a></div>',
            url.redirect_to,
            Truncator(url.redirect_to).chars(MAX_URL_CHARS),
        )
    return url_tag


@register.simple_tag
def linkcheck_status_icon(url):
    icon_tag = display_for_value(url.status, '', boolean=True)
    return format_html(
        '<span title="{}">{}</span>',
        url.get_status_display(),
        mark_safe(icon_tag),
    )


@register.simple_tag
def linkcheck_ssl_icon(url):
    if url.internal:
        return ''
    if url.external_url.startswith('http://'):
        icon_tag = display_for_value(False, '', boolean=True)
    elif url.ssl_status is None:
        icon_tag = display_for_value(None, '', boolean=True)
    else:
        icon_class = 'linkcheck-lock' if url.ssl_status else 'linkcheck-lock-open'
        icon_tag = format_html('<span class="linkcheck-icon {}"></span>', icon_class)
    return format_html(
        '<span title="{}">{}</span>',
        url.ssl_message,
        mark_safe(icon_tag),
    )


@register.simple_tag
def linkcheck_anchor_icon(url):
    if not url.has_anchor or not url.last_checked:
        return ''
    icon_tag = display_for_value(url.anchor_status, '', boolean=True)
    return format_html(
        '<span title="{}">{}</span>',
        f'{url.anchor_message}: #{url.anchor}',
        mark_safe(icon_tag),
    )


@register.simple_tag
def linkcheck_status_code(url):
    return url.get_redirect_status_code_display() or url.get_status_code_display()


@register.simple_tag
def linkcheck_wrap_in_div(text):
    return format_html(
        '<div>{}</div>',
        text,
    )


@register.simple_tag
def linkcheck_links(url):
    try:
        link_count = url.links__count
    except AttributeError:
        link_count = url.links.count()
    return format_html(
        '<a href="{}?url__id__exact={}">{}</a>',
        reverse('admin:linkcheck_link_changelist'),
        url.pk,
        link_count,
    )


@register.simple_tag
def linkcheck_actions(url, obj=None):
    if not obj:
        obj = url
    recheck_link = '' if url.status else format_html(
        '<a href="#" data-action="{}" data-id="{}">{}</a>',
        'recheck',
        obj.pk,
        _('Recheck'),
    )
    ignore_link = format_html(
        '<a href="#" data-action="{}" data-id="{}">{}</a>',
        'unignore' if obj.ignore else 'ignore',
        obj.pk,
        _('Unignore') if obj.ignore else _('Ignore'),
    )
    return format_html(
        '{} {}',
        mark_safe(recheck_link),
        mark_safe(ignore_link),
    )


@register.simple_tag
def linkcheck_source(link):
    try:
        view_link = format_html(
            '<span><a href="{}">{}</a></span> | ',
            link.content_object.get_absolute_url(),
            _('view'),
        )
    except AttributeError:
        view_link = ''
    try:
        edit_link = format_html(
            '<span><a href="{}">{}</a></span> | ',
            reverse(
                f'admin:{link.content_type.app_label}_{link.content_type.model}_change',
                kwargs={'object_id': link.object_id}
            ),
            _('edit'),
        )
    except NoReverseMatch:
        edit_link = ''
    filter_link = format_html(
        '<span><a href="{}">{}</a></span>',
        f'?content_type_id__exact={link.content_type_id}&object_id__exact={link.object_id}',
        _('filter'),
    )
    return format_html(
        '<span>{}</span> <span>({}{}{})</span>',
        link.content_object,
        mark_safe(view_link),
        mark_safe(edit_link),
        mark_safe(filter_link),
    )
