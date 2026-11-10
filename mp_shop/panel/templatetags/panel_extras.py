from django import template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils import timezone

from tienda.models import Venta

register = template.Library()


@register.filter
def formato(valor, tipo):
    """Da formato a una celda de reporte según el tipo de columna."""
    if valor is None:
        return "—"
    if tipo == "clp":
        return f"${intcomma(valor)}"
    if tipo == "num":
        return intcomma(valor)
    if tipo == "fecha":
        return timezone.localtime(valor).strftime("%d-%m-%Y %H:%M")
    if tipo == "estado":
        try:
            return Venta.Estado(valor).label
        except ValueError:
            return valor
    return valor


@register.filter
def indice(secuencia, i):
    return secuencia[i]


@register.filter
def dictget(diccionario, clave):
    """Lee diccionario[clave] dentro de una plantilla."""
    return diccionario.get(clave, "")
