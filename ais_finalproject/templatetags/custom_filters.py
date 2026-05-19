from django import template

register = template.Library()

@register.filter
def rupiah(value):
    try:
        if value is None:
            return "Rp 0"
        return f"Rp {int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return value

@register.filter
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()

@register.filter
def abs_value(value):
    try:
        return value if value >= 0 else -value
    except (TypeError, ValueError):
        return value