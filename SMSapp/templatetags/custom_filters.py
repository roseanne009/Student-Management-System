from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def split(value, arg):
    return value.split(arg)

@register.filter(name='sub')
def sub(value, arg):
    """Subtracts the arg from the value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value
