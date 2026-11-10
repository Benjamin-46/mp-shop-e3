"""Genera datos de prueba ficticios con Faker (Evaluación 2, punto 6).

Uso:
    python manage.py poblar_datos productos 100
    python manage.py poblar_datos clientes 1000
    python manage.py poblar_datos ventas 100000
    python manage.py poblar_datos productos 1000000 --lote 10000

Cargas pedidas por el docente: 100, 1.000, 100.000 y 1.000.000 de registros.
Para que la carga masiva sea rápida se usa bulk_create() (un INSERT por lote,
no uno por fila) dentro de una transacción.
"""
import random
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone
from faker import Faker

from tienda.utils import digito_verificador  # noqa: F401  (también se usa en las pruebas)
from tienda.models import (
    Categoria, Cliente, DetalleVenta, Inventario, Marca, Producto, Sucursal, Venta,
)

# Tipos de producto por categoría (Faker no conoce instrumentos musicales).
CATALOGO_BASE = {
    "Guitarras": ["Guitarra Eléctrica", "Guitarra Acústica", "Guitarra Clásica"],
    "Bajos": ["Bajo Eléctrico 4 Cuerdas", "Bajo Eléctrico 5 Cuerdas", "Bajo Acústico"],
    "Baterías": ["Batería Acústica", "Batería Electrónica", "Caja Redoblante"],
    "Cuerdas": ["Set de Cuerdas", "Ukelele", "Violín", "Charango"],
    "Amplificadores": ["Amplificador Combo", "Cabezal", "Amplificador de Bajo"],
    "Accesorios": ["Correa", "Cable Plug", "Afinador", "Púas (pack)", "Pedal de Efectos"],
    "DJ": ["Controlador DJ", "Audífonos DJ", "Mezclador"],
}
MARCAS_BASE = [
    ("Fender", "Estados Unidos"), ("Gibson", "Estados Unidos"), ("Yamaha", "Japón"),
    ("Ibanez", "Japón"), ("Roland", "Japón"), ("Pearl", "Japón"), ("Marshall", "Reino Unido"),
    ("Behringer", "Alemania"), ("Cort", "Corea del Sur"), ("Music Pro", "Chile"),
]
SUCURSALES_BASE = [
    ("Casa Matriz", "Santiago", "Av. Providencia 1234", "+56 2 2345 6789"),
    ("Sucursal Valparaíso", "Valparaíso", "Calle Esmeralda 456", "+56 32 234 5678"),
    ("Sucursal Concepción", "Concepción", "Calle Barros Arana 789", "+56 41 234 5678"),
]


def asegurar_pks(modelo, objetos):
    """MySQL (a diferencia de MariaDB, PostgreSQL y SQLite) no devuelve los id al
    hacer bulk_create. En ese caso se leen los últimos id insertados, que
    corresponden a este lote porque la carga se hace dentro de una transacción."""
    if objetos and objetos[0].pk is None:
        ids = list(modelo.objects.order_by("-id").values_list("id", flat=True)[:len(objetos)])
        for objeto, pk in zip(objetos, reversed(ids)):
            objeto.pk = pk


class Command(BaseCommand):
    help = "Genera datos ficticios (Faker) para productos, clientes o ventas."

    def add_arguments(self, parser):
        parser.add_argument("modelo", choices=["productos", "clientes", "ventas"])
        parser.add_argument("cantidad", type=int, help="Cantidad de registros a crear")
        parser.add_argument("--lote", type=int, default=5000, help="Tamaño de lote (bulk_create)")
        parser.add_argument("--semilla", type=int, default=None, help="Semilla para repetir datos")

    def handle(self, *args, **opts):
        cantidad, lote = opts["cantidad"], opts["lote"]
        if cantidad < 1 or lote < 1:
            raise CommandError("cantidad y lote deben ser mayores que 0.")

        self.fake = Faker("es_CL")
        if opts["semilla"] is not None:
            Faker.seed(opts["semilla"])
            random.seed(opts["semilla"])

        # En SQLite se relaja la sincronización a disco solo durante la carga.
        # (no se puede cambiar dentro de una transacción, p. ej. en las pruebas).
        if connection.vendor == "sqlite" and not connection.in_atomic_block:
            connection.cursor().execute("PRAGMA synchronous = OFF")

        self._asegurar_base()
        inicio = time.perf_counter()
        creados = getattr(self, f"_{opts['modelo']}")(cantidad, lote)
        seg = time.perf_counter() - inicio
        self.stdout.write(self.style.SUCCESS(
            f"{creados:,} registro(s) de {opts['modelo']} creados en {seg:,.1f} s "
            f"({creados / max(seg, 0.001):,.0f} registros/s)."))

    # --- datos base (categorías, marcas y sucursales) -----------------------
    def _asegurar_base(self):
        for nombre in CATALOGO_BASE:
            Categoria.objects.get_or_create(nombre=nombre)
        for nombre, pais in MARCAS_BASE:
            Marca.objects.get_or_create(nombre=nombre, defaults={"pais_origen": pais})
        for nombre, ciudad, direccion, telefono in SUCURSALES_BASE:
            Sucursal.objects.get_or_create(
                nombre=nombre,
                defaults={"ciudad": ciudad, "direccion": direccion, "telefono": telefono},
            )

    # --- productos (+ inventario por sucursal) ------------------------------
    def _productos(self, cantidad, lote):
        categorias = {c.nombre: c for c in Categoria.objects.all()}
        marcas = list(Marca.objects.all())
        sucursales = list(Sucursal.objects.all())
        base = (Producto.objects.aggregate(m=Max("id"))["m"] or 0) + 1
        creados = 0
        while creados < cantidad:
            n = min(lote, cantidad - creados)
            productos = []
            for i in range(n):
                cat_nombre = random.choice(list(CATALOGO_BASE))
                marca = random.choice(marcas)
                tipo = random.choice(CATALOGO_BASE[cat_nombre])
                modelo = self.fake.bothify("??-###").upper()
                productos.append(Producto(
                    sku=f"MP-{base + creados + i:09d}",
                    nombre=f"{tipo} {marca.nombre} {modelo}",
                    descripcion=self.fake.sentence(nb_words=12),
                    precio=random.randrange(4990, 1_500_000, 10),
                    categoria=categorias[cat_nombre],
                    marca=marca,
                    destacado=random.random() < 0.02,
                    activo=random.random() < 0.95,
                ))
            with transaction.atomic():
                Producto.objects.bulk_create(productos)
                asegurar_pks(Producto, productos)
                inventarios = [
                    Inventario(producto_id=p.pk, sucursal=s, stock=random.randint(0, 40))
                    for p in productos for s in sucursales
                ]
                Inventario.objects.bulk_create(inventarios)
            creados += n
            self._progreso(creados, cantidad)
        return creados

    # --- clientes -----------------------------------------------------------
    def _clientes(self, cantidad, lote):
        base = (Cliente.objects.aggregate(m=Max("id"))["m"] or 0) + 1
        creados = 0
        while creados < cantidad:
            n = min(lote, cantidad - creados)
            clientes = []
            for i in range(n):
                idx = base + creados + i
                numero = 6_000_000 + idx  # RUT único derivado del id
                clientes.append(Cliente(
                    rut=f"{numero}-{digito_verificador(numero)}",
                    nombre=self.fake.name(),
                    email=f"cliente{idx}@{self.fake.free_email_domain()}",
                    telefono=self.fake.phone_number()[:20],
                ))
            with transaction.atomic():
                Cliente.objects.bulk_create(clientes)
            creados += n
            self._progreso(creados, cantidad)
        return creados

    # --- ventas (+ detalle) -------------------------------------------------
    def _ventas(self, cantidad, lote):
        cli_ids = list(Cliente.objects.values_list("id", flat=True))
        prod = list(Producto.objects.values_list("id", "precio"))
        suc_ids = list(Sucursal.objects.values_list("id", flat=True))
        if not cli_ids or not prod:
            raise CommandError(
                "Primero genera clientes y productos "
                "(poblar_datos clientes N / poblar_datos productos N).")
        ahora = timezone.now()
        estados = [e.value for e in Venta.Estado]
        creados = 0
        while creados < cantidad:
            n = min(lote, cantidad - creados)
            ventas, lineas = [], []
            for _ in range(n):
                items = [(pid, precio, random.randint(1, 3))
                         for pid, precio in random.sample(prod, k=min(len(prod), random.randint(1, 4)))]
                ventas.append(Venta(
                    cliente_id=random.choice(cli_ids),
                    sucursal_id=random.choice(suc_ids),
                    fecha=ahora - timedelta(minutes=random.randint(0, 60 * 24 * 365)),
                    estado=random.choice(estados),
                    total=sum(precio * cant for _, precio, cant in items),
                ))
                lineas.append(items)
            with transaction.atomic():
                Venta.objects.bulk_create(ventas)
                asegurar_pks(Venta, ventas)
                detalles = [
                    DetalleVenta(venta_id=v.pk, producto_id=pid, cantidad=cant, precio_unitario=precio)
                    for v, items in zip(ventas, lineas) for pid, precio, cant in items
                ]
                DetalleVenta.objects.bulk_create(detalles)
            creados += n
            self._progreso(creados, cantidad)
        return creados

    def _progreso(self, hecho, total):
        if hecho == total or hecho % (20 * 5000) == 0:
            self.stdout.write(f"  ... {hecho:,}/{total:,}")
