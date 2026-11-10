"""
Modelos de datos de MP Shop (Music Pro Company - Sucursal / Punto de Venta).

Evaluación 2 (Unidad 2: Framework back end). En la Evaluación 1 los datos
vivían en un archivo JSON; ahora se persisten en una base de datos relacional
mediante el ORM de Django.

Entidades:
    Sucursal, Categoria, Marca, Producto, Inventario (stock por sucursal),
    Cliente, Venta y DetalleVenta.
"""
from django.core.validators import MinValueValidator
from django.db import models


class Sucursal(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    ciudad = models.CharField(max_length=60)
    direccion = models.CharField("dirección", max_length=150)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "sucursal"
        verbose_name_plural = "sucursales"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.ciudad})"


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    descripcion = models.TextField("descripción", blank=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Marca(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    pais_origen = models.CharField("país de origen", max_length=60, blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    sku = models.CharField("SKU", max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField("descripción", blank=True)
    precio = models.PositiveIntegerField("precio (CLP)", validators=[MinValueValidator(1)])
    imagen = models.URLField("URL de imagen", blank=True)
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField(
        default=False, help_text="Si está marcado, aparece en la portada de la tienda."
    )
    creado = models.DateTimeField(auto_now_add=True)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="productos"
    )
    marca = models.ForeignKey(
        Marca, on_delete=models.PROTECT, related_name="productos"
    )

    class Meta:
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["nombre"], name="producto_nombre_idx"),
        ]

    def __str__(self):
        return f"{self.sku} - {self.nombre}"

    @property
    def stock_total(self):
        """Suma del stock del producto en todas las sucursales."""
        return sum(inv.stock for inv in self.inventarios.all())


class Inventario(models.Model):
    """Tabla intermedia Producto <-> Sucursal con la cantidad en stock."""
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name="inventarios"
    )
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, related_name="inventarios"
    )
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "inventario"
        verbose_name_plural = "inventarios"
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "sucursal"], name="inventario_producto_sucursal_uniq"
            )
        ]

    def __str__(self):
        return f"{self.producto.sku} @ {self.sucursal.nombre}: {self.stock}"


class Cliente(models.Model):
    rut = models.CharField("RUT", max_length=12, unique=True)
    nombre = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.rut})"


class Venta(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PEN", "Pendiente"
        PAGADA = "PAG", "Pagada"
        ENTREGADA = "ENT", "Entregada"
        ANULADA = "ANU", "Anulada"

    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="ventas"
    )
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.PROTECT, related_name="ventas"
    )
    fecha = models.DateTimeField(db_index=True)
    estado = models.CharField(
        max_length=3, choices=Estado.choices, default=Estado.PENDIENTE
    )
    total = models.PositiveIntegerField(default=0, help_text="Se recalcula con el detalle.")

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Venta #{self.pk} - {self.cliente.nombre}"

    def recalcular_total(self):
        """Recalcula el total sumando los subtotales del detalle."""
        total = sum(d.subtotal for d in self.detalles.all())
        if total != self.total:
            self.total = total
            self.save(update_fields=["total"])
        return total


class DetalleVenta(models.Model):
    venta = models.ForeignKey(
        Venta, on_delete=models.CASCADE, related_name="detalles"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="detalles_venta"
    )
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    precio_unitario = models.PositiveIntegerField(
        blank=True, default=0,
        help_text="Si se deja en 0 se usa el precio actual del producto.",
    )

    class Meta:
        verbose_name = "detalle de venta"
        verbose_name_plural = "detalles de venta"

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio
        super().save(*args, **kwargs)
