import io, base64, logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

sns.set_style("whitegrid")
COLORS = ["#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6",
          "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b"]


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.getvalue()).decode()
    plt.close(fig)
    return b64


def generar_grafico(tipo: str, df: pd.DataFrame, **kwargs) -> dict:
    titulo = kwargs.get("titulo", "")
    filtro_col = kwargs.get("filtro_col")
    filtro_val = kwargs.get("filtro_val")

    if filtro_col and filtro_val and filtro_col in df.columns:
        df = df[df[filtro_col] == filtro_val]

    if len(df) == 0:
        return {"error": "No hay datos para graficar", "chart_base64": None}

    fig, ax = plt.subplots(figsize=(10, 5))

    if tipo == "bar":
        col_x = kwargs.get("x", "Year")
        col_y = kwargs.get("y", "Amount")
        group = kwargs.get("group", col_x)

        if group in df.columns:
            data = df.groupby(group, observed=True)[col_y].sum().sort_index()
        else:
            return {"error": f"Columna '{group}' no encontrada", "chart_base64": None}

        colors = COLORS[:len(data)]
        bars = ax.bar(data.index.astype(str), data.values, color=colors, edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, data.values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + abs(bar.get_height())*0.02,
                    f"${val:,.0f}", ha="center", va="bottom", fontsize=8, rotation=45)
        ax.set_title(titulo or f"Total por {group}", fontsize=13, fontweight="bold")
        ax.set_xlabel(group)
        ax.set_ylabel("Monto ($)")
        plt.xticks(rotation=45)

    elif tipo == "pie":
        col_group = kwargs.get("group", "SubClass")
        col_val = kwargs.get("y", "Amount_abs")

        if col_group in df.columns:
            data = df.groupby(col_group, observed=True)[col_val].sum().sort_values(ascending=False)
        else:
            return {"error": f"Columna '{col_group}' no encontrada", "chart_base64": None}

        labels = [str(c) for c in data.index]
        colors = COLORS[:len(labels)]
        wedges, texts, autotexts = ax.pie(
            data.values, labels=None, autopct="%1.1f%%",
            colors=colors, startangle=90, pctdistance=0.75,
        )
        ax.legend(wedges, labels, title=col_group, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=8)
        ax.set_title(titulo or f"Distribución por {col_group}", fontsize=13, fontweight="bold")

    elif tipo == "line":
        date_col = kwargs.get("date_col", "Date")
        val_col = kwargs.get("y", "Amount")
        freq = kwargs.get("freq", "ME")

        if date_col in df.columns:
            temp = df.copy()
            temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
            temp = temp.dropna(subset=[date_col])
            data = temp.set_index(date_col).resample(freq)[val_col].sum()
        else:
            return {"error": f"Columna de fecha '{date_col}' no encontrada", "chart_base64": None}

        ax.plot(data.index, data.values, marker="o", color="#3498db", linewidth=2, markersize=4)
        ax.fill_between(data.index, data.values, alpha=0.15, color="#3498db")
        ax.set_title(titulo or "Tendencia mensual", fontsize=13, fontweight="bold")
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Monto ($)")
        plt.xticks(rotation=45)

    elif tipo == "barh":
        col_group = kwargs.get("group", "SubAccount")
        col_val = kwargs.get("y", "Amount_abs")
        top_n = kwargs.get("top_n", 10)

        if col_group in df.columns:
            data = df.groupby(col_group, observed=True)[col_val].sum().sort_values(ascending=True).tail(top_n)
        else:
            return {"error": f"Columna '{col_group}' no encontrada", "chart_base64": None}

        colors = COLORS[:len(data)]
        ax.barh(data.index.astype(str), data.values, color=colors, edgecolor="white")
        for i, val in enumerate(data.values):
            ax.text(val + val*0.01, i, f"${val:,.0f}", va="center", fontsize=8)
        ax.set_title(titulo or f"Top {top_n} {col_group}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Monto ($)")

    else:
        plt.close(fig)
        return {"error": f"Tipo de gráfico '{tipo}' no soportado", "chart_base64": None}

    plt.tight_layout()
    b64 = _fig_to_base64(fig)
    return {"chart_base64": b64, "chart_type": tipo}
