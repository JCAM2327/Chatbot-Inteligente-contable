import sys
from pathlib import Path

import pytest
import pandas as pd

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data_processing import (
    _parse_amount,
    load_csv,
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
)
from app.intent import _normalize, detectar_intencion, extract_year


# ── Shared fixtures ─────────────────────────────────────

@pytest.fixture(scope="session")
def loaded_data():
    """Load real data once for the entire test session."""
    df, etl_stats, merges = load_data()
    return df, etl_stats, merges


@pytest.fixture(scope="session")
def df(loaded_data):
    return loaded_data[0]


@pytest.fixture(scope="session")
def etl_stats(loaded_data):
    return loaded_data[1]


@pytest.fixture(scope="session")
def merges(loaded_data):
    return loaded_data[2]


@pytest.fixture
def sample_gl():
    """Small synthetic GL DataFrame for unit tests."""
    return pd.DataFrame({
        "EntryNo": [1, 2, 3, 4, 5],
        "Date": pd.to_datetime(["2019-01-15", "2019-06-20", "2020-03-10", "2020-11-05", "2019-08-01"]),
        "Territory_key": [1, 1, 2, 2, 3],
        "Account_key": [100, 200, 100, 300, 200],
        "Details": ["Sale A", "Expense B", "Sale C", "Cost D", "Sale E"],
        "Amount": [1000.0, -500.0, 2000.0, -300.0, 1500.0],
    })


@pytest.fixture
def sample_coa():
    return pd.DataFrame({
        "Account_key": [100, 200, 300],
        "Report": ["Profit and Loss", "Profit and Loss", "Profit and Loss"],
        "Class": ["Revenue", "Expense", "Expense"],
        "SubClass": ["Sales", "Operating Expenses", "Cost of Sales"],
        "SubClass2": ["", "", ""],
        "Account": ["Sales Revenue", "Rent Expense", "COGS"],
        "SubAccount": ["Product Sales", "Office Rent", "Materials"],
    })


@pytest.fixture
def sample_territory():
    return pd.DataFrame({
        "Territory_key": [1, 2, 3],
        "Country": ["Argentina", "Chile", "Uruguay"],
        "Region": ["LATAM", "LATAM", "LATAM"],
    })
