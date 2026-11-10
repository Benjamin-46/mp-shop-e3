"""Vistas de la página de reportes ORM (Evaluación 3, Parte 2)."""
import inspect
from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.http import Http404

from tienda.models import Categoria
from tienda.utils import normalizar_rut

from .reportes import REPORTES


def _leer_parametros(request, definiciones):
    """Convierte los parámetros GET al tipo correcto. Devuelve (valores, errores)."""
    valores, errores, crudos = {}, [], {}
    for d in definiciones:
        texto = request.GET.get(d["nombre"], "").strip()
        crudos[d["nombre"]] = texto
        if not texto:
            continue
        try:
            if d["tipo"] in ("entero", "categoria"):
                valores[d["nombre"]] = int(texto)
            elif d["tipo"] == "anio":
                valores[d["nombre"]] = int(texto)
                if not 2000 <= valores[d["nombre"]] <= 2100:
                    raise ValueError
            elif d["tipo"] == "fecha":
                valores[d["nombre"]] = date.fromisoformat(texto)
            elif d["tipo"] == "rut":
                valores[d["nombre"]] = normalizar_rut(texto)
        except ValueError:
            errores.append(f"El valor de «{d['etiqueta']}» no es válido.")
    return valores, errores, crudos


@login_required
def indice(request):
    """Listado de los 20 reportes agrupados por nivel."""
    niveles = {}
    for r in REPORTES.values():
        niveles.setdefault(r["nivel"], []).append(r)
    return render(request, "panel/reportes_indice.html", {
        "titulo_pagina": "Reportes de consultas ORM", "niveles": niveles,
    })


@login_required
def reporte(request, numero):
    """Ejecuta un reporte. Si faltan parámetros, muestra el formulario para pedirlos."""
    definicion = REPORTES.get(numero)
    if definicion is None:
        raise Http404("Reporte inexistente")

    parametros = definicion["parametros"]
    valores, errores, crudos = _leer_parametros(request, parametros)
    if parametros and "anio" in {p["nombre"] for p in parametros} and not crudos.get("anio") and not request.GET:
        crudos["anio"] = str(date.today().year)

    contexto = {
        "titulo_pagina": f"Reporte {numero}",
        "definicion": definicion,
        "parametros": parametros,
        "crudos": crudos,
        "errores": errores,
        "categorias": Categoria.objects.all() if any(p["tipo"] == "categoria" for p in parametros) else None,
        # Evidencia para la defensa: el código ORM real de la consulta.
        "codigo": inspect.getsource(definicion["funcion"]),
    }

    completos = all(p["nombre"] in valores for p in parametros)
    if request.GET and completos and not errores:
        if "precio_min" in valores and valores["precio_min"] > valores["precio_max"]:
            contexto["errores"] = ["El precio mínimo no puede ser mayor que el máximo."]
        elif "desde" in valores and valores["desde"] > valores["hasta"]:
            contexto["errores"] = ["La fecha «Desde» no puede ser posterior a «Hasta»."]
        else:
            resultado = definicion["funcion"](valores)
            pagina = Paginator(resultado["consulta"], 25).get_page(request.GET.get("page"))
            parametros_url = request.GET.copy()
            parametros_url.pop("page", None)
            contexto.update({
                "ejecutado": True,
                "columnas": resultado["columnas"],
                "pagina": pagina,
                "resumen": resultado.get("resumen"),
                "qs": parametros_url.urlencode(),
            })
    elif not parametros:
        # Reportes sin parámetros se ejecutan al abrirlos.
        resultado = definicion["funcion"]({})
        pagina = Paginator(resultado["consulta"], 25).get_page(request.GET.get("page"))
        contexto.update({
            "ejecutado": True, "columnas": resultado["columnas"], "pagina": pagina,
            "resumen": resultado.get("resumen"), "qs": "",
        })
    return render(request, "panel/reporte.html", contexto)
