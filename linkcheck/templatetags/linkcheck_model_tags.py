from django import template

register = template.Library()


@register.filter
def get_verbose_name_plural(content_type):
    """
    Returns verbose_name_plural for a content type.
    """
    return content_type.model_class()._meta.verbose_name_plural.title()
