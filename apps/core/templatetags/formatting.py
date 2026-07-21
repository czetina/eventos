from django import template
from django.template.defaultfilters import date as date_filter

register = template.Library()

DATE_FORMAT_PATTERNS = {
    "iso": "Y-m-d",
    "dmy": "d/m/Y",
    "mdy": "m/d/Y",
}


@register.filter(name="money")
def money(value):
    """Formats a number with comma thousands separators and a dot decimal
    separator (e.g. 100,000.99), independent of the active language."""
    if value in (None, ""):
        value = 0
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    return "{:,.2f}".format(value)


@register.simple_tag(takes_context=True)
def cdate(context, value, show_weekday=None):
    """Formats a date per the current company's date_format setting
    (AAAA-MM-DD / DD/MM/AAAA / MM/DD/AAAA), optionally with the weekday name."""
    if not value:
        return ""
    company = context.get("current_company")
    pattern = DATE_FORMAT_PATTERNS.get(getattr(company, "date_format", "dmy"), "d/m/Y")
    weekday = show_weekday if show_weekday is not None else getattr(company, "date_show_weekday", False)
    if weekday:
        pattern = "l, " + pattern
    return date_filter(value, pattern)
