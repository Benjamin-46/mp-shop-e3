# MP Shop — Music Pro Company (Sucursal / Punto de Venta)

Proyecto del caso semestral de **Programación Backend** (INACAP).

| Evaluación | Unidad | Contenido |
|---|---|---|
| E1 | Tecnologías del lado del servidor | Sitio Django sin base de datos, datos mock en JSON |
| E2 | Framework back end | Base de datos, modelos, migraciones, diagrama, Django Admin y datos de prueba con Faker |
| **E3** | **Framework back end** | **Panel administrativo propio (sin Django Admin): login/logout, CRUD, usuarios, MySQL y 20 reportes con ORM** |

## Puesta en marcha (MySQL local)

1. Instala MySQL (o MariaDB) y crea la base de datos:

   ```sql
   CREATE DATABASE mp_shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

2. Copia `.env.example` como `.env` y escribe tu usuario y clave de MySQL (el archivo `.env` no se sube a GitHub).
3. En la terminal:

```bat
python -m venv venv
venv\Scripts\activate            :: Linux/Mac: source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py verificar_bd
python manage.py cargar_json_inicial
python manage.py createsuperuser           :: tu primer usuario administrador
python manage.py runserver
```

* Sitio público: <http://127.0.0.1:8000/>
* **Panel administrativo (E3): <http://127.0.0.1:8000/panel/>** (pide iniciar sesión)
* Django Admin (E2, se conserva): <http://127.0.0.1:8000/admin/>

Para probar sin MySQL: `set DB_ENGINE=sqlite` (Windows) o `DB_ENGINE=sqlite` (Linux/Mac) antes de los comandos.

## Evaluación 3: panel administrativo propio

| Requisito | Dónde está |
|---|---|
| Login y logout | `panel/views.py` (`IniciarSesion`), `LogoutView` en `panel/urls.py`; plantilla `panel/login.html` |
| Vistas protegidas con decoradores | `@login_required` en cada vista de `panel/views.py` y `panel/views_reportes.py` |
| Redirección de usuarios sin sesión | `LOGIN_URL` en `settings.py` |
| Sesiones | Tabla `django_session`; expira a los 30 min sin actividad o al cerrar el navegador (`settings.py`) |
| CRUD de usuarios (crear, consultar, modificar, desactivar, cambiar clave) | `usuario_*` en `panel/views.py`; solo administradores (`@solo_administradores`) |
| CRUD de entidades | Categorías, marcas, sucursales, productos (con stock por sucursal), clientes y ventas (con detalle) |
| Formularios con validación | `panel/forms.py` (RUT con dígito verificador, SKU único, cliente y producto deben existir, etc.) |
| Consultas con ORM | Todo con el ORM, sin SQL escrito a mano |
| 20 reportes (proyecto Tienda) | `panel/reportes.py`; menú **Reportes ORM** del panel |

Rutas principales: `/panel/`, `/panel/login/`, `/panel/productos/`, `/panel/clientes/`, `/panel/ventas/`,
`/panel/usuarios/`, `/panel/reportes/`.

Los usuarios **no se eliminan, se desactivan** (conservan su historial). Los registros con dependencias
(por ejemplo una categoría con productos) no se pueden borrar: el sistema lo avisa.

## Base de datos (2.1.1)

Desde la E3 usa **MySQL** (local). La configuración está en `mp_shop/settings.py` → `DATABASES` y los
datos de conexión se leen del archivo `.env` (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`).
También se puede usar SQLite (`DB_ENGINE=sqlite`) o PostgreSQL (`DB_ENGINE=postgresql`).

`python manage.py verificar_bd` muestra qué base de datos se está usando, prueba la conexión
con un `SELECT 1`, indica si hay migraciones pendientes y cuenta los registros por tabla.

## Modelos y diagrama

`Sucursal`, `Categoria`, `Marca`, `Producto`, `Inventario` (stock por sucursal),
`Cliente`, `Venta` y `DetalleVenta`.

* Código: `tienda/models.py`
* Diagrama: `docs/diagrama_bd.png` (se regenera desde los modelos con
  `python manage.py generar_diagrama`; requiere Graphviz para el PNG).

Relaciones: Categoria 1—N Producto · Marca 1—N Producto · Cliente 1—N Venta · Sucursal 1—N Venta ·
Venta 1—N DetalleVenta · Producto 1—N DetalleVenta · Producto N—M Sucursal (a través de `Inventario`).

## Migraciones

Historial en `tienda/migrations/`:

| Migración | Qué hace |
|---|---|
| `0001_initial` | Crea las 8 tablas, claves foráneas, índice y restricción única de inventario |
| `0002_producto_destacado` | Modificación del modelo: agrega `Producto.destacado` |

Flujo de trabajo: editar `models.py` → `python manage.py makemigrations` → `python manage.py migrate`.
Estado actual: `python manage.py showmigrations tienda`.

## Django Admin (2.1.2)

Configurado en `tienda/admin.py`: columnas (`list_display`), filtros (`list_filter`),
búsqueda (`search_fields`), edición en línea del stock y del detalle de venta (inlines),
acciones masivas (activar/desactivar productos), jerarquía por fecha, campos de solo
lectura y `autocomplete_fields` (para no cargar un desplegable con miles de productos).
Crear, consultar, modificar y eliminar registros se hace desde el panel. (En la E3 la administración
se hace con el panel propio; el Django Admin se conserva como parte de la E2.)

## Datos de prueba con Faker

```bash
python manage.py poblar_datos productos 100
python manage.py poblar_datos productos 1000
python manage.py poblar_datos productos 100000
python manage.py poblar_datos productos 1000000 --lote 10000
python manage.py poblar_datos clientes 1000
python manage.py poblar_datos ventas 1000        # requiere productos y clientes
```

Usa `bulk_create()` por lotes dentro de transacciones (un INSERT por lote, no por fila).
Cada producto genera además un registro de inventario por sucursal. Opción `--semilla N`
para repetir los mismos datos.

## Pruebas automáticas

```bash
python manage.py test
```

Cubre la conexión, restricciones de los modelos, el CRUD completo en Django Admin,
filtros, búsquedas, acciones, la carga con Faker y el sitio público.
