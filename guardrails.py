"""Guardrails deterministas de entrada y salida para `POST /consultar` (Parte D).

Entrada (se ejecutan antes del modelo, la memoria y las herramientas):
    1. Límite de longitud: más de 1000 caracteres se rechaza.
    2. Filtro heurístico de prompt injection por categorías.

Salida (se aplica a la respuesta final antes de enviarla al cliente):
    3. Enmascarado de CUIT/CUIL, DNI, correo electrónico y teléfono.

Estos controles son una barrera adicional, no la única: la autorización real
(pedido propio, permisos de escritura) sigue en cada herramienta y en el
backend. El filtro de inyección es heurístico y no garantiza detectar todos
los ataques.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


LIMITE_CARACTERES_CONSULTA = 1000

ETIQUETA_CUIT_CUIL = "[CUIT_CUIL_ENMASCARADO]"
ETIQUETA_DNI = "[DNI_ENMASCARADO]"
ETIQUETA_EMAIL = "[EMAIL_ENMASCARADO]"
ETIQUETA_TELEFONO = "[TELEFONO_ENMASCARADO]"

MENSAJE_BLOQUEO_INYECCION = (
    "No puedo procesar esa solicitud. Puedo ayudarte con consultas sobre "
    "productos, el estado de tus pedidos o el registro de un reclamo."
)
MENSAJE_LIMITE_LONGITUD = (
    f"La consulta supera el límite de {LIMITE_CARACTERES_CONSULTA} caracteres."
)


@dataclass(frozen=True, slots=True)
class DeteccionInyeccion:
    """Resultado de una detección: solo la categoría, nunca el texto."""

    categoria: str


def excede_longitud(texto: str) -> bool:
    """Indica si la consulta supera el límite (1000 caracteres inclusive)."""

    return len(texto) > LIMITE_CARACTERES_CONSULTA


def _normalizar(texto: str) -> str:
    """Pasa a minúsculas, quita tildes y colapsa espacios.

    Así "Ignorá", "IGNORA" e "ignora" se evalúan igual.
    """

    sin_tildes = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


# Cada patrón exige una combinación de palabras (verbo + objeto), no una
# palabra aislada, para no bloquear consultas legítimas del dominio como
# "ignoren mi mensaje anterior" o "quiero reclamar por el pedido de otro local".
_PATRONES_INYECCION: dict[str, tuple[re.Pattern[str], ...]] = {
    "cambio_de_reglas": (
        re.compile(
            r"\b(ignor|olvid|omit|salte|descart|desobedec|anul)\w*"
            r"( (todas?|todos|cualquier|las|los|tus|sus|esas?|estas?|"
            r"previas?|anteriores?))*"
            r" (instrucciones|reglas|indicaciones|restricciones|politicas"
            r"|directivas|ordenes|prompt)"
        ),
        re.compile(
            r"\b(ignore|disregard|forget) (all |any |the |your )*"
            r"(previous |prior |above )?(instructions|rules|prompt)"
        ),
        re.compile(
            r"\bnuevas? (instrucciones|reglas)( del sistema)?:"
        ),
    ),
    "cambio_de_rol": (
        re.compile(
            r"\b(a partir de ahora|desde ahora|ahora) (sos|eres|seras|vas a ser"
            r"|actuas|actua|actuá)\b"
        ),
        re.compile(r"\b(actua|comportate|hace de cuenta que sos) como\b"),
        re.compile(
            r"\bmodo (desarrollador|developer|dios|admin|administrador|"
            r"sin restricciones|debug)\b"
        ),
        re.compile(r"\b(jailbreak|you are now|act as)\b"),
    ),
    "extraccion_de_instrucciones": (
        re.compile(
            r"\b(mostr|revel|deci|dame|imprim|repet|copi|escrib|pasa|filtr)\w*"
            r"( (me|el|la|los|las|tu|tus|su|sus|todo|todas?|completo))*"
            r" (system prompt|prompt( del sistema| interno| original)?"
            r"|instrucciones (del sistema|internas|ocultas|iniciales|originales)"
            r"|api ?key|clave de (la )?api|contrasena|credenciales|token)"
        ),
        re.compile(r"\bsystem prompt\b"),
    ),
    "evasion_de_validaciones": (
        re.compile(
            r"\b(sin|salte\w*|evit\w*|desactiv\w*|deshabilit\w*|bypass\w*"
            r"|omit\w*|saltarte|saltar)"
            r"( (los|las|todos?|todas?|tus|sus|esos?|esas?))*"
            r" (controles|validaciones|verificaciones|filtros|guardrails"
            r"|chequeos|restricciones de seguridad)"
        ),
    ),
    "acceso_a_otro_cliente": (
        re.compile(r"\bcliente_?id\b"),
        re.compile(
            r"\b(pedidos?|datos|reclamos?|envios?|informacion|cuenta|historial)"
            r" (de|del) (otro|otra|otros|otras|todos los|cualquier)"
            r" (cliente|clientes|usuario|usuarios)\b"
        ),
        re.compile(
            r"\b(hacete pasar|haceme pasar|suplanta\w*|como si fuera)"
            r"( por)? (otro|el) (cliente|usuario)\b"
        ),
    ),
}


def detectar_prompt_injection(texto: str) -> DeteccionInyeccion | None:
    """Detecta señales claras de prompt injection.

    Categorías: intentar cambiar reglas o rol del agente, extraer
    instrucciones internas o credenciales, evadir validaciones o acceder a
    datos de otro cliente.

    Returns:
        La categoría detectada o None si no hay señales claras.
    """

    normalizado = _normalizar(texto)
    for categoria, patrones in _PATRONES_INYECCION.items():
        if any(patron.search(normalizado) for patron in patrones):
            return DeteccionInyeccion(categoria=categoria)
    return None


# --- Enmascarado de datos personales (salida) ------------------------------

_PATRON_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+\b"
)

# CUIT/CUIL: prefijo válido + 8 dígitos + verificador, con o sin guiones o
# espacios. Los prefijos acotan los falsos positivos sobre números de pedido.
_PATRON_CUIT_CUIL = re.compile(
    r"(?<![\w$.])(20|23|24|27|30|33|34)[- ]?\d{8}[- ]?\d(?![\w])"
)

# DNI con contexto explícito ("DNI 30.123.456", "documento: 30123456").
_PATRON_DNI_CON_CONTEXTO = re.compile(
    r"\b(DNI|D\.N\.I\.?|documento)"
    r"(\s*(n[°ºo]\.?|nro\.?|numero|número))?\s*:?\s*"
    r"(\d{1,2}\.?\d{3}\.?\d{3})(?!\d)",
    re.IGNORECASE,
)
# DNI con formato inequívoco de puntos (30.123.456), sin "$" adelante para no
# enmascarar montos.
_PATRON_DNI_CON_PUNTOS = re.compile(r"(?<![\w$.,])\d{1,2}\.\d{3}\.\d{3}(?![\d.,])")

# Teléfono con contexto explícito ("tel 1145678901", "whatsapp: 11 4567 8901").
_PATRON_TELEFONO_CON_CONTEXTO = re.compile(
    r"\b(tel|tel\.|telefono|teléfono|celular|cel|movil|móvil|whatsapp|wsp)"
    r"\s*:?\s*(\+?[\d][\d\s()-]{6,}\d)",
    re.IGNORECASE,
)
# Teléfono con formato de separadores (+54 9 11 4567-8901, (011) 4567-8901,
# 11-4567-8901). Exige separador en el bloque final para no confundirlo con
# un número de pedido o una cantidad.
_PATRON_TELEFONO_FORMATEADO = re.compile(
    r"(?<![\w$])(\+54[\s-]?9?[\s-]?)?(\(?0?\d{2,4}\)?[\s-]?)?(15[\s-]?)?"
    r"\d{3,4}[\s-]\d{4}(?![\w])"
)


def enmascarar_datos_personales(texto: str) -> str:
    """Reemplaza CUIT/CUIL, DNI, email y teléfono por etiquetas semánticas.

    No enmascara números de pedido, SKU (ECO-XXXX), cantidades ni montos con
    "$". Para DNI y teléfono exige contexto o un formato inequívoco para
    evitar falsos positivos con secuencias numéricas aisladas.
    """

    if not texto:
        return texto

    resultado = _PATRON_EMAIL.sub(ETIQUETA_EMAIL, texto)
    resultado = _PATRON_CUIT_CUIL.sub(ETIQUETA_CUIT_CUIL, resultado)
    resultado = _PATRON_DNI_CON_CONTEXTO.sub(
        lambda coincidencia: f"{coincidencia.group(1)} {ETIQUETA_DNI}",
        resultado,
    )
    resultado = _PATRON_DNI_CON_PUNTOS.sub(ETIQUETA_DNI, resultado)
    resultado = _PATRON_TELEFONO_CON_CONTEXTO.sub(
        lambda coincidencia: f"{coincidencia.group(1)} {ETIQUETA_TELEFONO}",
        resultado,
    )
    resultado = _PATRON_TELEFONO_FORMATEADO.sub(ETIQUETA_TELEFONO, resultado)
    return resultado
