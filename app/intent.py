import re
import unicodedata
from rapidfuzz import fuzz, process
from app.constants import MESES_ES, MESES_EN, TERRITORIO_ES_EN

MESES_ES_inv = {v: k.capitalize() for k, v in MESES_ES.items()}

# Diccionario de palabras clave por intención
INTENT_KEYWORDS = {
    "ventas": [
        "venta", "ventas", "vendido", "vendidos",
        "ingreso", "ingresos", "ingresado",
        "facturado", "facturación",
        "total ventas", "qué se vendió", "cuánto se vendió",
    ],
    "gastos": [
        "gasto", "gastos", "gastó",
        "egreso", "egresos",
        "costo operativo", "costos operativos",
        "gasto operativo", "gastos operativos",
        "cuánto se gastó", "qué se gastó",
    ],
    "neto": [
        "neto", "neta",
        "ganancia", "ganancias", "ganó",
        "pérdida", "pérdidas", "perdí",
        "resultado neto", "resultado",
        "utilidad", "hubo ganancia", "hubo pérdida",
        "saldo",
    ],
    "pais": [
        "país", "países",
        "región", "regiones",
        "territorio", "territorios",
        "geográfico", "geográfica",
        "mayor movimiento", "más actividad",
        "qué país", "cuál país",
    ],
    "cuenta": [
        "cuenta", "cuentas",
        "subcuenta", "subcuentas",
        "mayor monto", "mayor acumulado",
        "qué cuenta", "cuál cuenta",
        "más dinero",
    ],
    "etl": [
        "limpieza", "limpiar", "limpiado",
        "transformación", "transformar", "transformaciones",
        "merge", "unión", "unir",
        "duplicados", "nulos",
        "etl", "procesamiento", "preparación",
        "qué se hizo", "qué limpieza", "qué transformaciones",
        "cómo se limpió", "cómo se procesó",
        "antes y después", "antes despues",
    ],
    "modelo": [
        "modelo", "relaciones", "diagrama",
        "conexiones", "tablas", "schema",
        "estructura", "cómo se conectan",
        "qué tablas hay", "cuáles tablas",
        "relación entre tablas",
    ],
    "pais_menor": [
        "menor movimiento", "menos actividad",
        "último país", "país con menos",
        "país inferior", "menos movimiento",
    ],
    "cuenta_menor": [
        "menor monto", "menos dinero",
        "última cuenta", "cuenta con menos",
        "cuenta inferior", "menor acumulado",
    ],
    "mensual": [
        "enero", "febrero", "marzo", "abril",
        "mayo", "junio", "julio", "agosto",
        "septiembre", "octubre", "noviembre", "diciembre",
        "mes", "mensual", "por mes",
    ],
    "territorio": [
        "norte", "sur", "este", "oeste",
        "territorio norte", "territorio sur",
        "región norte", "región sur",
    ],
    "resumen": [
        "resumen", "resumen general",
        "panorama", "vista general",
        "totales generales",
    ],
    "cuentas_mas_usadas": [
        "cuentas más usadas", "cuentas más utilizadas",
        "cuentas con más transacciones",
        "cuentas con mayor cantidad",
        "top cuentas",
    ],
    "dashboard": [
        "dashboard", "panel", "tablero",
        "indicadores", "kpi", "kpis",
        "mostrame dashboard", "ver dashboard",
        "panel de control",
    ],
    "grafico": [
        "grafico", "graficos", "graficar", "grafica", "graficame",
        "barras", "torta", "linea", "chart",
        "visualizar", "mostrar grafico",
        "grafico de barras", "grafico de torta",
        "grafico de lineas",
    ],
    "anomalia": [
        "anomalia", "anomalias", "outlier", "outliers",
        "atipico", "atipicos", "valor extraño",
        "fuera de lo normal", "valores anormales",
        "deteccion de anomalias",
    ],
    "prediccion": [
        "prediccion", "predicciones", "pronostico", "pronosticos",
        "tendencia futura", "proyeccion", "proyecciones",
        "predecir", "que pasara",
    ],
    "comparativa": [
        "comparativa", "comparar", "comparacion",
        "vs", "versus", "diferencia entre",
        "comparado con",
    ],
}

# Canonical questions for fuzzy matching (one per intent)
CANONICAL_QUESTIONS = {
    "ventas": "cuánto se vendió total de ventas",
    "gastos": "cuánto se gastó total de gastos",
    "neto": "resultado neto ganancia o pérdida",
    "pais": "país con mayor movimiento",
    "cuenta": "cuenta con mayor monto",
    "etl": "proceso de limpieza transformación",
    "modelo": "relaciones entre tablas diagrama",
    "pais_menor": "país con menor movimiento",
    "cuenta_menor": "cuenta con menor monto",
    "mensual": "gastos o ventas del mes de enero",
    "territorio": "gastos del territorio norte",
    "resumen": "resumen general de todas las cuentas",
    "cuentas_mas_usadas": "cuentas más utilizadas con más transacciones",
    "dashboard": "mostrame dashboard panel indicadores",
    "grafico": "grafico de barras ventas por pais",
    "anomalia": "detectar anomalias outliers valores atipicos",
    "prediccion": "prediccion tendencia futura proyeccion",
    "comparativa": "comparar ventas entre dos años",
}

# Umbral mínimo para fuzzy matching (0-100)
FUZZY_THRESHOLD = 65


def _normalize(text: str) -> str:
    """Normaliza texto: minúsculas, sin tildes, sin espacios extra.

    Usa unicodedata.NFKD para descomponer caracteres acentuados y eliminar
    diacríticos, en lugar de reemplazos manuales. Más robusto y eficiente.
    """
    text = text.lower().strip()
    # NFKD descompone 'é' en 'e' + combining acute accent
    text = unicodedata.normalize("NFKD", text)
    # Eliminar caracteres diacríticos (categoría 'Mn' = Mark, nonspacing)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Reemplazar ñ → n (NFKD no descompone la ñ)
    text = text.replace("ñ", "n")
    return text


def _has_word_boundary(normalized_text: str, keyword: str) -> bool:
    """Verifica que el keyword aparezca como palabra completa (no como substring)."""
    pattern = r'\b' + re.escape(keyword) + r'\b'
    return bool(re.search(pattern, normalized_text))


def detectar_intencion(question: str) -> str:
    """
    Detecta la intención de la pregunta del usuario con prioridad:
    1) Acciones explícitas (grafico, dashboard, anomalia, prediccion, comparativa, etl, modelo)
    2) Modificadores (mensual, territorio) — chequean nombres de mes/territorio
    3) Categorías (ventas, gastos, neto, pais, cuenta, pais_menor, cuenta_menor, cuentas_mas_usadas, resumen)
    4) Fuzzy matching como fallback
    """
    normalized = _normalize(question)

    # Prioridad 1: Acciones explícitas (deben coincidir exacto, no fuzzy)
    ACTION_INTENTS = ["dashboard", "grafico", "anomalia", "prediccion", "comparativa", "etl", "modelo"]
    for intent in ACTION_INTENTS:
        for kw in INTENT_KEYWORDS[intent]:
            if _has_word_boundary(normalized, _normalize(kw)):
                return intent

    # Prioridad 2: Modificadores (mensual, territorio)
    # Detecta si hay nombre de mes
    for nombre in MESES_ES:
        if _has_word_boundary(normalized, _normalize(nombre)):
            return "mensual"
    # Detecta si hay nombre de territorio
    for es_term in TERRITORIO_ES_EN:
        if _has_word_boundary(normalized, _normalize(es_term)):
            return "territorio"

    # Prioridad 3: Categorías, ordenadas por longitud descendente
    CATEGORY_INTENTS = [
        "pais_menor", "cuenta_menor", "cuentas_mas_usadas",
        "ventas", "gastos", "neto", "pais", "cuenta", "resumen",
    ]
    all_keywords = []
    for intent in CATEGORY_INTENTS:
        for kw in INTENT_KEYWORDS[intent]:
            all_keywords.append((_normalize(kw), intent))
    all_keywords.sort(key=lambda x: len(x[0]), reverse=True)

    for kw_normalized, intent in all_keywords:
        if _has_word_boundary(normalized, kw_normalized):
            return intent

    # Prioridad 4: Fuzzy matching como fallback
    best_intent = None
    best_score = 0
    for intent, canonical in CANONICAL_QUESTIONS.items():
        score = fuzz.token_sort_ratio(normalized, _normalize(canonical))
        if score > best_score:
            best_score = score
            best_intent = intent

    if best_score >= FUZZY_THRESHOLD:
        return best_intent

    return "desconocida"


def extract_year(question: str) -> int | None:
    """
    Extrae un año de la pregunta (cualquier año 20XX).
    Retorna None si no encuentra.
    """
    patterns = [
        r"\b(20\d{2})\b",
        r"\ben\s+(20\d{2})\b",
        r"\bdurante\s+(20\d{2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            return int(match.group(1))
    return None





def extract_month(question: str) -> tuple[int | None, str | None]:
    """
    Extrae un mes de la pregunta.
    Retorna (numero_mes, nombre_mes) o (None, None).
    Soporta español e inglés (Jan, Feb, etc).
    """
    normalized = _normalize(question)
    for nombre, num in MESES_ES.items():
        if _has_word_boundary(normalized, nombre):
            return num, nombre.capitalize()
    for nombre_en, num in MESES_EN.items():
        if _has_word_boundary(normalized, nombre_en):
            return num, MESES_ES_inv.get(num, nombre_en.capitalize())
    return None, None


def extract_territorio(question: str) -> str | None:
    """
    Extrae un territorio/región de la pregunta.
    Retorna el nombre en inglés o None.
    """
    normalized = _normalize(question)
    for es_term, en_term in TERRITORIO_ES_EN.items():
        if _has_word_boundary(normalized, es_term):
            return en_term
    return None
