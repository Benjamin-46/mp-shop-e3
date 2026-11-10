"""
MODULO HISTORICO (Evaluación 1). Desde la Evaluación 2 los datos viven en la base
de datos (models.py); este módulo solo se conserva para importar el JSON inicial
con "python manage.py cargar_json_inicial".

Acceso a los datos de productos de Music Pro (Sucursal / Punto de Venta).

En esta fase del proyecto (Evaluación 1 - Unidad 1: Tecnologías del lado
del servidor) todavía NO existe conexión a base de datos. La información
se simula mediante un archivo productos.json que se lee y actualiza desde
el propio servidor, cumpliendo con el requisito de "datos mock" de la
Fase 3 del caso semestral.
"""
import json
from pathlib import Path

RUTA_JSON = Path(__file__).resolve().parent / "data" / "productos.json"


def obtener_productos():
    """Lee y retorna la lista completa de productos (lista de diccionarios)."""
    with open(RUTA_JSON, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def obtener_categorias():
    """Retorna la lista de categorías únicas presentes en el catálogo."""
    productos = obtener_productos()
    categorias = sorted({producto["categoria"] for producto in productos})
    return categorias


def obtener_producto_por_id(producto_id):
    """Busca un producto por su id. Retorna None si no existe."""
    for producto in obtener_productos():
        if producto["id"] == producto_id:
            return producto
    return None


def filtrar_por_categoria(categoria):
    """Retorna solo los productos que pertenecen a la categoría indicada."""
    productos = obtener_productos()
    if not categoria:
        return productos
    return [p for p in productos if p["categoria"].lower() == categoria.lower()]


def agregar_producto(datos_producto):
    """
    Agrega un nuevo producto al archivo JSON (simula el alta administrativa
    de un producto, sin base de datos todavía).
    """
    productos = obtener_productos()
    nuevo_id = max((p["id"] for p in productos), default=0) + 1
    datos_producto["id"] = nuevo_id
    productos.append(datos_producto)
    with open(RUTA_JSON, "w", encoding="utf-8") as archivo:
        json.dump(productos, archivo, ensure_ascii=False, indent=2)
    return datos_producto
