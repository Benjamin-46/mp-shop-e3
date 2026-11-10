"""Utilidades compartidas: validación y formato de RUT chileno."""


def digito_verificador(numero: int) -> str:
    """Calcula el dígito verificador de un RUT chileno (módulo 11)."""
    suma, factor = 0, 2
    for digito in reversed(str(numero)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: "0", 10: "K"}.get(resto, str(resto))


def normalizar_rut(texto: str) -> str:
    """Devuelve el RUT como 12345678-5 (sin puntos, DV en mayúscula).

    Lanza ValueError si el formato o el dígito verificador no son válidos.
    """
    limpio = texto.replace(".", "").replace(" ", "").upper()
    if "-" not in limpio:
        limpio = f"{limpio[:-1]}-{limpio[-1:]}"
    cuerpo, _, dv = limpio.partition("-")
    if not cuerpo.isdigit() or not (1 <= len(cuerpo) <= 8) or len(dv) != 1:
        raise ValueError("Formato de RUT no válido. Ejemplo: 12.345.678-5")
    if digito_verificador(int(cuerpo)) != dv:
        raise ValueError("El dígito verificador del RUT no es correcto.")
    return f"{int(cuerpo)}-{dv}"
