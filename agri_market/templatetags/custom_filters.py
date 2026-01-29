"""
Filtres de template personnalisés pour e_agri
"""

from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplier deux valeurs"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
