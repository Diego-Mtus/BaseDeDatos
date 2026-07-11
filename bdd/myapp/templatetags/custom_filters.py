from django import template

register = template.Library()

@register.filter(name='split')
def split(value, arg):
    try:
        return value.split(arg[0])[int(arg[1])]
    except:
        return ""