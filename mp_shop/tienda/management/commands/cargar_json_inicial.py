"""Migra los datos mock de la Evaluación 1 (productos.json) a la base de datos.

Da continuidad al trabajo anterior: el catálogo que antes vivía en un archivo
JSON pasa a ser registros reales de la base de datos. Es idempotente: se puede
ejecutar varias veces sin duplicar productos (usa el SKU como identificador).

Uso:  python manage.py cargar_json_inicial
"""
import json

from django.core.management.base import BaseCommand
from django.db import transaction

from tienda.data_access import RUTA_JSON
from tienda.models import Categoria, Inventario, Marca, Producto, Sucursal

SUCURSALES = [
    ("Casa Matriz", "Santiago", "Av. Providencia 1234", "+56 2 2345 6789"),
    ("Sucursal Valparaíso", "Valparaíso", "Calle Esmeralda 456", "+56 32 234 5678"),
    ("Sucursal Concepción", "Concepción", "Calle Barros Arana 789", "+56 41 234 5678"),
]


class Command(BaseCommand):
    help = "Carga sucursales base y los productos del JSON de la Evaluación 1."

    @transaction.atomic
    def handle(self, *args, **options):
        sucursales = []
        for nombre, ciudad, direccion, telefono in SUCURSALES:
            suc, _ = Sucursal.objects.get_or_create(
                nombre=nombre,
                defaults={"ciudad": ciudad, "direccion": direccion, "telefono": telefono},
            )
            sucursales.append(suc)

        marca, _ = Marca.objects.get_or_create(nombre="Music Pro", defaults={"pais_origen": "Chile"})

        with open(RUTA_JSON, encoding="utf-8") as archivo:
            productos = json.load(archivo)

        nuevos = 0
        for item in productos:
            categoria, _ = Categoria.objects.get_or_create(nombre=item["categoria"])
            producto, creado = Producto.objects.get_or_create(
                sku=f"MP-E1-{item['id']:04d}",
                defaults={
                    "nombre": item["nombre"],
                    "descripcion": item.get("descripcion", ""),
                    "precio": item["precio"],
                    "imagen": item.get("imagen", ""),
                    "categoria": categoria,
                    "marca": marca,
                    "destacado": item["id"] <= 3,
                },
            )
            if creado:
                nuevos += 1
                # El stock del JSON se asigna a la casa matriz.
                Inventario.objects.create(
                    producto=producto, sucursal=sucursales[0], stock=item["stock"]
                )

        self.stdout.write(self.style.SUCCESS(
            f"{len(sucursales)} sucursales verificadas, {nuevos} producto(s) nuevo(s) "
            f"importados desde {RUTA_JSON.name}."))
