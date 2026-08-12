import logging
import numpy as np
import pandas as pd
from pathlib import Path
from app.constants import MESES_ES, NOMBRE_MES

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

# Validación de calidad de datos
REQUIRED_GL_COLUMNS = {"EntryNo", "Date", "Territory_key", "Account_key", "Amount"}


# ── Helpers ──────────────────────────────────────────────

def _parse_amount(value) -> float:
    """
    Convierte formato contable a float.
    '(884)' → -884.0
    '2,394 ' → 2394.0
    """
    if pd.isna(value):
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("() ").replace(",", "")
    try:
        num = float(s)
        return -num if negative else num
    except ValueError:
        logger.warning("No se pudo parsear Amount: '%s'", s)
        return 0.0


# ── Carga y limpieza (reutilizables para Fase 4) ────────

def load_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    return pd.read_csv(path)


def clean_gl(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Limpieza y transformación del GL con tracking de stats ETL."""
    df = df.copy()  # Evitar mutar el DataFrame original

    etl = {
        "pasos": [],
        "filas_originales": len(df),
        "columnas_originales": len(df.columns),
        "duplicados_eliminados": 0,
        "nulos_eliminados": 0,
        "columnas_eliminadas": 0,
        "tipos_convertidos": [],
        "ejemplos_transformacion": [],
    }

    # 1. Renombrar columna Amount (tiene espacio)
    for c in df.columns:
        if c.strip() == "Amount":
            df = df.rename(columns={c: "Amount"})
            break
    etl["pasos"].append("Renombrar columna 'Amount ' → 'Amount'")

    # 2. Eliminar columnas vacías
    col_count_antes = len(df.columns)
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    df = df.dropna(axis=1, how="all")
    etl["columnas_eliminadas"] = col_count_antes - len(df.columns)
    if etl["columnas_eliminadas"] > 0:
        etl["pasos"].append(f"Eliminar {etl['columnas_eliminadas']} columnas vacías")

    # 3. Parsear Amount (vectorizado en vez de apply)
    if "Amount" in df.columns:
        ejemplo_antes = str(df["Amount"].dropna().iloc[0]) if len(df) > 0 else "N/A"
        df["Amount"] = df["Amount"].map(_parse_amount)
        ejemplo_despues = str(df["Amount"].iloc[0]) if len(df) > 0 else "N/A"
        etl["pasos"].append("Convertir Amount de formato contable a float")
        etl["tipos_convertidos"].append({"columna": "Amount", "antes": "string", "despues": "float"})
        etl["ejemplos_transformacion"].append({"columna": "Amount", "antes": ejemplo_antes, "despues": ejemplo_despues})

    # 4. Parsear Date
    if "Date" in df.columns:
        ejemplo_antes = str(df["Date"].dropna().iloc[0]) if len(df) > 0 else "N/A"
        df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y", errors="coerce")
        ejemplo_despues = str(df["Date"].iloc[0]) if len(df) > 0 else "N/A"
        etl["pasos"].append("Convertir Date de 'MM/DD/YY' a datetime")
        etl["tipos_convertidos"].append({"columna": "Date", "antes": "string", "despues": "datetime"})
        etl["ejemplos_transformacion"].append({"columna": "Date", "antes": ejemplo_antes, "despues": ejemplo_despues})

    # 5. Convertir tipos
    for col in ["Account_key", "Territory_key"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            etl["pasos"].append(f"Convertir {col} de string a Int64")
            etl["tipos_convertidos"].append({"columna": col, "antes": "string", "despues": "Int64"})

    # 6. Eliminar duplicados
    filas_antes = len(df)
    df = df.drop_duplicates()
    etl["duplicados_eliminados"] = filas_antes - len(df)
    etl["pasos"].append(f"Eliminar duplicados: {filas_antes} → {len(df)} filas ({etl['duplicados_eliminados']} eliminadas)")

    # 7. Tratar nulos en columnas críticas (incluyendo Amount)
    critical_cols = [c for c in ["Date", "Account_key", "Territory_key", "Amount"] if c in df.columns]
    filas_antes = len(df)
    df = df.dropna(subset=critical_cols)
    etl["nulos_eliminados"] = filas_antes - len(df)
    if etl["nulos_eliminados"] > 0:
        etl["pasos"].append(f"Eliminar filas con nulos en columnas críticas: {etl['nulos_eliminados']} eliminadas")
    else:
        etl["pasos"].append("Tratamiento de nulos: no se encontraron nulos en columnas críticas")

    etl["filas_finales"] = len(df)
    etl["columnas_finales"] = len(df.columns)

    return df, etl


def merge_tables(gl, coa, terr, cal) -> tuple[pd.DataFrame, list]:
    """Merge GL con chart_of_accounts, territory y calendar."""
    merges = []

    # Merge GL ━━🔗━━ chart_of_accounts
    df = pd.merge(
        gl, coa, on="Account_key", how="left",
        validate="m:1", indicator=True,
    )
    merges.append({
        "from": "GL", "to": "chart_of_accounts",
        "column": "Account_key", "filas": len(df),
        "unmatched": int((df["_merge"] != "both").sum()),
    })
    df.drop(columns=["_merge"], inplace=True)

    # Merge GL ━━🔗━━ territory
    df = pd.merge(
        df, terr, on="Territory_key", how="left",
        validate="m:1", indicator=True,
    )
    merges.append({
        "from": "GL", "to": "territory",
        "column": "Territory_key", "filas": len(df),
        "unmatched": int((df["_merge"] != "both").sum()),
    })
    df.drop(columns=["_merge"], inplace=True)

    # Merge GL ━━🔗━━ calendar (sin validate m:1 porque fechas NaT se duplican)
    if "Date" in df.columns and "Date" in cal.columns:
        cal_copy = cal.copy()
        cal_copy["Date"] = pd.to_datetime(cal_copy["Date"], format="%m/%d/%y", errors="coerce")
        df = pd.merge(
            df, cal_copy, on="Date", how="left",
            indicator=True,
        )
        merges.append({
            "from": "GL", "to": "calendar",
            "column": "Date", "filas": len(df),
            "unmatched": int((df["_merge"] != "both").sum()),
        })
        df.drop(columns=["_merge"], inplace=True)

    # Columna calculada: valor absoluto para mostrar montos legibles
    if "Amount" in df.columns:
        df["Amount_abs"] = df["Amount"].abs()

    return df, merges


def load_data() -> tuple[pd.DataFrame, dict, list]:
    gl = load_csv("GL.csv")
    coa = load_csv("chart_of_accounts.csv")
    terr = load_csv("territory.csv")
    cal = load_csv("calendar.csv")

    gl, etl_stats = clean_gl(gl)
    df, merges = merge_tables(gl, coa, terr, cal)

    etl_stats["merges"] = merges
    etl_stats["columnas_calculadas"] = ["Amount_abs = Amount.abs()"]

    return df, etl_stats, merges


# ── Funciones de consulta ───────────────────────────────

def _query_by_subclass(df, subclass: str, label: str, year=None) -> dict:
    mask = df["SubClass"] == subclass
    if year is not None and "Year" in df.columns:
        mask = mask & (df["Year"] == year)
    subset = df.loc[mask].copy()
    total = subset["Amount"].sum()

    labels, values = [], []
    if year:
        labels, values = [str(year)], [round(total, 2)]
    elif "Year" in df.columns:
        grouped = subset.groupby("Year", observed=True)["Amount"].sum()
        labels = [str(y) for y in grouped.index]
        values = [round(v, 2) for v in grouped.values]

    year_text = f" en {year}" if year else ""
    # Mostrar monto absoluto (gastos vienen como negativos en el dataset)
    display_total = abs(total)
    return {"answer": f"El total de {label}{year_text} fue ${display_total:,.2f}", "labels": labels, "values": values}


def get_total_ventas(df, year=None) -> dict:
    return _query_by_subclass(df, "Sales", "ventas", year)


def get_total_gastos(df, year=None) -> dict:
    return _query_by_subclass(df, "Operating Expenses", "gastos operativos", year)


def get_resultado_neto(df, year=None) -> dict:
    """Resultado neto = suma de todos los movimientos de Profit and Loss, con desglose por SubClass."""
    mask = df["Report"] == "Profit and Loss"
    if year is not None and "Year" in df.columns:
        mask = mask & (df["Year"] == year)
    subset = df.loc[mask].copy()

    neto = subset["Amount"].sum()

    # Desglose automático por SubClass
    breakdown = subset.groupby("SubClass", observed=True)["Amount"].sum().sort_values()

    labels = [str(c) for c in breakdown.index] + ["Neto"]
    values = [round(v, 2) for v in breakdown.values] + [round(neto, 2)]

    year_text = f" en {year}" if year else ""
    resultado_tipo = "✅ Ganancia" if neto >= 0 else "❌ Pérdida"
    texto = f"**Resultado neto{year_text}:** ${neto:,.2f} ({resultado_tipo})\n\n"
    texto += "**Desglose por categoría:**\n\n"
    texto += "| Categoría | Monto |\n"
    texto += "|---|---|\n"
    for subclase, monto in breakdown.items():
        texto += f"| {subclase} | ${monto:,.2f} |\n"
    texto += f"| **Neto** | **${neto:,.2f}** |\n"

    return {"answer": texto, "labels": labels, "values": values}


def _query_top_by_group(df, group_col: str, label_singular: str, top_n: int | None = None, asc: bool = False) -> dict:
    """Agrupa por columna, suma Amount_abs, ordena y devuelve top/bottom."""
    if group_col not in df.columns:
        cols_list = ", ".join(df.columns)
        return {"answer": f"No hay datos de {label_singular} disponibles. Columnas: {cols_list}", "labels": [], "values": []}

    grouped = (
        df.groupby(group_col, observed=True)["Amount_abs"]
        .sum()
        .sort_values(ascending=asc)
    )
    labels_all = [str(c) for c in grouped.index]
    values_all = [round(v, 2) for v in grouped.values]

    if top_n:
        labels = labels_all[:top_n]
        values = values_all[:top_n]
    else:
        labels = labels_all
        values = values_all

    extreme = grouped.idxmax() if not asc else grouped.idxmin()
    extreme_val = grouped.max() if not asc else grouped.min()
    adverbio = "mayor" if not asc else "menor"

    return {
        "answer": f"El/la {label_singular} con {adverbio} movimiento total es '{extreme}' con ${extreme_val:,.2f}",
        "labels": labels,
        "values": values,
    }


def get_pais_mayor_movimiento(df) -> dict:
    return _query_top_by_group(df, "Country", "país")


def get_pais_menor_movimiento(df) -> dict:
    return _query_top_by_group(df, "Country", "país", asc=True)


def get_cuenta_mayor_monto(df) -> dict:
    return _query_top_by_group(df, "SubAccount", "cuenta", top_n=10)


def get_cuenta_menor_monto(df) -> dict:
    return _query_top_by_group(df, "SubAccount", "cuenta", top_n=10, asc=True)


def get_info_etl(df, etl_stats) -> dict:
    pasos = etl_stats.get("pasos", [])
    merges = etl_stats.get("merges", [])
    ejemplos = etl_stats.get("ejemplos_transformacion", [])

    rows_orig = etl_stats.get('filas_originales', 0)
    rows_final = etl_stats.get('filas_finales', 0)
    cols_orig = etl_stats.get('columnas_originales', 0)
    cols_final = etl_stats.get('columnas_finales', 0)
    dups = etl_stats.get('duplicados_eliminados', 0)
    nulls = etl_stats.get('nulos_eliminados', 0)
    cols_elim = etl_stats.get('columnas_eliminadas', 0)

    answer = "**Proceso de limpieza y transformación (ETL):**\n\n"
    answer += "**📊 Dimensiones:**\n"
    answer += f"| Métrica | Valor |\n"
    answer += "|---|---|\n"
    answer += f"| Filas originales | {rows_orig:,} |\n"
    answer += f"| Filas finales | {rows_final:,} |\n"
    answer += f"| Columnas originales | {cols_orig} |\n"
    answer += f"| Columnas finales | {cols_final} |\n"
    answer += f"| Duplicados eliminados | {dups} |\n"
    answer += f"| Nulos eliminados | {nulls} |\n"
    answer += f"| Columnas vacías eliminadas | {cols_elim} |\n\n"

    answer += "**Pasos realizados:**\n"
    for i, paso in enumerate(pasos, 1):
        answer += f"  {i}. {paso}\n"
    if merges:
        answer += f"\n**🔗 Merges realizados:** {len(merges)}\n"
        for m in merges:
            answer += f"  • {m['from']} ⟷ {m['to']} (por _{m['column']}_)\n"
    if etl_stats.get("columnas_calculadas"):
        answer += f"\n**📐 Columnas calculadas:** {', '.join(etl_stats['columnas_calculadas'])}\n"
    if ejemplos:
        answer += "\n**Ejemplos de transformación:**\n"
        for ej in ejemplos:
            answer += f"  • _{ej['columna']}_: `{ej['antes']}` → `{ej['despues']}`\n"

    labels = ["Filas orig.", "Filas finales", "Duplicados", "Nulos", "Cols elim."]
    values = [
        etl_stats.get("filas_originales", 0),
        etl_stats.get("filas_finales", 0),
        etl_stats.get("duplicados_eliminados", 0),
        etl_stats.get("nulos_eliminados", 0),
        etl_stats.get("columnas_eliminadas", 0),
    ]
    return {"answer": answer, "labels": labels, "values": values}


# ── Fase 2: Detección de relaciones ─────────────────────

def _clean_col_name(name: str) -> str:
    return name.strip().lower()


def detectar_relaciones(dataframes: dict[str, pd.DataFrame]) -> dict:
    """Detecta relaciones entre tablas buscando columnas compartidas con key-like characteristics."""
    relaciones = []
    tablas = list(dataframes.keys())

    cols_norm = {}
    for t in tablas:
        cols_norm[t] = {_clean_col_name(c): c for c in dataframes[t].columns}

    for i, t1 in enumerate(tablas):
        for t2 in tablas[i + 1:]:
            comunes = set(cols_norm[t1].keys()) & set(cols_norm[t2].keys())
            for col_norm in comunes:
                if "unnamed" in col_norm or not col_norm:
                    continue
                col1 = cols_norm[t1][col_norm]
                col2 = cols_norm[t2][col_norm]
                u1 = dataframes[t1][col1].nunique()
                u2 = dataframes[t2][col2].nunique()
                t1_len = len(dataframes[t1])
                t2_len = len(dataframes[t2])

                is_key1 = u1 < t1_len or "key" in col_norm
                is_key2 = u2 < t2_len or "key" in col_norm

                if is_key1 and is_key2:
                    rel_type = "one-to-one" if u1 == u2 else "many-to-one"
                    relaciones.append({
                        "from": t1, "to": t2, "column": col1,
                        "type": rel_type, "unique_in_from": u1, "unique_in_to": u2,
                    })

    return {
        "relaciones": relaciones,
        "tablas": tablas,
        "columnas_por_tabla": {
            t: [c.strip() for c in dataframes[t].columns if "unnamed" not in c.lower()]
            for t in tablas
        },
    }


# ── Resumen ─────────────────────────────────────────────

def get_resumen(df) -> dict:
    """Resumen estadístico del dataset para debugging y overview."""
    result = {"total_registros": len(df)}
    if "Country" in df.columns:
        result["total_paises"] = df["Country"].nunique()
    if "SubAccount" in df.columns:
        result["total_cuentas"] = df["SubAccount"].nunique()
    if "Date" in df.columns:
        result["fecha_desde"] = str(df["Date"].min().date())
        result["fecha_hasta"] = str(df["Date"].max().date())
    if "Year" in df.columns:
        result["anos"] = sorted(df["Year"].dropna().unique().tolist())
    if "Country" in df.columns:
        result["paises"] = sorted(df["Country"].dropna().unique().tolist())
    return result


def get_resumen_general(df) -> dict:
    """Resumen general tipo 'panorama' para el usuario final."""
    total = len(df)
    monto = df["Amount"].sum()
    monto_abs = df["Amount_abs"].sum()
    lineas = [
        f"📋 **Resumen General**",
        f"",
        f"• Total de transacciones: {total:,}",
        f"• Monto total movimiento: ${monto:,.2f}",
        f"• Volumen absoluto: ${monto_abs:,.2f}",
    ]
    if "Country" in df.columns:
        paises = df["Country"].nunique()
        lineas.append(f"• Territorios registrados: {paises}")
    if "SubAccount" in df.columns:
        cuentas = df["SubAccount"].nunique()
        lineas.append(f"• Cuentas contables únicas: {cuentas}")
    if "Date" in df.columns:
        lineas.append(f"• Período: {df['Date'].min().date()} → {df['Date'].max().date()}")
    if "SubClass" in df.columns:
        sales = df.loc[df["SubClass"] == "Sales", "Amount"].sum()
        expenses = df.loc[df["SubClass"] == "Operating Expenses", "Amount"].sum()
        neto = sales + expenses
        lineas.append(f"• Ventas totales: ${sales:,.2f}")
        lineas.append(f"• Gastos totales: ${expenses:,.2f}")
        lineas.append(f"• Resultado neto: ${neto:,.2f}")
    return {
        "answer": "\n".join(lineas),
        "labels": ["Transacciones", "Monto total", "Volumen abs"],
        "values": [total, round(monto, 2), round(monto_abs, 2)],
    }


def get_cuentas_mas_usadas(df, top_n: int = 5) -> dict:
    """Cuentas con más transacciones (por cantidad, no por monto)."""
    if "SubAccount" not in df.columns:
        return {"answer": "No hay datos de cuentas", "labels": [], "values": []}

    counts = df["SubAccount"].value_counts().head(top_n)
    labels = [str(c) for c in counts.index]
    values = [int(v) for v in counts.values]
    return {
        "answer": f"Las {top_n} cuentas más utilizadas son:\n" + "\n".join(
            f"  {i+1}. {c} — {v} transacciones" for i, (c, v) in enumerate(zip(labels, values))
        ),
        "labels": labels,
        "values": values,
    }


# ── Nuevas consultas (del análisis del PDF) ────────────

def get_total_por_mes(df, month_num: int, year: int | None = None, subclass: str | None = None) -> dict:
    """Total de ventas o gastos para un mes específico."""
    mask = df["Date"].dt.month == month_num
    if year is not None and "Year" in df.columns:
        mask = mask & (df["Year"] == year)
    if subclass:
        mask = mask & (df["SubClass"] == subclass)

    subset = df.loc[mask]
    total = subset["Amount"].sum()
    count = len(subset)
    mes_nombre = NOMBRE_MES.get(month_num, f"Mes {month_num}")

    year_text = f" {year}" if year else ""
    subclass_text = f" de {subclass.lower()}" if subclass else ""

    return {
        "answer": f"El total{subclass_text} en {mes_nombre}{year_text} fue ${total:,.2f} ({count} transacciones)",
        "labels": [mes_nombre],
        "values": [round(total, 2)],
    }


def get_por_territorio(df, territorio_en: str, year: int | None = None) -> dict:
    """Total de movimientos para un territorio/región específico."""
    mask = (df["Country"] == territorio_en) | (df["Region"] == territorio_en)
    if year is not None and "Year" in df.columns:
        mask = mask & (df["Year"] == year)

    subset = df.loc[mask]
    if len(subset) == 0:
        return {"answer": f"No se encontraron datos para '{territorio_en}'", "labels": [], "values": []}

    ventas = subset.loc[subset["SubClass"] == "Sales", "Amount"].sum()
    gastos = subset.loc[subset["SubClass"] == "Operating Expenses", "Amount"].sum()
    total = subset["Amount_abs"].sum()

    year_text = f" en {year}" if year else ""
    return {
        "answer": (
            f"Movimientos en {territorio_en}{year_text}:\n"
            f"  • Ventas: ${ventas:,.2f}\n"
            f"  • Gastos: ${gastos:,.2f}\n"
            f"  • Movimiento total: ${total:,.2f}"
        ),
        "labels": ["Ventas", "Gastos"],
        "values": [round(ventas, 2), round(gastos, 2)],
    }


# ── Fase 1: Diagnóstico ETL ─────────────────────────────

DATE_FORMATS_TO_TRY = [
    ("%m/%d/%y", "MM/DD/YY (americano)"),
    ("%d/%m/%y", "DD/MM/YY (europeo)"),
    ("%Y-%m-%d", "YYYY-MM-DD (ISO)"),
    ("%m/%d/%Y", "MM/DD/YYYY"),
    ("%d/%m/%Y", "DD/MM/YYYY"),
]

ROLE_PATTERNS = [
    ({"Amount", "Date", "Account_key"}, "GL", "Libro Mayor (transaccional)"),
    ({"Date", "Account", "Debit", "Credit"}, "GL", "Libro Mayor (formato Débito/Crédito)"),
    ({"Account_key", "Report", "SubClass"}, "chart_of_accounts", "Plan de Cuentas"),
    ({"Account_Code", "Account_Name", "Account_Type"}, "chart_of_accounts", "Plan de Cuentas"),
    ({"Territory_key", "Country", "Region"}, "territory", "Territorios"),
    ({"Date", "Year", "Quarter", "Month"}, "calendar", "Calendario"),
]


def _try_date_formats(series: pd.Series) -> dict:
    """Prueba múltiples formatos de fecha y devuelve el que mejor funciona."""
    sample = series.dropna().astype(str).head(100)
    best = {"format": None, "name": None, "parsed": 0, "failed": 0}
    for fmt, fmt_name in DATE_FORMATS_TO_TRY:
        parsed = pd.to_datetime(sample, format=fmt, errors="coerce")
        ok = parsed.notna().sum()
        if ok > best["parsed"]:
            best = {"format": fmt, "name": fmt_name, "parsed": int(ok), "failed": int(len(sample) - ok)}
    return best


def _detect_role(columns: list[str]) -> dict:
    """Detecta el rol de un archivo según sus columnas."""
    col_set = set(c.strip().lower() for c in columns)
    for expected, role_id, role_name in ROLE_PATTERNS:
        expected_norm = set(e.lower() for e in expected)
        if expected_norm.issubset(col_set):
            return {"id": role_id, "name": role_name}
    return {"id": "unknown", "name": "Tabla desconocida"}


def _check_amount_format(series: pd.Series) -> dict:
    """Detecta el formato de montos en una columna."""
    sample = series.dropna().astype(str).head(200)
    has_parens = sample.str.contains(r"^\s*\(", na=False).sum()
    has_commas = sample.str.contains(r",", na=False).sum()
    has_dollar = sample.str.contains(r"\$", na=False).sum()
    return {
        "has_parentheses": int(has_parens > 0),
        "has_commas": int(has_commas > 0),
        "has_dollar_sign": int(has_dollar > 0),
        "format_type": "accounting (parentheses)" if has_parens > 10 else "plain" if has_parens == 0 else "mixed",
    }


def diagnose_csv(filepath_or_df: str | pd.DataFrame, filename: str = "unknown.csv") -> dict:
    """Analiza un CSV y devuelve diagnóstico detallado SIN limpiar."""
    if isinstance(filepath_or_df, str):
        try:
            df = pd.read_csv(filepath_or_df)
        except Exception as e:
            return {"filename": filename, "status": "error", "error": str(e), "issues": []}
    else:
        df = filepath_or_df.copy()

    issues = []
    columns = list(df.columns)
    col_set = set(c.strip().lower() for c in columns)

    # 1. Columnas vacías (Unnamed)
    unnamed = [c for c in columns if "unnamed" in c.lower()]
    if unnamed:
        issues.append({
            "severity": "warning", "icon": "⚠️",
            "title": f"Columnas vacías detectadas ({len(unnamed)})",
            "detail": f"Se encontraron {len(unnamed)} columnas sin nombre. Pueden eliminarse.",
            "columns": unnamed,
        })

    # 2. Detectar rol del archivo
    role = _detect_role(columns)

    # 3. Tipos de datos inferidos
    dtypes = {}
    for c in columns:
        col = df[c]
        if pd.api.types.is_datetime64_any_dtype(col):
            inferred = "datetime"
        elif pd.api.types.is_numeric_dtype(col):
            inferred = "numeric"
        elif pd.api.types.is_bool_dtype(col):
            inferred = "bool"
        else:
            inferred = "string"
        dtypes[c] = inferred

    # 4. Nulos por columna
    nulls = {}
    for c in columns:
        n = int(df[c].isna().sum())
        if n > 0:
            nulls[c] = n

    if nulls:
        critical_null_cols = [c for c in nulls if c.lower() in ("date", "amount", "account_key", "territory_key", "account", "debit", "credit")]
        severity = "critical" if critical_null_cols else "warning"
        issues.append({
            "severity": severity, "icon": "🔴" if severity == "critical" else "⚠️",
            "title": f"Valores nulos encontrados ({sum(nulls.values())} total)",
            "detail": f"Columnas con nulos: {', '.join(f'{c}: {n}' for c, n in nulls.items())}",
            "nulls": nulls,
        })

    # 5. Duplicados
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        issues.append({
            "severity": "warning", "icon": "⚠️",
            "title": f"Filas duplicadas ({dup_count})",
            "detail": f"Se encontraron {dup_count} filas exactamente duplicadas.",
            "duplicates": dup_count,
        })

    # 6. Formato de fecha
    date_cols = [c for c in columns if c.lower() in ("date", "fecha")]
    date_diagnosis = {}
    for dc in date_cols:
        date_diagnosis[dc] = _try_date_formats(df[dc])

    for dc, dd in date_diagnosis.items():
        if dd["failed"] > 0:
            issues.append({
                "severity": "critical", "icon": "🔴",
                "title": f"Formato de fecha en '{dc}'",
                "detail": f"Mejor formato detectado: {dd['name']} — {dd['parsed']}/{dd['parsed'] + dd['failed']} fechas parseadas correctamente, {dd['failed']} fallaron.",
                "date_diagnosis": dd,
            })
        else:
            issues.append({
                "severity": "info", "icon": "✅",
                "title": f"Formato de fecha en '{dc}'",
                "detail": f"Formato detectado: {dd['name']} — {dd['parsed']} fechas válidas.",
                "date_diagnosis": dd,
            })

    # 7. Formato de montos
    amount_cols = [c for c in columns if c.lower() in ("amount", "debit", "credit", "monto")]
    for ac in amount_cols:
        amt_check = _check_amount_format(df[ac])
        if amt_check["format_type"] == "accounting (parentheses)":
            issues.append({
                "severity": "info", "icon": "✅",
                "title": f"Formato contable detectado en '{ac}'",
                "detail": "Los montos negativos usan paréntesis (formato contable). Se convertirán automáticamente.",
                "amount_check": amt_check,
            })
        elif amt_check["format_type"] == "mixed":
            issues.append({
                "severity": "warning", "icon": "⚠️",
                "title": f"Formato mixto en '{ac}'",
                "detail": "Algunos valores usan paréntesis y otros no. Se normalizarán.",
                "amount_check": amt_check,
            })

    # 8. Columnas clave potenciales
    key_cols = [c for c in columns if "_key" in c.lower() or c.lower().endswith("_code") or c.lower().endswith("_id")]
    if not key_cols and role["id"] == "unknown":
        issues.append({
            "severity": "warning", "icon": "⚠️",
            "title": "Sin columnas clave detectadas",
            "detail": "No se encontraron columnas con '_key', '_code' o '_id'. Las relaciones entre tablas podrían no detectarse.",
        })

    return {
        "filename": filename,
        "status": "ok",
        "role": role,
        "rows": len(df),
        "columns": columns,
        "column_count": len(columns),
        "dtypes": dtypes,
        "issues": issues,
        "has_null": len(nulls) > 0,
        "null_count": int(df.isna().sum().sum()),
        "has_duplicates": dup_count > 0,
        "duplicate_count": dup_count,
        "key_columns": key_cols,
    }


def diagnose_all(files: dict[str, str | pd.DataFrame]) -> dict:
    """Diagnóstico multi-CSV con detección de relaciones."""
    diagnoses = {}
    all_dfs = {}

    for name, source in files.items():
        diag = diagnose_csv(source, filename=name)
        diagnoses[name] = diag
        if diag["status"] == "ok" and isinstance(source, pd.DataFrame):
            all_dfs[name] = source

    # Detectar relaciones entre archivos
    relaciones = []
    seen_pairs = set()
    names = list(all_dfs.keys())
    for i, n1 in enumerate(names):
        for n2 in names[i + 1:]:
            cols1 = set(c.lower() for c in diagnoses[n1]["columns"])
            cols2 = set(c.lower() for c in diagnoses[n2]["columns"])
            comunes = cols1 & cols2
            for cc in comunes:
                if "unnamed" in cc:
                    continue
                relaciones.append({
                    "from": n1, "to": n2, "column": cc,
                })
                seen_pairs.add((n1, n2, cc))

    # Resumen consolidado
    total_critical = sum(1 for d in diagnoses.values() for i in d.get("issues", []) if i["severity"] == "critical")
    total_warnings = sum(1 for d in diagnoses.values() for i in d.get("issues", []) if i["severity"] == "warning")
    total_info = sum(1 for d in diagnoses.values() for i in d.get("issues", []) if i["severity"] == "info")

    return {
        "files": diagnoses,
        "relationships": relaciones,
        "summary": {
            "total_files": len(files),
            "total_issues": total_critical + total_warnings + total_info,
            "critical": total_critical,
            "warnings": total_warnings,
            "info": total_info,
        },
    }


# ── Dashboard ─────────────────────────────────

def _calc_kpi(subset, label, icon, amount_col="Amount", condition=None):
    """Calcula un KPI simple con monto actual y variación vs año anterior."""
    if condition is not None:
        sub = subset[condition]
    else:
        sub = subset
    valor = round(sub[amount_col].sum(), 2) if amount_col in sub.columns and len(sub) > 0 else 0
    return {"label": label, "value": f"${valor:,.2f}", "icon": icon, "raw": valor}


def get_dashboard_data(df, year=None, territorio=None) -> dict:
    mask = pd.Series(True, index=df.index)
    if year is not None and "Year" in df.columns:
        mask &= (df["Year"] == year)
    if territorio and "Country" in df.columns:
        mask &= (df["Country"] == territorio)
    subset = df.loc[mask]
    if len(subset) == 0:
        return {"kpis": [], "charts": [], "error": "No hay datos para los filtros indicados"}

    kpis = []
    kpis.append({"label": "Transacciones", "value": f"{len(subset):,}", "icon": "📋", "raw": len(subset)})
    if "SubClass" in subset.columns:
        ventas_cond = subset["SubClass"] == "Sales"
        gastos_cond = subset["SubClass"] == "Operating Expenses"
        ventas_raw = round(subset.loc[ventas_cond, "Amount"].sum(), 2) if "Amount" in subset.columns else 0
        gastos_raw = round(subset.loc[gastos_cond, "Amount"].sum(), 2) if "Amount" in subset.columns else 0
        neto_raw = round(ventas_raw + gastos_raw, 2) if "Amount" in subset.columns else 0
        kpis.append({"label": "Ventas", "value": f"${ventas_raw:,.2f}", "icon": "💰", "raw": ventas_raw})
        kpis.append({"label": "Gastos", "value": f"${gastos_raw:,.2f}", "icon": "💸", "raw": gastos_raw})
        kpis.append({"label": "Resultado", "value": f"${neto_raw:,.2f}", "icon": "✅" if neto_raw >= 0 else "❌",
                      "raw": neto_raw, "color": "green" if neto_raw >= 0 else "red"})
        top_pais_df = subset.groupby("Country", observed=True)["Amount_abs"].sum().reset_index() if "Country" in subset.columns and "Amount_abs" in subset.columns else None
        if top_pais_df is not None and len(top_pais_df) > 0:
            top_pais = top_pais_df.sort_values("Amount_abs", ascending=False).iloc[0]
            kpis.append({"label": "Top país", "value": f"{top_pais['Country']} (${top_pais['Amount_abs']:,.0f})", "icon": "🌍", "raw": top_pais["Amount_abs"]})
        top_cuenta_df = subset.groupby("SubAccount", observed=True)["Amount_abs"].sum().reset_index() if "SubAccount" in subset.columns and "Amount_abs" in subset.columns else None
        if top_cuenta_df is not None and len(top_cuenta_df) > 0:
            top_cuenta = top_cuenta_df.sort_values("Amount_abs", ascending=False).iloc[0]
            kpis.append({"label": "Top cuenta", "value": f"{top_cuenta['SubAccount']} (${top_cuenta['Amount_abs']:,.0f})", "icon": "🏦", "raw": top_cuenta["Amount_abs"]})

    # Year-over-year (si hay año filtrado)
    if year is not None and "Year" in df.columns:
        prev_year = year - 1
        prev_mask = (df["Year"] == prev_year)
        if territorio and "Country" in df.columns:
            prev_mask &= (df["Country"] == territorio)
        prev = df.loc[prev_mask]
        if len(prev) > 0:
            for kpi in kpis:
                if kpi["label"] in ("Ventas", "Gastos", "Resultado", "Transacciones"):
                    if kpi["label"] == "Ventas":
                        prev_val = round(prev.loc[prev["SubClass"] == "Sales", "Amount"].sum(), 2)
                    elif kpi["label"] == "Gastos":
                        prev_val = round(prev.loc[prev["SubClass"] == "Operating Expenses", "Amount"].sum(), 2)
                    elif kpi["label"] == "Resultado":
                        pv = round(prev.loc[prev["SubClass"] == "Sales", "Amount"].sum(), 2)
                        pg = round(prev.loc[prev["SubClass"] == "Operating Expenses", "Amount"].sum(), 2)
                        prev_val = pv + pg
                    else:
                        prev_val = len(prev)
                    diff = kpi["raw"] - prev_val
                    pct = (diff / prev_val * 100) if prev_val != 0 else 0
                    kpi["vs_prev"] = f"{'▲' if diff >= 0 else '▼'} {abs(pct):.1f}%"
                    kpi["vs_color"] = "green" if diff >= 0 else "red"

    # Charts data (estructura para Chart.js)
    charts = []
    if "SubClass" in subset.columns:
        data = subset.groupby("SubClass", observed=True)["Amount_abs"].sum().sort_values(ascending=False)
        charts.append({
            "type": "doughnut", "title": "Distribución por categoría",
            "labels": [str(c) for c in data.index], "values": [round(v, 2) for v in data.values],
        })
    if "Year" in subset.columns and "Amount" in subset.columns:
        data = subset.groupby("Year", observed=True)["Amount"].sum().sort_index()
        charts.append({
            "type": "bar", "title": "Monto por año",
            "labels": [str(y) for y in data.index], "values": [round(v, 2) for v in data.values],
        })
    if "Country" in subset.columns and "Amount_abs" in subset.columns:
        data = subset.groupby("Country", observed=True)["Amount_abs"].sum().sort_values(ascending=False)
        charts.append({
            "type": "bar", "title": "Volumen por país",
            "labels": [str(c) for c in data.index], "values": [round(v, 2) for v in data.values],
        })
    if "Date" in subset.columns and "Amount" in subset.columns:
        temp = subset.copy()
        temp["Date"] = pd.to_datetime(temp["Date"], errors="coerce")
        temp = temp.dropna(subset=["Date"])
        monthly = temp.set_index("Date").resample("ME")["Amount"].sum().reset_index()
        if len(monthly) > 1:
            charts.append({
                "type": "line", "title": "Tendencia mensual",
                "labels": [str(d.date()) for d in monthly["Date"]],
                "values": [round(v, 2) for v in monthly["Amount"]],
            })

    # Top accounts table
    top_accounts = []
    if "SubAccount" in subset.columns and "Amount_abs" in subset.columns:
        grouped = subset.groupby(["SubAccount", "SubClass", "Country"], observed=True)["Amount_abs"].sum().reset_index()
        grouped = grouped.sort_values("Amount_abs", ascending=False).head(10)
        top_accounts = grouped.to_dict("records")
        for r in top_accounts:
            r["Amount_abs"] = round(r["Amount_abs"], 2)

    return {"kpis": kpis, "charts": charts, "top_accounts": top_accounts}


# ── Fase 5: Anomalías ─────────────────────────────

def detectar_anomalias(df, threshold_std=2.0) -> dict:
    if "Amount" not in df.columns or len(df) == 0:
        return {"error": "No hay datos para analizar"}

    mean = df["Amount"].mean()
    std = df["Amount"].std()

    upper_std = mean + threshold_std * std
    lower_std = mean - threshold_std * std
    outliers_std = df[(df["Amount"] > upper_std) | (df["Amount"] < lower_std)].copy()

    Q1 = df["Amount"].quantile(0.25)
    Q3 = df["Amount"].quantile(0.75)
    IQR = Q3 - Q1
    lower_iqr = Q1 - 1.5 * IQR
    upper_iqr = Q3 + 1.5 * IQR
    outliers_iqr = df[(df["Amount"] < lower_iqr) | (df["Amount"] > upper_iqr)].copy()

    cols_show = [c for c in ["Date", "Account", "SubAccount", "Country", "Details", "Amount"] if c in df.columns]
    out_std_list = outliers_std[cols_show].head(20).to_dict("records") if len(outliers_std) > 0 else []
    out_iqr_list = outliers_iqr[cols_show].head(20).to_dict("records") if len(outliers_iqr) > 0 else []

    for rec in out_std_list:
        rec["Amount"] = round(rec["Amount"], 2)
    for rec in out_iqr_list:
        rec["Amount"] = round(rec["Amount"], 2)

    return {
        "total": len(df),
        "media": round(mean, 2),
        "desvio_std": round(std, 2),
        "rango_normal_std": {"min": round(lower_std, 2), "max": round(upper_std, 2)},
        "outliers_std": {"cantidad": len(outliers_std), "lista": out_std_list},
        "rango_normal_iqr": {"min": round(lower_iqr, 2), "max": round(upper_iqr, 2)},
        "outliers_iqr": {"cantidad": len(outliers_iqr), "lista": out_iqr_list},
    }


# ── Fase 5: Predicción ────────────────────────────

def predecir_tendencia(df, periods=3) -> dict:
    if "Date" not in df.columns or "Amount" not in df.columns or len(df) == 0:
        return {"error": "Datos insuficientes para predicción"}

    temp = df.copy()
    temp["Date"] = pd.to_datetime(temp["Date"], errors="coerce")
    temp = temp.dropna(subset=["Date"])
    monthly = temp.set_index("Date").resample("ME")["Amount"].sum().reset_index()
    monthly["Month_num"] = range(len(monthly))

    X = monthly["Month_num"].values.reshape(-1, 1)
    y = monthly["Amount"].values

    from sklearn.linear_model import LinearRegression
    model = LinearRegression()
    model.fit(X, y)

    last_idx = len(monthly)
    future_X = np.arange(last_idx, last_idx + periods).reshape(-1, 1)
    preds = model.predict(future_X)

    historical = [{"label": str(d.date()), "value": round(v, 2)} for d, v in zip(monthly["Date"], y)]
    future = [{"label": f"Periodo {i+1}", "value": round(float(p), 2)} for i, p in enumerate(preds)]

    tendencia = "creciente" if model.coef_[0] > 0 else "decreciente"

    return {
        "historical": historical,
        "prediction": future,
        "tendencia": tendencia,
        "coeficiente": round(float(model.coef_[0]), 4),
        "periodos": periods,
    }
