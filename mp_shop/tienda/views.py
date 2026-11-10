from django.core.paginator import Paginator
from django.db.models import OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404, render

from .models import Categoria, Inventario, Producto


def _con_stock(queryset):
    """Agrega 'stock_total' a cada producto con una subconsulta por fila."""
    stock = (
        Inventario.objects.filter(producto=OuterRef("pk"))
        .values("producto")
        .annotate(total=Sum("stock"))
        .values("total")
    )
    return queryset.annotate(stock_total_db=Subquery(stock))


def home(request):
    """Portada: productos destacados y total de productos publicados."""
    activos = Producto.objects.filter(activo=True)
    contexto = {
        "titulo_pagina": "Inicio",
        "total_productos": activos.count(),
        # Se anota el stock antes de cortar el resultado con [:6].
        "destacados": _con_stock(
            activos.filter(destacado=True).select_related("categoria", "marca")
        ).order_by("-id")[:6],
    }
    return render(request, "tienda/home.html", contexto)


def catalogo(request):
    """
    Catálogo paginado. Filtra por categoría (?categoria=) y busca por texto
    (?q=), replicando la bifurcación del diagrama de flujo de la Evaluación 1.
    """
    categoria_seleccionada = request.GET.get("categoria", "")
    busqueda = request.GET.get("q", "").strip()

    productos = Producto.objects.filter(activo=True).select_related("categoria", "marca")
    if categoria_seleccionada:
        productos = productos.filter(categoria__nombre=categoria_seleccionada)
    if busqueda:
        productos = productos.filter(Q(nombre__icontains=busqueda) | Q(sku__icontains=busqueda))

    pagina = Paginator(_con_stock(productos.order_by("nombre", "id")), 12).get_page(
        request.GET.get("page")
    )
    contexto = {
        "titulo_pagina": "Catálogo",
        "pagina": pagina,
        "categorias": Categoria.objects.values_list("nombre", flat=True),
        "categoria_seleccionada": categoria_seleccionada,
        "busqueda": busqueda,
    }
    return render(request, "tienda/catalogo.html", contexto)


def detalle_producto(request, producto_id):
    """Detalle de un producto con su stock en cada sucursal."""
    producto = get_object_or_404(
        Producto.objects.select_related("categoria", "marca"), pk=producto_id, activo=True
    )
    inventarios = producto.inventarios.select_related("sucursal").order_by("sucursal__nombre")
    stock_total = sum(i.stock for i in inventarios)
    contexto = {
        "titulo_pagina": producto.nombre,
        "producto": producto,
        "inventarios": inventarios,
        "stock_total": stock_total,
        "sin_stock": stock_total == 0,
    }
    return render(request, "tienda/detalle.html", contexto)
