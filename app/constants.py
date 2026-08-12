"""Constantes compartidas entre módulos."""

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

NOMBRE_MES = {v: k.capitalize() for k, v in MESES_ES.items()}

MESES_EN = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

TERRITORIO_ES_EN = {
    "norte": "North America",
    "norteamerica": "North America",
    "north america": "North America",
    "europa": "Europe",
    "europe": "Europe",
    "oceania": "Oceania",
}
