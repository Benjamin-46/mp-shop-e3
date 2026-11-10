"""
Vistas del panel administrativo propio (Evaluación 3).

Seguridad: TODAS las vistas llevan @login_required. Las de usuarios además
exigen ser administrador (is_staff). Quien no ha iniciado sesión y escribe la
URL directamente es redirigido a la pantalla de login (settings.LOGIN_URL).
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import ProtectedError, Q, RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from tienda.models import (
    Categoria, Cliente, Marca, Producto, Sucursal, Venta,
)

from .forms import (
    CategoriaForm, ClienteForm, DetalleVentaFormSet, InventarioFormSet, MarcaForm,
    ProductoForm, SucursalForm, UsuarioClaveForm, UsuarioCrearForm,
    UsuarioEditarForm, VentaForm,
)

User = get_user_model()
POR_PAGINA = 15


# --- control de acceso -----------------------------------------------------------
def solo_administradores(vista):
    """Decorador: además de haber iniciado sesión, hay que ser administrador."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


# --- autenticación -----------------------------------------------------------------
class IniciarSesion(LoginView):
    """Login con las herramientas de Django (AuthenticationForm + sesión)."""
    template_name = "panel/login.html"
    redirect_authenticated_user = True


# --- ayudas compartidas por las vistas CRUD ---------------------------------------
def _valor(obj, ruta):
    """Resuelve 'categoria.nombre' sobre un objeto; formatea booleanos."""
    for parte in ruta.split("."):
        obj = getattr(obj, parte)
        if callable(obj):
            obj = obj()
    if isinstance(obj, bool):
        return "Sí" if obj else "No"
    return obj


def _lista(request, *, titulo, queryset, columnas, base, buscar=(), singular="registro", extra_acciones=None):
    """Listado paginado con búsqueda. 'base' arma los nombres de URL del CRUD."""
    q = request.GET.get("q", "").strip()
    if q and buscar:
        condicion = Q()
        for campo in buscar:
            condicion |= Q(**{f"{campo}__icontains": q})
        queryset = queryset.filter(condicion)
    pagina = Paginator(queryset, POR_PAGINA).get_page(request.GET.get("page"))
    filas = [
        {"pk": obj.pk, "celdas": [_valor(obj, ruta) for _, ruta in columnas]}
        for obj in pagina
    ]
    return render(request, "panel/lista.html", {
        "titulo_pagina": titulo,
        "encabezados": [nombre for nombre, _ in columnas],
        "filas": filas,
        "pagina": pagina,
        "q": q,
        "buscable": bool(buscar),
        "url_crear": f"panel:{base}_crear",
        "url_editar": f"panel:{base}_editar",
        "url_eliminar": f"panel:{base}_eliminar" if base != "usuario" else None,
        "singular": singular,
        "usuarios": base == "usuario",
        "extra_acciones": extra_acciones,
    })


def _formulario(request, *, titulo, form_class, instancia, url_lista, formset_class=None,
                titulo_formset="", despues=None, mensaje="guardado"):
    """Alta / edición genérica: valida, guarda en una transacción y avisa."""
    if request.method == "POST":
        form = form_class(request.POST, instance=instancia)
        formset = formset_class(request.POST, instance=form.instance) if formset_class else None
        if form.is_valid() and (formset is None or formset.is_valid()):
            with transaction.atomic():
                objeto = form.save()
                if formset is not None:
                    formset.instance = objeto
                    formset.save()
                if despues:
                    despues(objeto)
            messages.success(request, f"«{objeto}» {mensaje} correctamente.")
            return redirect(url_lista)
        messages.error(request, "Revisa los datos: hay errores en el formulario.")
    else:
        form = form_class(instance=instancia)
        formset = formset_class(instance=form.instance) if formset_class else None
    return render(request, "panel/form.html", {
        "titulo_pagina": titulo, "form": form, "formset": formset,
        "titulo_formset": titulo_formset, "url_lista": url_lista,
    })


def _eliminar(request, *, objeto, titulo, url_lista, aviso=""):
    """Confirma y elimina. Si otros registros dependen del objeto, no se borra."""
    if request.method == "POST":
        nombre = str(objeto)
        try:
            objeto.delete()
        except (ProtectedError, RestrictedError):
            messages.error(
                request,
                f"No se puede eliminar «{nombre}» porque tiene registros asociados "
                "(por ejemplo productos o ventas).")
            return redirect(url_lista)
        messages.success(request, f"«{nombre}» eliminado correctamente.")
        return redirect(url_lista)
    return render(request, "panel/confirmar_eliminar.html", {
        "titulo_pagina": titulo, "objeto": objeto, "url_lista": url_lista, "aviso": aviso,
    })


# --- inicio -----------------------------------------------------------------------------
@login_required
def inicio(request):
    contexto = {
        "titulo_pagina": "Panel administrativo",
        "totales": [
            ("Productos", Producto.objects.count(), "panel:producto_lista"),
            ("Clientes", Cliente.objects.count(), "panel:cliente_lista"),
            ("Ventas", Venta.objects.count(), "panel:venta_lista"),
            ("Categorías", Categoria.objects.count(), "panel:categoria_lista"),
        ],
        "ultimas_ventas": Venta.objects.select_related("cliente", "sucursal").order_by("-fecha")[:5],
    }
    return render(request, "panel/inicio.html", contexto)


# --- categorías ---------------------------------------------------------------------------
@login_required
def categoria_lista(request):
    return _lista(request, titulo="Categorías", queryset=Categoria.objects.all(), base="categoria",
                  columnas=[("Nombre", "nombre"), ("Descripción", "descripcion")],
                  buscar=("nombre",), singular="categoría")


@login_required
def categoria_crear(request):
    return _formulario(request, titulo="Nueva categoría", form_class=CategoriaForm,
                       instancia=None, url_lista="panel:categoria_lista", mensaje="creada")


@login_required
def categoria_editar(request, pk):
    return _formulario(request, titulo="Editar categoría", form_class=CategoriaForm,
                       instancia=get_object_or_404(Categoria, pk=pk),
                       url_lista="panel:categoria_lista", mensaje="actualizada")


@login_required
def categoria_eliminar(request, pk):
    return _eliminar(request, objeto=get_object_or_404(Categoria, pk=pk),
                     titulo="Eliminar categoría", url_lista="panel:categoria_lista")


# --- marcas -------------------------------------------------------------------------------
@login_required
def marca_lista(request):
    return _lista(request, titulo="Marcas", queryset=Marca.objects.all(), base="marca",
                  columnas=[("Nombre", "nombre"), ("País de origen", "pais_origen")],
                  buscar=("nombre", "pais_origen"), singular="marca")


@login_required
def marca_crear(request):
    return _formulario(request, titulo="Nueva marca", form_class=MarcaForm,
                       instancia=None, url_lista="panel:marca_lista", mensaje="creada")


@login_required
def marca_editar(request, pk):
    return _formulario(request, titulo="Editar marca", form_class=MarcaForm,
                       instancia=get_object_or_404(Marca, pk=pk),
                       url_lista="panel:marca_lista", mensaje="actualizada")


@login_required
def marca_eliminar(request, pk):
    return _eliminar(request, objeto=get_object_or_404(Marca, pk=pk),
                     titulo="Eliminar marca", url_lista="panel:marca_lista")


# --- sucursales -----------------------------------------------------------------------------
@login_required
def sucursal_lista(request):
    return _lista(request, titulo="Sucursales", queryset=Sucursal.objects.all(), base="sucursal",
                  columnas=[("Nombre", "nombre"), ("Ciudad", "ciudad"),
                            ("Dirección", "direccion"), ("Activa", "activa")],
                  buscar=("nombre", "ciudad"), singular="sucursal")


@login_required
def sucursal_crear(request):
    return _formulario(request, titulo="Nueva sucursal", form_class=SucursalForm,
                       instancia=None, url_lista="panel:sucursal_lista", mensaje="creada")


@login_required
def sucursal_editar(request, pk):
    return _formulario(request, titulo="Editar sucursal", form_class=SucursalForm,
                       instancia=get_object_or_404(Sucursal, pk=pk),
                       url_lista="panel:sucursal_lista", mensaje="actualizada")


@login_required
def sucursal_eliminar(request, pk):
    return _eliminar(request, objeto=get_object_or_404(Sucursal, pk=pk),
                     titulo="Eliminar sucursal", url_lista="panel:sucursal_lista")


# --- productos -------------------------------------------------------------------------------
@login_required
def producto_lista(request):
    consulta = Producto.objects.select_related("categoria", "marca").order_by("-id")
    return _lista(request, titulo="Productos", queryset=consulta, base="producto",
                  columnas=[("SKU", "sku"), ("Nombre", "nombre"), ("Categoría", "categoria.nombre"),
                            ("Marca", "marca.nombre"), ("Precio", "precio"), ("Activo", "activo")],
                  buscar=("sku", "nombre", "marca__nombre"), singular="producto")


@login_required
def producto_crear(request):
    return _formulario(request, titulo="Nuevo producto", form_class=ProductoForm, instancia=None,
                       url_lista="panel:producto_lista", formset_class=InventarioFormSet,
                       titulo_formset="Stock por sucursal", mensaje="creado")


@login_required
def producto_editar(request, pk):
    return _formulario(request, titulo="Editar producto", form_class=ProductoForm,
                       instancia=get_object_or_404(Producto, pk=pk),
                       url_lista="panel:producto_lista", formset_class=InventarioFormSet,
                       titulo_formset="Stock por sucursal", mensaje="actualizado")


@login_required
def producto_eliminar(request, pk):
    return _eliminar(request, objeto=get_object_or_404(Producto, pk=pk),
                     titulo="Eliminar producto", url_lista="panel:producto_lista",
                     aviso="También se borrará su stock en todas las sucursales.")


# --- clientes ---------------------------------------------------------------------------------
@login_required
def cliente_lista(request):
    return _lista(request, titulo="Clientes", queryset=Cliente.objects.order_by("-id"), base="cliente",
                  columnas=[("RUT", "rut"), ("Nombre", "nombre"), ("Email", "email"), ("Teléfono", "telefono")],
                  buscar=("rut", "nombre", "email"), singular="cliente")


@login_required
def cliente_crear(request):
    return _formulario(request, titulo="Nuevo cliente", form_class=ClienteForm,
                       instancia=None, url_lista="panel:cliente_lista", mensaje="creado")


@login_required
def cliente_editar(request, pk):
    return _formulario(request, titulo="Editar cliente", form_class=ClienteForm,
                       instancia=get_object_or_404(Cliente, pk=pk),
                       url_lista="panel:cliente_lista", mensaje="actualizado")


@login_required
def cliente_eliminar(request, pk):
    return _eliminar(request, objeto=get_object_or_404(Cliente, pk=pk),
                     titulo="Eliminar cliente", url_lista="panel:cliente_lista")


# --- ventas -----------------------------------------------------------------------------------
@login_required
def venta_lista(request):
    consulta = Venta.objects.select_related("cliente", "sucursal").order_by("-fecha")
    return _lista(request, titulo="Ventas", queryset=consulta, base="venta",
                  columnas=[("N°", "id"), ("Fecha", "fecha"), ("Cliente", "cliente.nombre"),
                            ("Sucursal", "sucursal.nombre"), ("Estado", "get_estado_display"),
                            ("Total", "total")],
                  buscar=("cliente__nombre", "cliente__rut"), singular="venta")


@login_required
def venta_crear(request):
    return _formulario(request, titulo="Nueva venta", form_class=VentaForm, instancia=None,
                       url_lista="panel:venta_lista", formset_class=DetalleVentaFormSet,
                       titulo_formset="Detalle de la venta",
                       despues=lambda venta: venta.recalcular_total(), mensaje="registrada")


@login_required
def venta_editar(request, pk):
    return _formulario(request, titulo="Editar venta", form_class=VentaForm,
                       instancia=get_object_or_404(Venta, pk=pk),
                       url_lista="panel:venta_lista", formset_class=DetalleVentaFormSet,
                       titulo_formset="Detalle de la venta",
                       despues=lambda venta: venta.recalcular_total(), mensaje="actualizada")


@login_required
def venta_eliminar(request, pk):
    return _eliminar(request, objeto=get_object_or_404(Venta, pk=pk),
                     titulo="Eliminar venta", url_lista="panel:venta_lista",
                     aviso="También se borrará el detalle de la venta.")


# --- usuarios (solo administradores) ----------------------------------------------------------
def _usuario_editable(request, pk):
    """Un administrador común no puede tocar a un superusuario."""
    usuario = get_object_or_404(User, pk=pk)
    if usuario.is_superuser and not request.user.is_superuser:
        raise PermissionDenied
    return usuario


@login_required
@solo_administradores
def usuario_lista(request):
    return _lista(request, titulo="Usuarios", queryset=User.objects.order_by("username"),
                  base="usuario",
                  columnas=[("Usuario", "username"), ("Nombre", "get_full_name"), ("Email", "email"),
                            ("Administrador", "is_staff"), ("Activo", "is_active")],
                  buscar=("username", "first_name", "last_name", "email"), singular="usuario")


@login_required
@solo_administradores
def usuario_crear(request):
    return _formulario(request, titulo="Nuevo usuario", form_class=UsuarioCrearForm,
                       instancia=None, url_lista="panel:usuario_lista", mensaje="creado")


@login_required
@solo_administradores
def usuario_editar(request, pk):
    usuario = _usuario_editable(request, pk)
    if request.method == "POST":
        form = UsuarioEditarForm(request.POST, instance=usuario)
        if usuario == request.user:
            # Nadie puede quitarse a sí mismo el acceso o el rol de administrador.
            form.fields["is_staff"].disabled = True
            form.fields["is_active"].disabled = True
        if form.is_valid():
            form.save()
            messages.success(request, f"Usuario «{usuario.username}» actualizado correctamente.")
            return redirect("panel:usuario_lista")
        messages.error(request, "Revisa los datos: hay errores en el formulario.")
    else:
        form = UsuarioEditarForm(instance=usuario)
        if usuario == request.user:
            form.fields["is_staff"].disabled = True
            form.fields["is_active"].disabled = True
    return render(request, "panel/form.html", {
        "titulo_pagina": f"Editar usuario {usuario.username}", "form": form, "formset": None,
        "url_lista": "panel:usuario_lista",
        "enlace_extra": ("panel:usuario_clave", usuario.pk, "Cambiar contraseña"),
    })


@login_required
@solo_administradores
def usuario_clave(request, pk):
    usuario = _usuario_editable(request, pk)
    if request.method == "POST":
        form = UsuarioClaveForm(usuario, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Contraseña de «{usuario.username}» actualizada.")
            return redirect("panel:usuario_lista")
    else:
        form = UsuarioClaveForm(usuario)
    return render(request, "panel/form.html", {
        "titulo_pagina": f"Cambiar contraseña de {usuario.username}", "form": form,
        "formset": None, "url_lista": "panel:usuario_lista",
    })


@login_required
@solo_administradores
@require_POST
def usuario_estado(request, pk):
    """Desactiva o reactiva un usuario (no se elimina: conserva su historial)."""
    usuario = _usuario_editable(request, pk)
    if usuario == request.user:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
    else:
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active"])
        estado = "activado" if usuario.is_active else "desactivado"
        messages.success(request, f"Usuario «{usuario.username}» {estado}.")
    return redirect("panel:usuario_lista")
