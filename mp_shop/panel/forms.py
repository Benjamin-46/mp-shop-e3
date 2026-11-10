"""Formularios del panel administrativo (Evaluación 3)."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.forms import inlineformset_factory
from django.utils import timezone

from tienda.models import (
    Categoria, Cliente, DetalleVenta, Inventario, Marca, Producto, Sucursal, Venta,
)
from tienda.utils import normalizar_rut

User = get_user_model()


class EstiloBootstrap:
    """Agrega las clases de Bootstrap a todos los campos del formulario."""

    def _aplicar_estilo(self):
        for campo in self.fields.values():
            w = campo.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs["class"] = "form-check-input"
            elif isinstance(w, forms.Select):
                w.attrs["class"] = "form-select"
            else:
                w.attrs["class"] = "form-control"


class FormularioBase(EstiloBootstrap, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_estilo()


# --- catálogos simples --------------------------------------------------------
class CategoriaForm(FormularioBase):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}


class MarcaForm(FormularioBase):
    class Meta:
        model = Marca
        fields = ["nombre", "pais_origen"]


class SucursalForm(FormularioBase):
    class Meta:
        model = Sucursal
        fields = ["nombre", "ciudad", "direccion", "telefono", "activa"]


# --- productos (+ stock por sucursal) ----------------------------------------
class ProductoForm(FormularioBase):
    class Meta:
        model = Producto
        fields = [
            "sku", "nombre", "categoria", "marca", "precio",
            "descripcion", "imagen", "activo", "destacado",
        ]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        if len(nombre) < 3:
            raise forms.ValidationError("El nombre debe tener al menos 3 caracteres.")
        return nombre

    def clean_sku(self):
        return self.cleaned_data["sku"].strip().upper()


class InventarioForm(FormularioBase):
    class Meta:
        model = Inventario
        fields = ["sucursal", "stock"]


InventarioFormSet = inlineformset_factory(
    Producto, Inventario, form=InventarioForm, extra=1, can_delete=True
)


# --- clientes -----------------------------------------------------------------
class ClienteForm(FormularioBase):
    class Meta:
        model = Cliente
        fields = ["rut", "nombre", "email", "telefono"]

    def clean_rut(self):
        try:
            return normalizar_rut(self.cleaned_data["rut"])
        except ValueError as error:
            raise forms.ValidationError(str(error))


# --- ventas (+ detalle) ---------------------------------------------------------
class VentaForm(FormularioBase):
    """El cliente se indica por RUT: un <select> con miles de clientes no sirve."""
    rut_cliente = forms.CharField(label="RUT del cliente", max_length=12)

    class Meta:
        model = Venta
        fields = ["sucursal", "fecha", "estado"]
        widgets = {
            "fecha": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]
        if self.instance.pk:
            self.fields["rut_cliente"].initial = self.instance.cliente.rut
            self.initial["fecha"] = timezone.localtime(self.instance.fecha)
        else:
            self.initial["fecha"] = timezone.localtime()
        self.order_fields(["rut_cliente", "sucursal", "fecha", "estado"])
        self._aplicar_estilo()

    def clean_rut_cliente(self):
        try:
            rut = normalizar_rut(self.cleaned_data["rut_cliente"])
        except ValueError as error:
            raise forms.ValidationError(str(error))
        try:
            self._cliente = Cliente.objects.get(rut=rut)
        except Cliente.DoesNotExist:
            raise forms.ValidationError("No existe un cliente con ese RUT. Créalo primero en Clientes.")
        return rut

    def save(self, commit=True):
        self.instance.cliente = self._cliente
        return super().save(commit)


class DetalleVentaForm(FormularioBase):
    """Cada línea de la venta identifica el producto por su SKU."""
    sku = forms.CharField(label="SKU del producto", max_length=20)

    class Meta:
        model = DetalleVenta
        fields = ["cantidad", "precio_unitario"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["sku"].initial = self.instance.producto.sku
        self.fields["precio_unitario"].help_text = "Vacío = precio actual del producto"
        self.fields["precio_unitario"].required = False
        if not self.instance.pk:
            self.initial["precio_unitario"] = None   # vacío = usa el precio actual
        self.order_fields(["sku", "cantidad", "precio_unitario"])
        self._aplicar_estilo()

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip().upper()
        try:
            self._producto = Producto.objects.get(sku=sku)
        except Producto.DoesNotExist:
            raise forms.ValidationError(f"No existe el producto con SKU {sku}.")
        return sku

    def clean_precio_unitario(self):
        return self.cleaned_data.get("precio_unitario") or 0

    def save(self, commit=True):
        self.instance.producto = self._producto
        return super().save(commit)


DetalleVentaFormSet = inlineformset_factory(
    Venta, DetalleVenta, form=DetalleVentaForm,
    extra=0, min_num=1, validate_min=True, can_delete=True,
)


# --- usuarios -------------------------------------------------------------------
class UsuarioCrearForm(EstiloBootstrap, UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_staff"]
        labels = {"is_staff": "Administrador (puede gestionar usuarios)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_estilo()


class UsuarioEditarForm(FormularioBase):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_staff", "is_active"]
        labels = {
            "is_staff": "Administrador (puede gestionar usuarios)",
            "is_active": "Activo (puede iniciar sesión)",
        }


class UsuarioClaveForm(EstiloBootstrap, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_estilo()
