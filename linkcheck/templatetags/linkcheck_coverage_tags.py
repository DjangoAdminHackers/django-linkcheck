from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def render_config(config):

    html = []
    # Remove blank lines
    for line in render_to_string('linkcheck/suggested_linklist.html', config).splitlines():
        if line.strip():
            html.append(line)

    return mark_safe('<pre>{}</pre>'.format('\n'.join(html)))
