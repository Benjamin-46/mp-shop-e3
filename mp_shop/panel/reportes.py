"""
Reportes con Django ORM (Evaluación 3, Parte 2): proyecto TIENDA.

Cada función r01..r20 responde una pregunta del informe del docente usando
SOLO el ORM (sin SQL escrito a mano). Devuelven:
    columnas : lista de (encabezado, tipo)  -> tipo: txt | num | clp | fecha
    consulta : QuerySet (o lista) con las filas
    resumen  : texto opcional con la respuesta directa

Criterios que se aplican y se pueden explicar en la defensa:
  * En reportes de DINERO o UNIDADES VENDIDAS no cuentan las ventas ANULADAS.
  * El monto de una línea es cantidad x precio_unitario (el precio aplicado al
    momento de la venta, no el precio actual del producto).
  * Para días, rangos y meses se usan rangos de fecha calculados en Python.
    Así no se depende de funciones de zona horaria de MySQL.
"""
from datetime import date, datetime, time, timedelta

from django.db.models import (
    Count, Exists, ExpressionWrapper, F, IntegerField, OuterRef, Q, Sum,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from tienda.models import Categoria, Cliente, DetalleVenta, Producto, Venta

ANULADA = Venta.Estado.ANULADA

# monto de una línea de venta = cantidad x precio aplicado
MONTO = ExpressionWrapper(F("cantidad") * F("precio_unitario"), output_field=IntegerField())


def _detalles_validos():
    """Líneas de venta que pertenecen a ventas no anuladas."""
    return DetalleVenta.objects.exclude(venta__estado=ANULADA)


def _inicio_dia(dia: date):
    return timezone.make_aware(datetime.combine(dia, time.min))


def _rango(desde: date, hasta: date):
    """[inicio, fin) que cubre desde 00:00 de 'desde' hasta el fin del día 'hasta'."""
    return _inicio_dia(desde), _inicio_dia(hasta + timedelta(days=1))


def _rango_anio(anio: int):
    return _inicio_dia(date(anio, 1, 1)), _inicio_dia(date(anio + 1, 1, 1))


# ---------------------------------------------------------------- BÁSICOS
def r01(p):
    """1. Todos los productos disponibles en la tienda."""
    consulta = (Producto.objects.filter(activo=True)
                .order_by("nombre", "id")
                .values_list("sku", "nombre", "categoria__nombre", "precio"))
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Categoría", "txt"), ("Precio", "clp")],
                consulta=consulta)


def r02(p):
    """2. Productos de una categoría seleccionada."""
    consulta = (Producto.objects.filter(categoria_id=p["categoria"])
                .order_by("nombre", "id")
                .values_list("sku", "nombre", "marca__nombre", "precio"))
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Marca", "txt"), ("Precio", "clp")],
                consulta=consulta)


def r03(p):
    """3. Productos dentro de un rango de precios."""
    consulta = (Producto.objects.filter(precio__range=(p["precio_min"], p["precio_max"]))
                .order_by("precio", "id")
                .values_list("sku", "nombre", "categoria__nombre", "precio"))
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Categoría", "txt"), ("Precio", "clp")],
                consulta=consulta)


def r04(p):
    """4. Los 10 productos más caros."""
    consulta = (Producto.objects.order_by("-precio", "id")
                .values_list("sku", "nombre", "categoria__nombre", "precio")[:10])
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Categoría", "txt"), ("Precio", "clp")],
                consulta=consulta)


def r05(p):
    """5. Cantidad de clientes registrados."""
    total = Cliente.objects.count()
    return dict(columnas=[("Dato", "txt"), ("Valor", "num")],
                consulta=[("Clientes registrados", total)],
                resumen=f"Hay {total:,} clientes registrados.".replace(",", "."))


# ---------------------------------------------------------- INTERMEDIOS
def r06(p):
    """6. Compras realizadas por un cliente (por RUT)."""
    consulta = (Venta.objects.filter(cliente__rut=p["rut"])
                .annotate(monto=Sum(F("detalles__cantidad") * F("detalles__precio_unitario"),
                                    output_field=IntegerField()))
                .order_by("-fecha")
                .values_list("id", "fecha", "sucursal__nombre", "estado", "monto"))
    return dict(columnas=[("N° venta", "num"), ("Fecha", "fecha"), ("Sucursal", "txt"),
                          ("Estado", "estado"), ("Monto", "clp")], consulta=consulta)


def r07(p):
    """7. Productos comprados en una venta determinada."""
    consulta = (DetalleVenta.objects.filter(venta_id=p["venta"])
                .annotate(subtotal=MONTO)
                .order_by("id")
                .values_list("producto__sku", "producto__nombre", "cantidad", "precio_unitario", "subtotal"))
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Cantidad", "num"),
                          ("Precio aplicado", "clp"), ("Subtotal", "clp")], consulta=consulta)


def r08(p):
    """8. Ventas realizadas durante un período."""
    inicio, fin = _rango(p["desde"], p["hasta"])
    ventas = Venta.objects.filter(fecha__gte=inicio, fecha__lt=fin)
    consulta = (ventas.select_related("cliente").order_by("fecha")
                .values_list("id", "fecha", "cliente__nombre", "estado", "total"))
    return dict(columnas=[("N° venta", "num"), ("Fecha", "fecha"), ("Cliente", "txt"),
                          ("Estado", "estado"), ("Total", "clp")],
                consulta=consulta,
                resumen=f"Ventas en el período: {ventas.count():,}".replace(",", "."))


def r09(p):
    """9. Productos con menos de cinco unidades disponibles (stock sumado de todas las sucursales)."""
    consulta = (Producto.objects.filter(activo=True)
                .annotate(stock=Coalesce(Sum("inventarios__stock"), 0))
                .filter(stock__lt=5)
                .order_by("stock", "id")
                .values_list("sku", "nombre", "stock"))
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Stock total", "num")], consulta=consulta)


def r10(p):
    """10. Monto total vendido en un día seleccionado."""
    inicio, fin = _rango(p["dia"], p["dia"])
    detalles = _detalles_validos().filter(venta__fecha__gte=inicio, venta__fecha__lt=fin)
    datos = detalles.aggregate(total=Coalesce(Sum(MONTO), 0), ventas=Count("venta", distinct=True))
    return dict(columnas=[("Dato", "txt"), ("Valor", "clp")],
                consulta=[("Monto total vendido", datos["total"]), ],
                resumen=f"Se registraron {datos['ventas']} venta(s) no anuladas ese día.")


def r11(p):
    """11. Los cinco productos más vendidos según unidades."""
    consulta = (_detalles_validos()
                .values("producto__sku", "producto__nombre")
                .annotate(unidades=Sum("cantidad"))
                .order_by("-unidades", "producto__sku")
                .values_list("producto__sku", "producto__nombre", "unidades")[:5])
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Unidades vendidas", "num")],
                consulta=consulta)


def r12(p):
    """12. Los cinco clientes con más compras."""
    consulta = (Cliente.objects
                .annotate(compras=Count("ventas", filter=~Q(ventas__estado=ANULADA)))
                .order_by("-compras", "id")
                .values_list("rut", "nombre", "compras")[:5])
    return dict(columnas=[("RUT", "txt"), ("Cliente", "txt"), ("Compras", "num")], consulta=consulta)


# ----------------------------------------------------------- AVANZADOS
def r13(p):
    """13. Monto total comprado por cada cliente."""
    consulta = (_detalles_validos()
                .values("venta__cliente__rut", "venta__cliente__nombre")
                .annotate(total=Sum(MONTO))
                .order_by("-total", "venta__cliente__rut")
                .values_list("venta__cliente__rut", "venta__cliente__nombre", "total"))
    return dict(columnas=[("RUT", "txt"), ("Cliente", "txt"), ("Monto total", "clp")], consulta=consulta)


def r14(p):
    """14. Productos que nunca han sido vendidos (en ventas no anuladas)."""
    vendidos = _detalles_validos().filter(producto=OuterRef("pk"))
    consulta = (Producto.objects.annotate(vendido=Exists(vendidos)).filter(vendido=False)
                .order_by("nombre", "id")
                .values_list("sku", "nombre", "categoria__nombre", "precio"))
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Categoría", "txt"), ("Precio", "clp")],
                consulta=consulta)


def r15(p):
    """15. Promedio de dinero gastado por venta."""
    datos = _detalles_validos().aggregate(total=Sum(MONTO), ventas=Count("venta", distinct=True))
    promedio = round(datos["total"] / datos["ventas"]) if datos["ventas"] else 0
    return dict(columnas=[("Dato", "txt"), ("Valor", "clp")],
                consulta=[("Promedio por venta", promedio)],
                resumen=f"Calculado sobre {datos['ventas']} venta(s) no anuladas.")


def r16(p):
    """16. Categoría que genera el mayor monto de ventas."""
    consulta = list(_detalles_validos()
                    .values("producto__categoria__nombre")
                    .annotate(total=Sum(MONTO))
                    .order_by("-total", "producto__categoria__nombre")
                    .values_list("producto__categoria__nombre", "total"))
    resumen = f"La categoría con mayor monto es «{consulta[0][0]}»." if consulta else "Sin ventas."
    return dict(columnas=[("Categoría", "txt"), ("Monto vendido", "clp")], consulta=consulta, resumen=resumen)


def r17(p):
    """17. Unidades vendidas de cada producto durante el último mes (30 días)."""
    desde = timezone.now() - timedelta(days=30)
    consulta = (_detalles_validos().filter(venta__fecha__gte=desde)
                .values("producto__sku", "producto__nombre")
                .annotate(unidades=Sum("cantidad"))
                .order_by("-unidades", "producto__sku")
                .values_list("producto__sku", "producto__nombre", "unidades"))
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Unidades", "num")], consulta=consulta)


# ------------------------------------------------------------ ANÁLISIS
def r18(p):
    """18. Cliente que ha gastado más dinero durante el año seleccionado."""
    inicio, fin = _rango_anio(p["anio"])
    consulta = (_detalles_validos().filter(venta__fecha__gte=inicio, venta__fecha__lt=fin)
                .values("venta__cliente__rut", "venta__cliente__nombre")
                .annotate(total=Sum(MONTO))
                .order_by("-total", "venta__cliente__rut")
                .values_list("venta__cliente__rut", "venta__cliente__nombre", "total")[:1])
    return dict(columnas=[("RUT", "txt"), ("Cliente", "txt"), ("Monto gastado", "clp")], consulta=consulta)


def r19(p):
    """19. Distribución de los montos de ventas por mes durante el año seleccionado."""
    anio = p["anio"]
    # Una sola consulta con 12 sumas condicionales (una por mes).
    sumas = {}
    for mes in range(1, 13):
        ini = _inicio_dia(date(anio, mes, 1))
        fin = _inicio_dia(date(anio + (mes == 12), mes % 12 + 1, 1))
        sumas[f"m{mes:02d}"] = Coalesce(
            Sum(MONTO, filter=Q(venta__fecha__gte=ini, venta__fecha__lt=fin)), 0)
    datos = _detalles_validos().aggregate(**sumas)
    nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
               "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    filas = [(nombres[m - 1], datos[f"m{m:02d}"]) for m in range(1, 13)]
    return dict(columnas=[("Mes", "txt"), (f"Monto vendido {anio}", "clp")], consulta=filas,
                resumen=f"Total del año: ${sum(f[1] for f in filas):,}".replace(",", "."))


def r20(p):
    """20. Los 10 productos que generan mayores ingresos."""
    consulta = (_detalles_validos()
                .values("producto__sku", "producto__nombre")
                .annotate(ingresos=Sum(MONTO))
                .order_by("-ingresos", "producto__sku")
                .values_list("producto__sku", "producto__nombre", "ingresos")[:10])
    return dict(columnas=[("SKU", "txt"), ("Producto", "txt"), ("Ingresos", "clp")], consulta=consulta)


# ============================================================ REGISTRO
CATEGORIA = dict(nombre="categoria", etiqueta="Categoría", tipo="categoria")
RUT = dict(nombre="rut", etiqueta="RUT del cliente", tipo="rut")
VENTA = dict(nombre="venta", etiqueta="N° de venta", tipo="entero")
PERIODO = [dict(nombre="desde", etiqueta="Desde", tipo="fecha"), dict(nombre="hasta", etiqueta="Hasta", tipo="fecha")]
DIA = dict(nombre="dia", etiqueta="Día", tipo="fecha")
ANIO = dict(nombre="anio", etiqueta="Año", tipo="anio")
PRECIOS = [dict(nombre="precio_min", etiqueta="Precio mínimo", tipo="entero"),
           dict(nombre="precio_max", etiqueta="Precio máximo", tipo="entero")]

_DEFINICION = [
    (1, "Básico", "¿Cuáles son todos los productos disponibles en la tienda?", r01, []),
    (2, "Básico", "¿Qué productos pertenecen a una categoría seleccionada?", r02, [CATEGORIA]),
    (3, "Básico", "¿Qué productos se encuentran dentro de un rango de precios?", r03, PRECIOS),
    (4, "Básico", "¿Cuáles son los 10 productos más caros de la tienda?", r04, []),
    (5, "Básico", "¿Cuántos clientes están registrados en el sistema?", r05, []),
    (6, "Intermedio", "¿Cuáles son las compras realizadas por un cliente específico?", r06, [RUT]),
    (7, "Intermedio", "¿Qué productos adquirió un cliente en una venta determinada?", r07, [VENTA]),
    (8, "Intermedio", "¿Cuántas ventas se realizaron durante un período seleccionado?", r08, PERIODO),
    (9, "Intermedio", "¿Cuáles son los productos que tienen menos de cinco unidades disponibles?", r09, []),
    (10, "Intermedio", "¿Cuál es el monto total vendido durante un día seleccionado?", r10, [DIA]),
    (11, "Intermedio", "¿Cuáles son los cinco productos más vendidos según cantidad de unidades?", r11, []),
    (12, "Intermedio", "¿Cuáles son los cinco clientes que han realizado más compras?", r12, []),
    (13, "Avanzado", "¿Cuál es el monto total comprado por cada cliente?", r13, []),
    (14, "Avanzado", "¿Qué productos nunca han sido vendidos?", r14, []),
    (15, "Avanzado", "¿Cuál es el promedio de dinero gastado por venta?", r15, []),
    (16, "Avanzado", "¿Qué categoría genera el mayor monto de ventas?", r16, []),
    (17, "Avanzado", "¿Cuántas unidades se han vendido de cada producto durante el último mes?", r17, []),
    (18, "Análisis", "¿Qué cliente ha gastado más dinero durante el año?", r18, [ANIO]),
    (19, "Análisis", "¿Cómo se distribuyen los montos de ventas por mes durante el año seleccionado?", r19, [ANIO]),
    (20, "Análisis", "¿Cuáles son los 10 productos que generan mayores ingresos para la tienda?", r20, []),
]

REPORTES = {
    n: dict(numero=n, nivel=nivel, pregunta=pregunta, funcion=f, parametros=params)
    for n, nivel, pregunta, f, params in _DEFINICION
}
