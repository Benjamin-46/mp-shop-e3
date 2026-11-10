"""Genera el diagrama de la base de datos a partir de los modelos de Django.

Como el diagrama se construye leyendo los modelos reales, siempre mantiene
correspondencia con el código (Evaluación 2, punto 3).

Uso:  python manage.py generar_diagrama
Salida: docs/diagrama_bd.dot y docs/diagrama_bd.png (el PNG requiere Graphviz:
https://graphviz.org/download/ ; si no está instalado se genera solo el .dot,
que se puede pegar en https://dreampuf.github.io/GraphvizOnline/).
"""
import shutil
import subprocess
from html import escape

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand


def tipo_columna(campo):
    tipo = campo.get_internal_type()
    if getattr(campo, "max_length", None):
        return f"{tipo}({campo.max_length})"
    return tipo


class Command(BaseCommand):
    help = "Genera el diagrama entidad-relación (DOT/PNG) desde los modelos."

    def handle(self, *args, **options):
        modelos = list(apps.get_app_config("tienda").get_models())
        lineas = [
            "digraph MP_Shop {",
            '  graph [rankdir=LR, bgcolor="white", fontname="Helvetica", pad=0.4, nodesep=0.45, ranksep=1.6,'
            ' label="MP Shop (Music Pro) - Diagrama de base de datos", labelloc=t, fontsize=20];',
            '  node [shape=plain, fontname="Helvetica"];',
            '  edge [color="#444444", dir=both, arrowtail=crow, arrowhead=tee, fontname="Helvetica", fontsize=10];',
        ]
        relaciones = []
        for m in modelos:
            filas = []
            for campo in m._meta.concrete_fields:
                marcas = []
                if campo.primary_key:
                    marcas.append("PK")
                if campo.is_relation:
                    marcas.append("FK")
                if campo.unique and not campo.primary_key:
                    marcas.append("UQ")
                color = "#fff3cd" if campo.primary_key else ("#e7f1ff" if campo.is_relation else "white")
                filas.append(
                    f'<TR><TD ALIGN="LEFT" BGCOLOR="{color}">{escape(" ".join(marcas)) or "&nbsp;"}</TD>'
                    f'<TD ALIGN="LEFT" BGCOLOR="{color}" PORT="{campo.column}">{escape(campo.column)}</TD>'
                    f'<TD ALIGN="LEFT" BGCOLOR="{color}"><FONT COLOR="#555555">{escape(tipo_columna(campo))}</FONT></TD></TR>'
                )
                if campo.is_relation:
                    relaciones.append((m._meta.db_table, campo.column, campo.related_model._meta.db_table))
            tabla = (
                f'  {m._meta.db_table} [label=<<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">'
                f'<TR><TD COLSPAN="3" BGCOLOR="#212529"><FONT COLOR="white"><B>{escape(m._meta.db_table)}</B></FONT></TD></TR>'
                + "".join(filas) + "</TABLE>>];"
            )
            lineas.append(tabla)
        for origen, columna, destino in relaciones:
            # :e = sale por el lado derecho de la columna FK; :w = entra por el
            # lado izquierdo de la PK. Evita que las flechas crucen el texto.
            lineas.append(f'  {origen}:{columna}:e -> {destino}:id:w;')
        lineas.append("}")

        carpeta = settings.BASE_DIR / "docs"
        carpeta.mkdir(exist_ok=True)
        dot = carpeta / "diagrama_bd.dot"
        dot.write_text("\n".join(lineas), encoding="utf-8")
        self.stdout.write(f"Diagrama DOT escrito en {dot}")

        if shutil.which("dot"):
            png = carpeta / "diagrama_bd.png"
            subprocess.run(["dot", "-Tpng", "-Gdpi=150", str(dot), "-o", str(png)], check=True)
            self.stdout.write(self.style.SUCCESS(f"Imagen generada en {png}"))
        else:
            self.stdout.write(self.style.WARNING("Graphviz no está instalado: solo se generó el .dot"))
