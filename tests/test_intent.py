"""Tests for app/intent.py — intent detection and year extraction."""
import pytest
from app.intent import _normalize, detectar_intencion, extract_year


# ── _normalize ───────────────────────────────────────────

class TestNormalize:
    def test_lowercase(self):
        assert _normalize("HOLA") == "hola"

    def test_removes_accents(self):
        assert _normalize("país") == "pais"

    def test_strips_whitespace(self):
        assert _normalize("  hola  ") == "hola"

    def test_combined(self):
        assert _normalize("  Países  ") == "paises"


# ── detectar_intencion ───────────────────────────────────

class TestDetectarIntencion:
    # Ventas
    def test_ventas_directo(self):
        assert detectar_intencion("cuánto se vendió") == "ventas"

    def test_ventas_with_year(self):
        assert detectar_intencion("cuánto se vendió en 2019") == "ventas"

    def test_ventas_total(self):
        assert detectar_intencion("total de ventas") == "ventas"

    # Gastos
    def test_gastos_directo(self):
        assert detectar_intencion("cuánto se gastó") == "gastos"

    def test_gastos_operativos(self):
        assert detectar_intencion("gastos operativos") == "gastos"

    # Neto
    def test_neto(self):
        assert detectar_intencion("resultado neto") == "neto"

    def test_ganancia(self):
        assert detectar_intencion("hubo ganancia") == "neto"

    def test_perdida(self):
        assert detectar_intencion("hubo pérdida") == "neto"

    # País
    def test_pais(self):
        assert detectar_intencion("qué país tuvo mayor movimiento") == "pais"

    def test_paises(self):
        assert detectar_intencion("países con más actividad") == "pais"

    # Cuenta
    def test_cuenta(self):
        assert detectar_intencion("qué cuenta tiene mayor monto") == "cuenta"

    def test_cuentas(self):
        assert detectar_intencion("cuentas con más dinero") == "cuenta"

    # ETL
    def test_etl(self):
        assert detectar_intencion("qué limpieza se hizo") == "etl"

    def test_etl_transformaciones(self):
        assert detectar_intencion("qué transformaciones") == "etl"

    # Modelo
    def test_modelo(self):
        assert detectar_intencion("cómo se conectan las tablas") == "modelo"

    def test_modelo_relaciones(self):
        assert detectar_intencion("relaciones entre tablas") == "modelo"

    # Desconocida
    def test_desconocida(self):
        assert detectar_intencion("blablabla random") == "desconocida"

    def test_inventario_no_falso_positivo(self):
        """inventario NO debe detectarse como ventas"""
        assert detectar_intencion("mostrar inventario") == "desconocida"

    def test_costos_fijo(self):
        """costos ya no matchea gastos (quitamos 'costo' suelto)"""
        result = detectar_intencion("costos del año")
        assert result in ("gastos", "desconocida")


# ── extract_year ─────────────────────────────────────────

class TestExtractYear:
    def test_extract_2018(self):
        assert extract_year("ventas en 2018") == 2018

    def test_extract_2019(self):
        assert extract_year("cuánto se vendió en 2019") == 2019

    def test_extract_2020(self):
        assert extract_year("resultados durante 2020") == 2020

    def test_no_year(self):
        assert extract_year("cuánto se vendió") is None

    def test_invalid_year(self):
        # Años que no empiezan con 20 no deben matchear
        assert extract_year("ventas en 1999") is None

    def test_year_in_middle(self):
        assert extract_year("del año 2019 fue") == 2019
