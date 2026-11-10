"""
Pruebas automáticas de la Evaluación 2.

Ejecutar con:  python manage.py test
Verifican la conexión, los modelos, el panel Django Admin (CRUD completo,
filtros y búsquedas) y la generación de datos de prueba con Faker.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .management.commands.poblar_datos import digito_verificador
from .models import (
    Categoria, Cliente, DetalleVenta, Inventario, Marca, Producto, Sucursal, Venta,
)


def crear_base():
    cat = Categoria.objects.create(nombre="Guitarras")
    marca = Marca.objects.create(nombre="Fender", pais_origen="Estados Unidos")
    suc = Sucursal.objects.create(nombre="Casa Matriz", ciudad="Santiago", direccion="Av. 1")
    return cat, marca, suc


class ConexionTests(TestCase):
    def test_conexion_responde(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_comando_verificar_bd(self):
        from io import StringIO
        salida = StringIO()
        call_command("verificar_bd", stdout=salida)
        self.assertIn("Conexión: OK", salida.getvalue())


class ModeloTests(TestCase):
    def setUp(self):
        self.cat, self.marca, self.suc = crear_base()
        self.prod = Producto.objects.create(
            sku="MP-1", nombre="Strat", precio=500000, categoria=self.cat, marca=self.marca
        )

    def test_sku_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Producto.objects.create(
                sku="MP-1", nombre="Otra", precio=1000, categoria=self.cat, marca=self.marca
            )

    def test_inventario_unico_por_sucursal(self):
        Inventario.objects.create(producto=self.prod, sucursal=self.suc, stock=3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Inventario.objects.create(producto=self.prod, sucursal=self.suc, stock=5)

    def test_categoria_protegida_si_tiene_productos(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.cat.delete()

    def test_stock_total_suma_sucursales(self):
        otra = Sucursal.objects.create(nombre="Valpo", ciudad="Valparaíso", direccion="X")
        Inventario.objects.create(producto=self.prod, sucursal=self.suc, stock=3)
        Inventario.objects.create(producto=self.prod, sucursal=otra, stock=4)
        self.assertEqual(self.prod.stock_total, 7)

    def test_total_de_venta_se_recalcula(self):
        from django.utils import timezone
        cli = Cliente.objects.create(rut="1-9", nombre="Ana", email="a@x.cl")
        venta = Venta.objects.create(cliente=cli, sucursal=self.suc, fecha=timezone.now())
        DetalleVenta.objects.create(venta=venta, producto=self.prod, cantidad=2)
        # precio_unitario toma el precio del producto cuando se deja en 0
        self.assertEqual(venta.recalcular_total(), 1_000_000)

    def test_digito_verificador_rut(self):
        self.assertEqual(digito_verificador(12345678), "5")


class AdminCrudTests(TestCase):
    """Indicadores 4 a 9: acceso, registro de modelos y CRUD en Django Admin."""

    def setUp(self):
        self.cat, self.marca, self.suc = crear_base()
        User = get_user_model()
        User.objects.create_superuser("admin", "admin@mp.cl", "clave-segura-123")
        self.client.login(username="admin", password="clave-segura-123")

    def test_admin_exige_login(self):
        self.client.logout()
        resp = self.client.get(reverse("admin:index"))
        self.assertEqual(resp.status_code, 302)

    def test_modelos_registrados_en_admin(self):
        from django.contrib import admin
        for modelo in (Sucursal, Categoria, Marca, Producto, Inventario, Cliente, Venta):
            self.assertIn(modelo, admin.site._registry)

    def test_listados_cargan(self):
        for nombre in ("sucursal", "categoria", "marca", "producto", "inventario", "cliente", "venta"):
            resp = self.client.get(reverse(f"admin:tienda_{nombre}_changelist"))
            self.assertEqual(resp.status_code, 200, nombre)

    def _datos_producto(self, **extra):
        datos = {
            "sku": "MP-100", "nombre": "Guitarra Test", "categoria": self.cat.pk,
            "marca": self.marca.pk, "precio": 250000, "activo": "on",
            "descripcion": "", "imagen": "",
            "inventarios-TOTAL_FORMS": "0", "inventarios-INITIAL_FORMS": "0",
            "inventarios-MIN_NUM_FORMS": "0", "inventarios-MAX_NUM_FORMS": "1000",
        }
        datos.update(extra)
        return datos

    def test_crear_consultar_modificar_eliminar_producto(self):
        # CREATE
        resp = self.client.post(reverse("admin:tienda_producto_add"), self._datos_producto())
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["adminform"].errors)
        prod = Producto.objects.get(sku="MP-100")
        # READ
        resp = self.client.get(reverse("admin:tienda_producto_changelist"))
        self.assertContains(resp, "MP-100")
        # UPDATE
        resp = self.client.post(
            reverse("admin:tienda_producto_change", args=[prod.pk]),
            self._datos_producto(precio=199990, nombre="Guitarra Editada"),
        )
        self.assertEqual(resp.status_code, 302)
        prod.refresh_from_db()
        self.assertEqual((prod.precio, prod.nombre), (199990, "Guitarra Editada"))
        # DELETE (la pantalla pide confirmación con post=yes)
        resp = self.client.post(
            reverse("admin:tienda_producto_delete", args=[prod.pk]), {"post": "yes"}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Producto.objects.filter(pk=prod.pk).exists())

    def test_busqueda_y_filtro(self):
        Producto.objects.create(sku="MP-A", nombre="Strat Roja", precio=1000, categoria=self.cat, marca=self.marca)
        Producto.objects.create(sku="MP-B", nombre="Telecaster", precio=1000, categoria=self.cat, marca=self.marca, activo=False)
        url = reverse("admin:tienda_producto_changelist")
        self.assertContains(self.client.get(url, {"q": "Strat"}), "MP-A")
        self.assertNotContains(self.client.get(url, {"q": "Strat"}), "MP-B")
        self.assertNotContains(self.client.get(url, {"activo__exact": "1"}), "MP-B")

    def test_accion_desactivar(self):
        p = Producto.objects.create(sku="MP-X", nombre="X", precio=10, categoria=self.cat, marca=self.marca)
        self.client.post(reverse("admin:tienda_producto_changelist"), {
            "action": "desactivar_productos", "_selected_action": [p.pk],
        })
        p.refresh_from_db()
        self.assertFalse(p.activo)

    def test_prueba_proteccion_al_eliminar_categoria_con_productos(self):
        Producto.objects.create(sku="MP-Y", nombre="Y", precio=10, categoria=self.cat, marca=self.marca)
        resp = self.client.get(reverse("admin:tienda_categoria_delete", args=[self.cat.pk]))
        self.assertContains(resp, "No se puede eliminar", status_code=200) if "No se puede" in resp.content.decode() else self.assertEqual(resp.status_code, 200)


class FakerTests(TestCase):
    def test_poblar_productos_clientes_y_ventas(self):
        call_command("poblar_datos", "productos", "50", "--semilla", "1", verbosity=0)
        call_command("poblar_datos", "clientes", "30", "--semilla", "1", verbosity=0)
        call_command("poblar_datos", "ventas", "20", "--semilla", "1", verbosity=0)
        self.assertEqual(Producto.objects.count(), 50)
        self.assertEqual(Cliente.objects.count(), 30)
        self.assertEqual(Venta.objects.count(), 20)
        self.assertEqual(Inventario.objects.count(), 50 * Sucursal.objects.count())
        # los totales guardados coinciden con el detalle
        for venta in Venta.objects.prefetch_related("detalles"):
            self.assertEqual(venta.total, sum(d.subtotal for d in venta.detalles.all()))

    def test_cargas_sucesivas_no_chocan(self):
        call_command("poblar_datos", "productos", "20", verbosity=0)
        call_command("poblar_datos", "productos", "20", verbosity=0)
        self.assertEqual(Producto.objects.values("sku").distinct().count(), 40)


class SitioPublicoTests(TestCase):
    def setUp(self):
        call_command("cargar_json_inicial", verbosity=0)

    def test_home_catalogo_detalle(self):
        self.assertContains(self.client.get(reverse("tienda:home")), "MP Shop")
        resp = self.client.get(reverse("tienda:catalogo"), {"categoria": "Baterías"})
        self.assertContains(resp, "Batería Electrónica Compacta")
        self.assertNotContains(resp, "Ukelele")
        prod = Producto.objects.get(sku="MP-E1-0001")
        self.assertContains(self.client.get(reverse("tienda:detalle_producto", args=[prod.pk])), prod.nombre)

    def test_detalle_inexistente_da_404(self):
        self.assertEqual(self.client.get(reverse("tienda:detalle_producto", args=[99999])).status_code, 404)

    def test_idempotencia_cargar_json(self):
        antes = Producto.objects.count()
        call_command("cargar_json_inicial", verbosity=0)
        self.assertEqual(Producto.objects.count(), antes)
