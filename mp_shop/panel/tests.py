"""
Pruebas de la Evaluación 3: autenticación, control de acceso, CRUD propio y
reportes ORM.   Ejecutar con:  python manage.py test panel
"""
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tienda.models import (
    Categoria, Cliente, DetalleVenta, Inventario, Marca, Producto, Sucursal, Venta,
)
from tienda.utils import digito_verificador

from .reportes import REPORTES

User = get_user_model()
CLAVE = "Clave-Segura-2026"


def rut(numero):
    return f"{numero}-{digito_verificador(numero)}"


def aware(anio, mes, dia, hora=12):
    return timezone.make_aware(datetime(anio, mes, dia, hora, 0))


class DatosBase(TestCase):
    """Crea un catálogo y ventas pequeñas con resultados fáciles de verificar."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin", password=CLAVE, is_staff=True)
        cls.operador = User.objects.create_user("operador", password=CLAVE)
        cls.super = User.objects.create_superuser("root", "r@x.cl", CLAVE)

        cls.guit = Categoria.objects.create(nombre="Guitarras")
        cls.bat = Categoria.objects.create(nombre="Baterías")
        cls.marca = Marca.objects.create(nombre="Fender")
        cls.suc = Sucursal.objects.create(nombre="Matriz", ciudad="Santiago", direccion="Av 1")
        cls.suc2 = Sucursal.objects.create(nombre="Valpo", ciudad="Valparaíso", direccion="Av 2")

        def prod(sku, nombre, precio, cat, stock):
            p = Producto.objects.create(sku=sku, nombre=nombre, precio=precio, categoria=cat, marca=cls.marca)
            Inventario.objects.create(producto=p, sucursal=cls.suc, stock=stock)
            return p
        cls.p1 = prod("P1", "Strat", 1000, cls.guit, 10)
        cls.p2 = prod("P2", "Tele", 2000, cls.guit, 3)       # stock bajo
        cls.p3 = prod("P3", "Batería Pro", 5000, cls.bat, 8)
        cls.p4 = prod("P4", "Nunca vendido", 300, cls.bat, 0)

        cls.c1 = Cliente.objects.create(rut=rut(11111111), nombre="Ana", email="a@x.cl")
        cls.c2 = Cliente.objects.create(rut=rut(22222222), nombre="Beto", email="b@x.cl")

        def venta(cliente, fecha, estado, lineas):
            v = Venta.objects.create(cliente=cliente, sucursal=cls.suc, fecha=fecha, estado=estado)
            for producto, cantidad in lineas:
                DetalleVenta.objects.create(venta=v, producto=producto, cantidad=cantidad)
            v.recalcular_total()
            return v
        hoy = timezone.now()
        # Ana: 2 x Strat (2.000) + 1 x Batería (5.000) = 7.000 (pagada, hace 5 días)
        cls.v1 = venta(cls.c1, hoy - timedelta(days=5), Venta.Estado.PAGADA, [(cls.p1, 2), (cls.p3, 1)])
        # Beto: 3 x Strat = 3.000 (entregada, hace 10 días)
        cls.v2 = venta(cls.c2, hoy - timedelta(days=10), Venta.Estado.ENTREGADA, [(cls.p1, 3)])
        # Beto: 1 x Tele = 2.000 (ANULADA: no debe contar en dinero ni unidades)
        cls.v3 = venta(cls.c2, hoy - timedelta(days=2), Venta.Estado.ANULADA, [(cls.p2, 1)])

    def entrar(self, usuario="admin"):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))


# =============================================================== AUTENTICACIÓN
class AutenticacionTests(DatosBase):
    URLS_PROTEGIDAS = [
        ("panel:inicio", []), ("panel:reportes", []), ("panel:reporte", [1]),
        ("panel:usuario_lista", []), ("panel:usuario_crear", []),
        ("panel:categoria_lista", []), ("panel:categoria_crear", []),
        ("panel:marca_lista", []), ("panel:sucursal_lista", []),
        ("panel:producto_lista", []), ("panel:producto_crear", []),
        ("panel:cliente_lista", []), ("panel:cliente_crear", []),
        ("panel:venta_lista", []), ("panel:venta_crear", []),
    ]

    def test_1_login_correcto(self):
        resp = self.client.post(reverse("panel:login"), {"username": "admin", "password": CLAVE})
        self.assertRedirects(resp, reverse("panel:inicio"))

    def test_login_incorrecto_no_entra(self):
        resp = self.client.post(reverse("panel:login"), {"username": "admin", "password": "mala"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "incorrectos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_usuario_inactivo_no_puede_entrar(self):
        User.objects.filter(username="operador").update(is_active=False)
        resp = self.client.post(reverse("panel:login"), {"username": "operador", "password": CLAVE})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(resp.status_code, 200)

    def test_4_anonimo_no_accede_a_vistas_protegidas(self):
        for nombre, args in self.URLS_PROTEGIDAS:
            url = reverse(nombre, args=args)
            resp = self.client.get(url)
            self.assertRedirects(resp, f"{reverse('panel:login')}?next={url}", msg_prefix=nombre)

    def test_rutas_con_id_protegidas_para_anonimos(self):
        for nombre in ("categoria", "marca", "sucursal", "producto", "cliente", "venta"):
            for accion in ("editar", "eliminar"):
                url = reverse(f"panel:{nombre}_{accion}", args=[1])
                self.assertEqual(self.client.get(url).status_code, 302, url)
        self.assertEqual(self.client.post(reverse("panel:usuario_estado", args=[self.admin.pk])).status_code, 302)

    def test_2_y_5_logout_cierra_sesion_y_pierde_acceso(self):
        self.entrar()
        self.assertEqual(self.client.get(reverse("panel:inicio")).status_code, 200)
        resp = self.client.post(reverse("panel:logout"))
        self.assertRedirects(resp, reverse("panel:login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        url = reverse("panel:inicio")
        self.assertRedirects(self.client.get(url), f"{reverse('panel:login')}?next={url}")

    def test_logout_no_funciona_con_get(self):
        self.entrar()
        self.assertEqual(self.client.get(reverse("panel:logout")).status_code, 405)
        self.assertEqual(self.client.get(reverse("panel:inicio")).status_code, 200)

    def test_6_la_sesion_identifica_al_usuario(self):
        self.entrar("operador")
        resp = self.client.get(reverse("panel:inicio"))
        self.assertEqual(resp.wsgi_request.user.username, "operador")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.operador.pk)

    def test_next_externo_no_permite_redireccion_abierta(self):
        resp = self.client.post(
            reverse("panel:login") + "?next=https://sitio-malo.example/",
            {"username": "admin", "password": CLAVE, "next": "https://sitio-malo.example/"})
        self.assertRedirects(resp, reverse("panel:inicio"), fetch_redirect_response=False)

    def test_login_redirige_si_ya_esta_autenticado(self):
        self.entrar()
        self.assertRedirects(self.client.get(reverse("panel:login")), reverse("panel:inicio"))

    def test_sin_token_csrf_el_login_se_rechaza(self):
        from django.test import Client
        cliente = Client(enforce_csrf_checks=True)
        resp = cliente.post(reverse("panel:login"), {"username": "admin", "password": CLAVE})
        self.assertEqual(resp.status_code, 403)


# ====================================================================== USUARIOS
class UsuariosTests(DatosBase):
    def test_operador_no_puede_gestionar_usuarios(self):
        self.entrar("operador")
        self.assertEqual(self.client.get(reverse("panel:usuario_lista")).status_code, 403)
        self.assertEqual(self.client.get(reverse("panel:usuario_crear")).status_code, 403)
        self.assertEqual(self.client.post(reverse("panel:usuario_estado", args=[self.admin.pk])).status_code, 403)

    def test_crear_consultar_modificar_y_desactivar_usuario(self):
        self.entrar()
        resp = self.client.post(reverse("panel:usuario_crear"), {
            "username": "nuevo", "first_name": "Nora", "last_name": "Paz", "email": "n@x.cl",
            "password1": "Otra-Clave-2026", "password2": "Otra-Clave-2026"})
        self.assertRedirects(resp, reverse("panel:usuario_lista"))
        nuevo = User.objects.get(username="nuevo")
        self.assertTrue(nuevo.check_password("Otra-Clave-2026"))   # la clave se guarda con hash
        self.assertNotEqual(nuevo.password, "Otra-Clave-2026")
        self.assertContains(self.client.get(reverse("panel:usuario_lista")), "nuevo")
        # modificar
        self.client.post(reverse("panel:usuario_editar", args=[nuevo.pk]), {
            "username": "nuevo", "first_name": "Nora", "last_name": "Soto", "email": "n@x.cl", "is_active": "on"})
        nuevo.refresh_from_db()
        self.assertEqual(nuevo.last_name, "Soto")
        # desactivar (no se elimina) y comprobar que ya no puede entrar
        self.client.post(reverse("panel:usuario_estado", args=[nuevo.pk]))
        nuevo.refresh_from_db()
        self.assertFalse(nuevo.is_active)
        self.assertTrue(User.objects.filter(pk=nuevo.pk).exists())
        self.client.logout()
        self.assertFalse(self.client.login(username="nuevo", password="Otra-Clave-2026"))

    def test_claves_distintas_o_debiles_se_rechazan(self):
        self.entrar()
        resp = self.client.post(reverse("panel:usuario_crear"), {
            "username": "x", "password1": "12345678", "password2": "12345678"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="x").exists())

    def test_no_puedes_desactivarte_a_ti_mismo(self):
        self.entrar()
        self.client.post(reverse("panel:usuario_estado", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_administrador_comun_no_toca_superusuarios(self):
        self.entrar("admin")
        self.assertEqual(self.client.get(reverse("panel:usuario_editar", args=[self.super.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("panel:usuario_estado", args=[self.super.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("panel:usuario_clave", args=[self.super.pk])).status_code, 403)

    def test_no_se_puede_quitar_el_rol_admin_a_uno_mismo(self):
        self.entrar()
        self.client.post(reverse("panel:usuario_editar", args=[self.admin.pk]), {
            "username": "admin", "first_name": "", "last_name": "", "email": ""})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff and self.admin.is_active)

    def test_cambiar_clave(self):
        self.entrar()
        self.client.post(reverse("panel:usuario_clave", args=[self.operador.pk]),
                         {"new_password1": "Clave-Nueva-9876", "new_password2": "Clave-Nueva-9876"})
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.check_password("Clave-Nueva-9876"))


# ========================================================================== CRUD
class CrudTests(DatosBase):
    def setUp(self):
        self.entrar("operador")      # un usuario normal con sesión puede usar el CRUD

    def test_categoria_crud_completo(self):
        self.client.post(reverse("panel:categoria_crear"), {"nombre": "Teclados", "descripcion": ""})
        cat = Categoria.objects.get(nombre="Teclados")
        self.assertContains(self.client.get(reverse("panel:categoria_lista"), {"q": "Tecl"}), "Teclados")
        self.client.post(reverse("panel:categoria_editar", args=[cat.pk]), {"nombre": "Teclados MIDI", "descripcion": "x"})
        cat.refresh_from_db()
        self.assertEqual(cat.nombre, "Teclados MIDI")
        self.client.post(reverse("panel:categoria_eliminar", args=[cat.pk]))
        self.assertFalse(Categoria.objects.filter(pk=cat.pk).exists())

    def test_categoria_con_productos_no_se_elimina(self):
        resp = self.client.post(reverse("panel:categoria_eliminar", args=[self.guit.pk]), follow=True)
        self.assertTrue(Categoria.objects.filter(pk=self.guit.pk).exists())
        self.assertContains(resp, "No se puede eliminar")

    def test_get_de_eliminar_pide_confirmacion_y_no_borra(self):
        resp = self.client.get(reverse("panel:categoria_eliminar", args=[self.bat.pk]))
        self.assertContains(resp, "¿Seguro")
        self.assertTrue(Categoria.objects.filter(pk=self.bat.pk).exists())

    def test_producto_crud_con_stock_por_sucursal(self):
        datos = {
            "sku": "nuevo-1", "nombre": "Bajo Test", "categoria": self.guit.pk, "marca": self.marca.pk,
            "precio": 99990, "descripcion": "", "imagen": "", "activo": "on",
            "inventarios-TOTAL_FORMS": "1", "inventarios-INITIAL_FORMS": "0",
            "inventarios-MIN_NUM_FORMS": "0", "inventarios-MAX_NUM_FORMS": "1000",
            "inventarios-0-sucursal": self.suc.pk, "inventarios-0-stock": "7",
        }
        resp = self.client.post(reverse("panel:producto_crear"), datos)
        self.assertRedirects(resp, reverse("panel:producto_lista"))
        p = Producto.objects.get(sku="NUEVO-1")             # el SKU se normaliza a mayúsculas
        self.assertEqual(p.stock_total, 7)
        # editar precio
        inv = p.inventarios.get()
        datos.update({"precio": 89990, "inventarios-INITIAL_FORMS": "1",
                      "inventarios-0-id": inv.pk, "inventarios-0-producto": p.pk, "inventarios-0-stock": "9"})
        self.client.post(reverse("panel:producto_editar", args=[p.pk]), datos)
        p.refresh_from_db()
        self.assertEqual((p.precio, p.stock_total), (89990, 9))
        # eliminar (el producto no tiene ventas)
        self.client.post(reverse("panel:producto_eliminar", args=[p.pk]))
        self.assertFalse(Producto.objects.filter(pk=p.pk).exists())
        self.assertFalse(Inventario.objects.filter(pk=inv.pk).exists())

    def test_producto_con_ventas_no_se_elimina(self):
        self.client.post(reverse("panel:producto_eliminar", args=[self.p1.pk]))
        self.assertTrue(Producto.objects.filter(pk=self.p1.pk).exists())

    def test_producto_validaciones(self):
        base = {"sku": "ZZ", "nombre": "ab", "categoria": self.guit.pk, "marca": self.marca.pk, "precio": 0,
                "inventarios-TOTAL_FORMS": "0", "inventarios-INITIAL_FORMS": "0",
                "inventarios-MIN_NUM_FORMS": "0", "inventarios-MAX_NUM_FORMS": "1000"}
        resp = self.client.post(reverse("panel:producto_crear"), base)
        self.assertContains(resp, "al menos 3 caracteres")
        self.assertFalse(Producto.objects.filter(sku="ZZ").exists())
        base.update({"nombre": "Nombre válido", "precio": 1000, "sku": "P1"})   # SKU repetido
        self.assertEqual(self.client.post(reverse("panel:producto_crear"), base).status_code, 200)

    def test_stock_duplicado_por_sucursal_se_rechaza(self):
        datos = {
            "sku": "DUP-1", "nombre": "Duplicado", "categoria": self.guit.pk, "marca": self.marca.pk, "precio": 1000,
            "inventarios-TOTAL_FORMS": "2", "inventarios-INITIAL_FORMS": "0",
            "inventarios-MIN_NUM_FORMS": "0", "inventarios-MAX_NUM_FORMS": "1000",
            "inventarios-0-sucursal": self.suc.pk, "inventarios-0-stock": "1",
            "inventarios-1-sucursal": self.suc.pk, "inventarios-1-stock": "2",
        }
        self.client.post(reverse("panel:producto_crear"), datos)
        self.assertFalse(Producto.objects.filter(sku="DUP-1").exists())

    def test_cliente_rut_se_valida_y_normaliza(self):
        url = reverse("panel:cliente_crear")
        malo = self.client.post(url, {"rut": "12.345.678-9", "nombre": "X", "email": "x@x.cl"})
        self.assertContains(malo, "dígito verificador")
        ok = self.client.post(url, {"rut": f"{digito_verificador(12345678) and '12.345.678-' + digito_verificador(12345678)}",
                                    "nombre": "Carla", "email": "c@x.cl"})
        self.assertRedirects(ok, reverse("panel:cliente_lista"))
        self.assertTrue(Cliente.objects.filter(rut=rut(12345678)).exists())
        # RUT repetido
        dup = self.client.post(url, {"rut": rut(12345678), "nombre": "Otra", "email": "o@x.cl"})
        self.assertEqual(dup.status_code, 200)

    def test_cliente_editar_y_eliminar(self):
        c = Cliente.objects.create(rut=rut(33333333), nombre="Temp", email="t@x.cl")
        self.client.post(reverse("panel:cliente_editar", args=[c.pk]), {"rut": c.rut, "nombre": "Temp2", "email": "t@x.cl"})
        c.refresh_from_db()
        self.assertEqual(c.nombre, "Temp2")
        self.client.post(reverse("panel:cliente_eliminar", args=[c.pk]))
        self.assertFalse(Cliente.objects.filter(pk=c.pk).exists())

    def test_cliente_con_ventas_no_se_elimina(self):
        self.client.post(reverse("panel:cliente_eliminar", args=[self.c1.pk]))
        self.assertTrue(Cliente.objects.filter(pk=self.c1.pk).exists())

    def _datos_venta(self, **extra):
        datos = {
            "rut_cliente": self.c1.rut, "sucursal": self.suc.pk, "fecha": "2026-10-01T10:30", "estado": "PAG",
            "detalles-TOTAL_FORMS": "2", "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "1", "detalles-MAX_NUM_FORMS": "1000",
            "detalles-0-sku": "p1", "detalles-0-cantidad": "2", "detalles-0-precio_unitario": "",
            "detalles-1-sku": "P3", "detalles-1-cantidad": "1", "detalles-1-precio_unitario": "4500",
        }
        datos.update(extra)
        return datos

    def test_venta_crud_y_total_recalculado(self):
        resp = self.client.post(reverse("panel:venta_crear"), self._datos_venta())
        self.assertRedirects(resp, reverse("panel:venta_lista"))
        v = Venta.objects.order_by("-id").first()
        # 2 x 1.000 (precio actual) + 1 x 4.500 (precio indicado a mano) = 6.500
        self.assertEqual(v.total, 6500)
        self.assertEqual(v.detalles.count(), 2)
        # editar: quitar una línea
        det = list(v.detalles.order_by("id"))
        datos = self._datos_venta(**{
            "detalles-INITIAL_FORMS": "2",
            "detalles-0-id": det[0].pk, "detalles-0-venta": v.pk, "detalles-0-sku": "P1", "detalles-0-cantidad": "2",
            "detalles-1-id": det[1].pk, "detalles-1-venta": v.pk, "detalles-1-sku": "P3", "detalles-1-cantidad": "1",
            "detalles-1-DELETE": "on",
        })
        self.client.post(reverse("panel:venta_editar", args=[v.pk]), datos)
        v.refresh_from_db()
        self.assertEqual((v.detalles.count(), v.total), (1, 2000))
        # eliminar la venta borra su detalle
        self.client.post(reverse("panel:venta_eliminar", args=[v.pk]))
        self.assertFalse(Venta.objects.filter(pk=v.pk).exists())
        self.assertFalse(DetalleVenta.objects.filter(venta_id=v.pk).exists())

    def test_venta_valida_cliente_producto_y_detalle_minimo(self):
        url = reverse("panel:venta_crear")
        antes = Venta.objects.count()
        self.client.post(url, self._datos_venta(rut_cliente=rut(99999999)))
        self.client.post(url, self._datos_venta(**{"detalles-0-sku": "NOEXISTE"}))
        self.client.post(url, self._datos_venta(**{"detalles-TOTAL_FORMS": "0"}))
        self.assertEqual(Venta.objects.count(), antes)

    def test_listas_cargan_y_paginan(self):
        for nombre in ("categoria", "marca", "sucursal", "producto", "cliente", "venta"):
            self.assertEqual(self.client.get(reverse(f"panel:{nombre}_lista")).status_code, 200, nombre)
        self.assertContains(self.client.get(reverse("panel:producto_lista"), {"q": "Strat"}), "Strat")
        self.assertEqual(self.client.get(reverse("panel:producto_lista"), {"page": "9999"}).status_code, 200)

    def test_editar_inexistente_da_404(self):
        self.assertEqual(self.client.get(reverse("panel:producto_editar", args=[999999])).status_code, 404)

    def test_html_se_escapa_en_las_listas(self):
        Categoria.objects.create(nombre="<script>alert(1)</script>")
        resp = self.client.get(reverse("panel:categoria_lista"))
        self.assertNotContains(resp, "<script>alert(1)</script>")
        self.assertContains(resp, "&lt;script&gt;")


# ================================================================== REPORTES ORM
class ReportesTests(DatosBase):
    def setUp(self):
        self.entrar("operador")

    def ejecutar(self, numero, **params):
        resp = self.client.get(reverse("panel:reporte", args=[numero]), params)
        self.assertEqual(resp.status_code, 200, f"reporte {numero}")
        return resp

    def filas(self, resp):
        return [list(f) for f in resp.context["pagina"].object_list]

    def test_los_20_reportes_existen_y_cargan(self):
        self.assertEqual(sorted(REPORTES), list(range(1, 21)))
        hoy = timezone.localdate()
        parametros = {
            2: {"categoria": self.guit.pk}, 3: {"precio_min": 100, "precio_max": 3000},
            6: {"rut": self.c1.rut}, 7: {"venta": self.v1.pk},
            8: {"desde": hoy - timedelta(days=30), "hasta": hoy}, 10: {"dia": hoy},
            18: {"anio": hoy.year}, 19: {"anio": hoy.year},
        }
        for n in range(1, 21):
            resp = self.ejecutar(n, **parametros.get(n, {}))
            self.assertTrue(resp.context.get("ejecutado"), f"reporte {n} no se ejecutó")
            self.assertContains(resp, "Ver la consulta ORM utilizada")

    def test_reporte_sin_parametros_muestra_formulario(self):
        resp = self.ejecutar(2)
        self.assertFalse(resp.context.get("ejecutado"))
        self.assertContains(resp, "Ejecutar reporte")

    def test_parametros_invalidos_se_rechazan_sin_error_500(self):
        self.assertContains(self.ejecutar(6, rut="123"), "no es válido")
        self.assertContains(self.ejecutar(3, precio_min=5000, precio_max=100), "no puede ser mayor")
        self.assertContains(self.ejecutar(8, desde="2026-12-31", hasta="2026-01-01"), "no puede ser posterior")
        self.assertContains(self.ejecutar(18, anio="abc"), "no es válido")
        self.assertEqual(self.client.get(reverse("panel:reporte", args=[21])).status_code, 404)

    def test_r01_r02_r03_r04_r05(self):
        self.assertEqual(len(self.filas(self.ejecutar(1))), 4)
        self.assertEqual({f[0] for f in self.filas(self.ejecutar(2, categoria=self.guit.pk))}, {"P1", "P2"})
        self.assertEqual({f[0] for f in self.filas(self.ejecutar(3, precio_min=1000, precio_max=2000))}, {"P1", "P2"})
        self.assertEqual([f[0] for f in self.filas(self.ejecutar(4))][:2], ["P3", "P2"])
        self.assertContains(self.ejecutar(5), "2 clientes")

    def test_r06_r07_compras_y_detalle(self):
        filas = self.filas(self.ejecutar(6, rut=self.c2.rut))
        self.assertEqual({f[0] for f in filas}, {self.v2.pk, self.v3.pk})
        det = self.filas(self.ejecutar(7, venta=self.v1.pk))
        self.assertEqual(sorted((f[0], f[2], f[4]) for f in det), [("P1", 2, 2000), ("P3", 1, 5000)])

    def test_r08_ventas_en_periodo_y_r10_monto_del_dia(self):
        hoy = timezone.localdate()
        resp = self.ejecutar(8, desde=hoy - timedelta(days=30), hasta=hoy)
        self.assertEqual(len(self.filas(resp)), 3)
        self.assertContains(resp, "Ventas en el período: 3")
        # el día de la venta v1: solo cuenta v1 (7.000)
        dia = timezone.localtime(self.v1.fecha).date()
        self.assertEqual(self.filas(self.ejecutar(10, dia=dia))[0][1], 7000)
        # el día de la venta anulada v3 el monto es 0
        dia_anulada = timezone.localtime(self.v3.fecha).date()
        self.assertEqual(self.filas(self.ejecutar(10, dia=dia_anulada))[0][1], 0)

    def test_r09_stock_bajo(self):
        skus = {f[0]: f[2] for f in self.filas(self.ejecutar(9))}
        self.assertEqual(skus, {"P2": 3, "P4": 0})

    def test_r11_r12_ranking_ignora_anuladas(self):
        top = self.filas(self.ejecutar(11))
        self.assertEqual(top[0][:3], ["P1", "Strat", 5])
        self.assertNotIn("P2", [f[0] for f in top])
        self.assertEqual(self.filas(self.ejecutar(12))[0][1], "Ana")  # Ana 1 compra válida; Beto 1 válida (+1 anulada)
        ranking = {f[1]: f[2] for f in self.filas(self.ejecutar(12))}
        self.assertEqual(ranking, {"Ana": 1, "Beto": 1})

    def test_r13_r14_r15_r16(self):
        totales = {f[1]: f[2] for f in self.filas(self.ejecutar(13))}
        self.assertEqual(totales, {"Ana": 7000, "Beto": 3000})
        self.assertEqual({f[0] for f in self.filas(self.ejecutar(14))}, {"P2", "P4"})
        self.assertEqual(self.filas(self.ejecutar(15))[0][1], 5000)           # (7.000 + 3.000) / 2
        cat = {f[0]: f[1] for f in self.filas(self.ejecutar(16))}
        self.assertEqual(cat, {"Guitarras": 5000, "Baterías": 5000})

    def test_r17_ultimo_mes(self):
        filas = {f[0]: f[2] for f in self.filas(self.ejecutar(17))}
        self.assertEqual(filas, {"P1": 5, "P3": 1})

    def test_r18_r19_r20_analisis(self):
        anio = timezone.localdate().year
        top = self.filas(self.ejecutar(18, anio=anio))
        if top:  # puede caer en el año anterior si la prueba corre a inicios de enero
            self.assertEqual(top[0][1:], ["Ana", 7000])
        meses = self.filas(self.ejecutar(19, anio=anio))
        self.assertEqual(len(meses), 12)
        self.assertLessEqual(sum(f[1] for f in meses), 10000)
        ingresos = self.filas(self.ejecutar(20))
        # P1 (5 x 1.000) y P3 (1 x 5.000) empatan en 5.000: el desempate es por SKU.
        self.assertEqual([f[:3] for f in ingresos[:2]],
                         [["P1", "Strat", 5000], ["P3", "Batería Pro", 5000]])


class ReporteSinLoginTests(DatosBase):
    def test_reportes_exigen_login(self):
        for n in (1, 10, 20):
            url = reverse("panel:reporte", args=[n])
            self.assertRedirects(self.client.get(url), f"{reverse('panel:login')}?next={url}")
