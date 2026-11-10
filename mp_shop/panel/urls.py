from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views, views_reportes

app_name = "panel"


def crud(nombre, modulo=views):
    """Genera las 4 rutas CRUD de una entidad: lista, crear, editar, eliminar."""
    return [
        path(f"{nombre}s/", getattr(modulo, f"{nombre}_lista"), name=f"{nombre}_lista"),
        path(f"{nombre}s/nuevo/", getattr(modulo, f"{nombre}_crear"), name=f"{nombre}_crear"),
        path(f"{nombre}s/<int:pk>/editar/", getattr(modulo, f"{nombre}_editar"), name=f"{nombre}_editar"),
        path(f"{nombre}s/<int:pk>/eliminar/", getattr(modulo, f"{nombre}_eliminar"), name=f"{nombre}_eliminar"),
    ]


urlpatterns = [
    path("", views.inicio, name="inicio"),
    # Autenticación
    path("login/", views.IniciarSesion.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # Usuarios (solo administradores; se desactivan, no se eliminan)
    path("usuarios/", views.usuario_lista, name="usuario_lista"),
    path("usuarios/nuevo/", views.usuario_crear, name="usuario_crear"),
    path("usuarios/<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/clave/", views.usuario_clave, name="usuario_clave"),
    path("usuarios/<int:pk>/estado/", views.usuario_estado, name="usuario_estado"),
    # Reportes ORM
    path("reportes/", views_reportes.indice, name="reportes"),
    path("reportes/<int:numero>/", views_reportes.reporte, name="reporte"),
] + crud("categoria") + crud("marca") + crud("sucursal") + crud("producto") + crud("cliente") + crud("venta")
