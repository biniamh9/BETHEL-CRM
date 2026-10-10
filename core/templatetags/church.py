from decimal import Decimal

from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def usd(value, cents=False):
    """$12,345 (or $12,345.67 with usd:True)."""
    try:
        value = Decimal(value or 0)
    except Exception:
        return value
    return f"${value:,.2f}" if cents else f"${value:,.0f}"


@register.inclusion_tag("partials/form_fields.html")
def form_fields(form, only=""):
    names = [n.strip() for n in only.split(",") if n.strip()]
    fields = [form[n] for n in names if n in form.fields] if names else list(form)
    return {"fields": fields, "form": form, "show_errors": not names}


@register.simple_tag
def progress_ring(percent, size=180):
    """An SVG ring showing campaign progress."""
    r = 70
    circ = 2 * 3.14159 * r
    dash = circ * min(float(percent), 100) / 100
    return format_html(
        '<svg class="ring" width="{s}" height="{s}" viewBox="0 0 180 180" role="img" aria-label="{p}% of goal">'
        '<circle cx="90" cy="90" r="{r}" class="ring-track"/>'
        '<circle cx="90" cy="90" r="{r}" class="ring-fill" stroke-dasharray="{d} {c}" transform="rotate(-90 90 90)"/>'
        '<text x="90" y="88" class="ring-pct">{p}%</text><text x="90" y="112" class="ring-sub">of goal</text></svg>',
        s=size, r=r, d=f"{dash:.1f}", c=f"{circ:.1f}", p=percent,
    )
