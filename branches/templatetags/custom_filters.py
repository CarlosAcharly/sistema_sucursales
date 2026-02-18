# En tu archivo de templatetags (ej: custom_filters.py)
from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    return value * arg

@register.filter
def divisibleby(value, arg):
    if arg and arg > 0:
        return (value / arg) * 100
    return 0