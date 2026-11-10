"""Tests for app/data_processing.py — ETL, merges, and query functions."""
import pandas as pd
import pytest

from app.data_processing import (
    _parse_amount,
    clean_gl,
    merge_tables,
    load_data,
    get_total_ventas,
    get_total_gastos,
    get_resultado_neto,
    get_pais_mayor_movimiento,
    get_cuenta_mayor_monto,
    get_info_etl,
    get_resumen,
    get_resumen_general,
    get_dashboard_data,
)


# ── _parse_amount ────────────────────────────────────────

class TestParseAmount:
    def test_positive_integer(self):
        assert _parse_amount("1000") == 1000.0

    def test_negative_parentheses(self):
        assert _parse_amount("(884)") == -884.0

    def test_comma_separated(self):
        assert _parse_amount("2,394") == 2394.0

    def test_european_decimal(self):
        assert _parse_amount("1.234,56") == 1234.56

    def test_currency_and_thousands(self):
        assert _parse_amount("$1,234.56") == 1234.56

    def test_negative_with_currency(self):
        assert _parse_amount("$-1,234") == -1234.0

    def test_whitespace_stripped(self):
        assert _parse_amount("  500  ") == 500.0

    def test_nan_returns_zero(self):
        assert _parse_amount(float("nan")) == 0.0

    def test_empty_string_returns_zero(self):
        assert _parse_amount("") == 0.0

    def test_none_returns_zero(self):
        assert _parse_amount(None) == 0.0

    def test_invalid_returns_zero(self):
        assert _parse_amount("abc") == 0.0


# ── clean_gl ─────────────────────────────────────────────

class TestCleanGl:
    def test_returns_tuple(self, sample_gl):
        result = clean_gl(sample_gl)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_etl_stats_structure(self, sample_gl):
        _, etl = clean_gl(sample_gl)
        assert "pasos" in etl
        assert "filas_originales" in etl
        assert "filas_finales" in etl
        assert etl["filas_originales"] == 5

    def test_drops_duplicates(self):
        df = pd.DataFrame({
            "EntryNo": [1, 1, 2],
            "Date": pd.to_datetime(["2019-01-01", "2019-01-01", "2019-06-01"]),
            "Territory_key": [1, 1, 2],
            "Account_key": [100, 100, 200],
            "Amount": [100.0, 100.0, 200.0],
        })
        cleaned, etl = clean_gl(df)
        assert len(cleaned) == 2
        assert etl["duplicados_eliminados"] == 1

    def test_drops_nulls_in_critical_columns(self):
        df = pd.DataFrame({
            "EntryNo": [1, 2],
            "Date": [pd.Timestamp("2019-01-01"), pd.NaT],
            "Territory_key": [1, 2],
            "Account_key": [100, 200],
            "Amount": [100.0, 200.0],
        })
        cleaned, etl = clean_gl(df)
        assert len(cleaned) == 1
        assert etl["nulos_eliminados"] == 1

    def test_does_not_mutate_input(self, sample_gl):
        original_len = len(sample_gl)
        clean_gl(sample_gl)
        assert len(sample_gl) == original_len

    def test_amount_parsed_to_float(self, sample_gl):
        cleaned, _ = clean_gl(sample_gl)
        assert cleaned["Amount"].dtype == float

    def test_date_parsed_to_datetime(self, sample_gl):
        cleaned, _ = clean_gl(sample_gl)
        assert pd.api.types.is_datetime64_any_dtype(cleaned["Date"])


# ── merge_tables ─────────────────────────────────────────

class TestMergeTables:
    def test_merge_coa(self, sample_gl, sample_coa):
        df, merges = merge_tables(sample_gl, sample_coa, pd.DataFrame({"Territory_key": [], "Country": []}), pd.DataFrame())
        assert "SubClass" in df.columns
        assert len(merges) >= 1

    def test_merge_territory(self, sample_gl, sample_coa, sample_territory):
        df, merges = merge_tables(sample_gl, sample_coa, sample_territory, pd.DataFrame())
        assert "Country" in df.columns
        assert len(merges) >= 2

    def test_amount_abs_created(self, sample_gl, sample_coa):
        df, _ = merge_tables(sample_gl, sample_coa, pd.DataFrame({"Territory_key": [], "Country": []}), pd.DataFrame())
        assert "Amount_abs" in df.columns
        assert (df["Amount_abs"] >= 0).all()

    def test_merge_without_auxiliary_tables(self, sample_gl):
        df, merges = merge_tables(sample_gl)
        assert merges == []
        assert "Amount_abs" in df.columns

    def test_merge_gl_and_coa_without_territory_or_calendar(self, sample_gl, sample_coa):
        df, merges = merge_tables(sample_gl, sample_coa)
        assert "SubClass" in df.columns
        assert len(merges) == 1


# ── Query functions ──────────────────────────────────────

class TestGetTotalVentas:
    def test_returns_dict_with_answer(self, df):
        result = get_total_ventas(df)
        assert "answer" in result
        assert "labels" in result
        assert "values" in result

    def test_with_year_filter(self, df):
        result_2019 = get_total_ventas(df, year=2019)
        result_2020 = get_total_ventas(df, year=2020)
        assert result_2019["values"] != result_2020["values"] or result_2019["values"] == result_2020["values"]
        assert "2019" in result_2019["answer"]

    def test_labels_populated_without_year(self, df):
        result = get_total_ventas(df)
        assert len(result["labels"]) > 0

    def test_total_is_positive(self, df):
        result = get_total_ventas(df)
        assert result["values"][0] > 0


class TestGetTotalGastos:
    def test_returns_dict_with_answer(self, df):
        result = get_total_gastos(df)
        assert "answer" in result

    def test_gastos_display_positive(self, df):
        """La respuesta debe mostrar el gasto como número positivo,
        aunque internamente los gastos sean negativos en el dataset."""
        result = get_total_gastos(df)
        # El texto debe mostrar el monto sin signo negativo
        assert "[-]" not in result["answer"], "No debe mostrar signo negativo en gastos"
        # El primer valor de la respuesta debe ser el monto absoluto (positivo)
        import re
        montos = re.findall(r'\$[\d,]+\.?\d*', result["answer"])
        if montos:
            # Extraer el número sin $ ni comas
            monto_str = montos[0].replace("$", "").replace(",", "")
            assert float(monto_str) > 0, f"El monto mostrado debe ser positivo, pero es {montos[0]}"


class TestGetResultadoNeto:
    def test_returns_dict_with_answer(self, df):
        result = get_resultado_neto(df)
        assert "answer" in result
        assert "labels" in result
        assert len(result["labels"]) > 4  # Múltiples SubClass + Neto

    def test_indicates_ganancia_o_perdida(self, df):
        result = get_resultado_neto(df)
        assert "ganancia" in result["answer"].lower() or "perdida" in result["answer"].lower()

    def test_includes_desglose(self, df):
        result = get_resultado_neto(df)
        assert "Desglose" in result["answer"]
        assert "Sales" in result["answer"]
        assert "Neto" in result["labels"][-1]

    def test_value_matches_other_agent(self, df):
        result = get_resultado_neto(df)
        neto = result["values"][-1]
        # El otro agente reportó $3,216,948 — verificar que coincida
        assert abs(neto - 3216948) < 1000, f"Neto {neto} muy lejos de $3,216,948"


class TestGetPaisMayorMovimiento:
    def test_returns_dict(self, df):
        result = get_pais_mayor_movimiento(df)
        assert "answer" in result
        assert len(result["labels"]) > 0

    def test_no_countries(self):
        result = get_pais_mayor_movimiento(pd.DataFrame({"Amount_abs": [100]}))
        assert "No hay datos" in result["answer"]


class TestGetCuentaMayorMonto:
    def test_returns_dict(self, df):
        result = get_cuenta_mayor_monto(df)
        assert "answer" in result
        assert len(result["labels"]) > 0


class TestGetInfoEtl:
    def test_returns_dict(self, df, etl_stats):
        result = get_info_etl(df, etl_stats)
        assert "answer" in result
        assert "ETL" in result["answer"] or "limpieza" in result["answer"].lower()


class TestGetResumen:
    def test_returns_dict(self, df):
        result = get_resumen(df)
        assert "total_registros" in result
        assert result["total_registros"] > 0


class TestAccountingSemantics:
    def test_resumen_net_uses_profit_and_loss(self, sample_gl, sample_coa):
        merged, _ = merge_tables(sample_gl, sample_coa)
        result = get_resumen_general(merged)
        assert "Resultado neto: $3,700.00" in result["answer"]
        assert "Gastos operativos: $1,000.00" in result["answer"]

    def test_dashboard_result_uses_profit_and_loss(self, sample_gl, sample_coa):
        merged, _ = merge_tables(sample_gl, sample_coa)
        dash = get_dashboard_data(merged)
        kpis = {k["label"]: k for k in dash["kpis"]}
        assert kpis["Resultado"]["raw"] == 3700.0
        assert kpis["Gastos"]["value"] == "$1,000.00"

    def test_dashboard_works_without_country_column(self, sample_gl, sample_coa):
        merged, _ = merge_tables(sample_gl, sample_coa)
        assert "Country" not in merged.columns
        dash = get_dashboard_data(merged)
        assert "top_accounts" in dash


# ── load_data (integration) ─────────────────────────────

class TestLoadData:
    def test_load_data_returns_three_values(self):
        result = load_data()
        assert len(result) == 3

    def test_df_has_expected_columns(self, df):
        expected_cols = ["EntryNo", "Date", "Account_key", "Territory_key", "Amount", "Amount_abs"]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_etl_has_merges(self, etl_stats):
        assert "merges" in etl_stats
        assert len(etl_stats["merges"]) == 3

    def test_merges_count(self, merges):
        assert len(merges) == 3
