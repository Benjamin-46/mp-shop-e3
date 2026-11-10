"""
Configuración de Django Admin para MP Shop (Evaluación 2, criterio 2.1.2).

Cada ModelAdmin define cómo se ve y se administra un modelo: columnas,
filtros, búsquedas, edición en línea y acciones masivas.
"""
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Categoria, Cliente, DetalleVenta, Inventario, Marca, Producto, Sucursal, Venta,
)

admin.site.site_header = "Music Pro - Administración MP Shop"
admin.site.site_title = "MP Shop Admin"
admin.site.index_title = "Sucursal y Punto de Venta"


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ciudad", "direccion", "telefono", "activa")
    list_filter = ("activa", "ciudad")
    search_fields = ("nombre", "ciudad", "direccion")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion")
    search_fields = ("nombre",)


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "pais_origen")
    list_filter = ("pais_origen",)
    search_fields = ("nombre",)


class InventarioInline(admin.TabularInline):
    """Permite editar el stock por sucursal dentro de la ficha del producto."""
    model = Inventario
    extra = 1


@admin.action(description="Marcar productos seleccionados como activos")
def activar_productos(modeladmin, request, queryset):
    cantidad = queryset.update(activo=True)
    modeladmin.message_user(request, f"{cantidad} producto(s) activado(s).", messages.SUCCESS)


@admin.action(description="Marcar productos seleccionados como inactivos")
def desactivar_productos(modeladmin, request, queryset):
    cantidad = queryset.update(activo=False)
    modeladmin.message_user(request, f"{cantidad} producto(s) desactivado(s).", messages.WARNING)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "sku", "nombre", "categoria", "marca", "precio_clp", "stock_total_col",
        "destacado", "activo",
    )
    list_display_links = ("sku", "nombre")
    list_editable = ("destacado", "activo")
    list_filter = ("categoria", "marca", "activo", "destacado")
    search_fields = ("sku", "nombre", "marca__nombre")
    list_select_related = ("categoria", "marca")
    list_per_page = 25
    # Con cientos de miles de filas, contar el total en cada página es lento.
    show_full_result_count = False
    readonly_fields = ("creado",)
    inlines = [InventarioInline]
    actions = [activar_productos, desactivar_productos]
    fieldsets = (
        ("Identificación", {"fields": ("sku", "nombre", "categoria", "marca")}),
        ("Venta", {"fields": ("precio", "activo", "destacado")}),
        ("Contenido", {"fields": ("descripcion", "imagen"), "classes": ("collapse",)}),
        ("Auditoría", {"fields": ("creado",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        # prefetch evita una consulta extra por fila al calcular el stock.
        return super().get_queryset(request).prefetch_related("inventarios")

    @admin.display(description="Precio", ordering="precio")
    def precio_clp(self, obj):
        return f"${obj.precio:,}".replace(",", ".")

    @admin.display(description="Stock total")
    def stock_total_col(self, obj):
        total = obj.stock_total
        color = "red" if total == 0 else "green"
        return format_html('<b style="color:{}">{}</b>', color, total)


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ("producto", "sucursal", "stock")
    list_filter = ("sucursal",)
    search_fields = ("producto__sku", "producto__nombre")
    autocomplete_fields = ("producto",)
    list_select_related = ("producto", "sucursal")
    show_full_result_count = False


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("rut", "nombre", "email", "telefono", "creado")
    search_fields = ("rut", "nombre", "email")
    list_filter = ("creado",)
    date_hierarchy = "creado"
    readonly_fields = ("creado",)
    show_full_result_count = False


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 1
    # El buscador evita cargar un <select> con todos los productos.
    autocomplete_fields = ("producto",)


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "cliente", "sucursal", "estado", "total_clp")
    list_filter = ("estado", "sucursal", "fecha")
    search_fields = ("id", "cliente__nombre", "cliente__rut")
    date_hierarchy = "fecha"
    list_select_related = ("cliente", "sucursal")
    autocomplete_fields = ("cliente",)
    readonly_fields = ("total",)
    inlines = [DetalleVentaInline]
    show_full_result_count = False
    list_per_page = 25

    @admin.display(description="Total", ordering="total")
    def total_clp(self, obj):
        return f"${obj.total:,}".replace(",", ".")

    def save_related(self, request, form, formsets, change):
        # Primero se guardan los detalles (inlines) y luego se recalcula el total.
        super().save_related(request, form, formsets, change)
        form.instance.recalcular_total()
