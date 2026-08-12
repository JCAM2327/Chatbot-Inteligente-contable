import io, json, re, tempfile, logging, threading, os
import pandas as pd
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from pathlib import Path

from app.data_processing import (
    load_data, load_csv, clean_gl, merge_tables,
    get_total_ventas, get_total_gastos, get_resultado_neto,
    get_pais_mayor_movimiento, get_cuenta_mayor_monto,
    get_pais_menor_movimiento, get_cuenta_menor_monto,
    get_resumen, get_resumen_general, get_cuentas_mas_usadas,
    get_info_etl, detectar_relaciones,
    diagnose_all, get_total_por_mes, get_por_territorio,
    get_dashboard_data, detectar_anomalias, predecir_tendencia,
)
from app.graficos import generar_grafico
from app.intent import detectar_intencion, extract_year, extract_month, extract_territorio
from app.constants import NOMBRE_MES, MESES_EN

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """Estado mutable de la aplicación, thread-safe para escritura."""
    df: pd.DataFrame | None = None
    etl_stats: dict = field(default_factory=dict)
    merges: list = field(default_factory=list)
    modelo: dict = field(default_factory=lambda: {"relaciones": [], "tablas": []})
    data_source: str = "none"
    raw_files: dict = field(default_factory=dict)
    diagnosis: dict = field(default_factory=dict)
    dashboard_cache: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                object.__setattr__(self, k, v)

    def __getitem__(self, key: str):
        return getattr(self, key)

    def __setitem__(self, key: str, value):
        self.update(**{key: value})

    def get(self, key: str, default=None):
        return getattr(self, key, default)


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-carga datos de ejemplo al iniciar."""
    load_dotenv()
    print("Cargando datos de ejemplo...")
    try:
        df, etl_stats, merges = load_data()
        raw_dfs = {
            "GL": load_csv("GL.csv"),
            "chart_of_accounts": load_csv("chart_of_accounts.csv"),
            "territory": load_csv("territory.csv"),
            "calendar": load_csv("calendar.csv"),
        }
        modelo = detectar_relaciones(raw_dfs)
        state.update(df=df, etl_stats=etl_stats, merges=merges, modelo=modelo, data_source="sample")
        print(f"Datos de ejemplo cargados: {len(df)} registros")
    except Exception as e:
        logger.warning(f"No se pudieron cargar datos de ejemplo: {e}")
        state.update(df=None, data_source="none")
    yield
    print("Servidor apagado")


app = FastAPI(
    title="Chatbot de Libro Mayor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Modelos Pydantic ────────────────────────────────────

class QueryRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La pregunta no puede estar vacía")
        if len(v) > 500:
            raise ValueError("La pregunta excede los 500 caracteres")
        return v.strip()

class ChatResponse(BaseModel):
    answer: str
    labels: list = []
    values: list = []
    dashboard: dict | None = None
    chart_base64: str | None = None
    chart_type: str | None = None

class DashboardResponse(BaseModel):
    kpis: list = []
    charts: list = []
    top_accounts: list = []
    error: str | None = None

# ── Endpoints ───────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "data_source": state.get("data_source", "none")}

@app.get("/resumen")
def resumen():
    if state.get("df") is None:
        return {"total_registros": 0, "mensaje": "No hay datos cargados"}
    return get_resumen(state.df)

@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(year: int | None = None, territory: str | None = None):
    if state.get("df") is None:
        return DashboardResponse(error="No hay datos cargados")
    cache_key = f"{year}:{territory}"
    cached = state.get("dashboard_cache", {}).get(cache_key)
    if cached:
        return DashboardResponse(**cached)
    dash = get_dashboard_data(state.df, year, territory)
    state.dashboard_cache[cache_key] = dash
    return DashboardResponse(**dash)

@app.get("/modelo")
def get_modelo():
    return state.get("modelo", {"relaciones": [], "tablas": []})

@app.post("/upload")
def upload_files(files: list[UploadFile] = File(...)):
    """Recibe múltiples CSVs, los analiza y devuelve diagnóstico."""
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    print(f"[UPLOAD] Recibidos {len(files)} archivos")
    parsed: dict[str, pd.DataFrame] = {}
    errors = []

    for f in files:
        try:
            fname = f.filename or "unknown.csv"
            print(f"[UPLOAD] Leyendo archivo: {fname}")
            content = f.file.read()
            print(f"[UPLOAD] Leidos {len(content)} bytes")
            if fname.lower().endswith(".xlsx"):
                df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
            else:
                df = pd.read_csv(io.BytesIO(content))
            print(f"[UPLOAD] Parseado: {df.shape}")
            parsed[fname] = df
        except Exception as e:
            print(f"[UPLOAD] Error: {e}")
            errors.append({"file": f.filename, "error": str(e)})

    print(f"[UPLOAD] Diagnóstico de {len(parsed)} archivos...")
    diagnosis = diagnose_all(parsed)
    print(f"[UPLOAD] Diagnóstico completado")

    state.update(raw_files=parsed, diagnosis=diagnosis)

    return {"diagnosis": diagnosis, "errors": errors}

@app.post("/reset")
def reset_to_sample():
    """Vuelve a cargar los datos de ejemplo."""
    try:
        df, etl_stats, merges = load_data()
        raw_dfs = {
            "GL": load_csv("GL.csv"),
            "chart_of_accounts": load_csv("chart_of_accounts.csv"),
            "territory": load_csv("territory.csv"),
            "calendar": load_csv("calendar.csv"),
        }
        modelo = detectar_relaciones(raw_dfs)
        state.update(df=df, etl_stats=etl_stats, merges=merges, modelo=modelo, data_source="sample", raw_files={}, diagnosis={}, dashboard_cache={})
        return {"status": "ok", "rows": len(df)}
    except Exception as e:
        logger.error(f"Error al resetear: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="No se pudieron recargar los datos de ejemplo.")


@app.get("/suggestions")
def get_suggestions():
    """Devuelve sugerencias de preguntas dinámicas basadas en los datos cargados."""
    df = state.get("df")
    if df is None:
        suggestions = [
            {"icon": "💰", "text": "¿Cuánto se vendió en 2019?"},
            {"icon": "💸", "text": "¿Cuál fue el total de gastos?"},
        ]
        return {"suggestions": suggestions}

    suggestions = [
        {"category": "ventas", "icon": "💰", "text": "¿Cuánto se vendió en total?"},
        {"category": "gastos", "icon": "💸", "text": "¿Cuál fue el total de gastos?"},
        {"category": "neto", "icon": "📈", "text": "¿Hubo ganancia o pérdida?"},
    ]

    ano_ref = 2019
    if "Year" in df.columns:
        anos = sorted(df["Year"].dropna().unique().tolist(), reverse=True)
        ano_ref = anos[0]
        suggestions.append({"category": "ventas", "icon": "📅", "text": f"¿Cuánto se vendió en {ano_ref}?"})
        suggestions.append({"category": "gastos", "icon": "💸", "text": f"¿Cuánto se gastó en {ano_ref}?"})
        if len(anos) >= 2:
            suggestions.append({"category": "comparativa", "icon": "⚖️", "text": f"Comparar ventas {anos[0]} vs {anos[1]}"})
        suggestions.append({"category": "neto", "icon": "📈", "text": f"Resultado neto de {ano_ref}"})

    if "Country" in df.columns:
        suggestions.append({"category": "pais", "icon": "🌍", "text": "¿Qué país tuvo mayor movimiento?"})
        suggestions.append({"category": "pais_menor", "icon": "🌍", "text": "¿Qué país tuvo menor movimiento?"})

    if "SubAccount" in df.columns:
        suggestions.append({"category": "cuenta", "icon": "🏦", "text": "¿Qué cuenta movió más dinero?"})
        suggestions.append({"category": "cuentas_mas_usadas", "icon": "🧾", "text": "¿Cuáles son las cuentas más usadas?"})

    if "Month" in df.columns and "Year" in df.columns:
        meses_raw = df["Month"].dropna().unique().tolist()
        for mes in meses_raw:
            mes_int = MESES_EN.get(str(mes).strip().lower()[:3])
            if mes_int is None:
                try:
                    mes_int = int(mes)
                except (ValueError, TypeError):
                    continue
            mes_nombre = NOMBRE_MES.get(mes_int)
            if mes_nombre:
                suggestions.append({"category": "mensual", "icon": "📅", "text": f"Movimientos de {mes_nombre.lower()} {ano_ref}"})
                break

    if "Region" in df.columns:
        suggestions.append({"category": "territorio", "icon": "🗺️", "text": "Gastos del territorio norte"})

    suggestions.append({"category": "resumen", "icon": "📊", "text": "Generá un resumen general"})
    suggestions.append({"category": "dashboard", "icon": "📊", "text": "Mostrame el dashboard"})
    suggestions.append({"category": "modelo", "icon": "🔗", "text": "¿Cómo se conectan las tablas?"})
    suggestions.append({"category": "etl", "icon": "🛠️", "text": "¿Qué limpieza se hizo?"})
    suggestions.append({"category": "grafico", "icon": "📊", "text": "Graficame ventas por año"})
    suggestions.append({"category": "anomalia", "icon": "⚠️", "text": "Detectá anomalías en los datos"})
    suggestions.append({"category": "prediccion", "icon": "🔮", "text": "Predecí la tendencia futura"})

    return {"suggestions": suggestions}


@app.post("/apply")
def apply_etl():
    """Aplica las correcciones ETL a los archivos subidos y carga los datos."""
    raw = state.get("raw_files")
    if not raw:
        raise HTTPException(status_code=400, detail="No hay archivos subidos. Usá /upload primero.")

    try:
        # Buscar el archivo que sea GL (por rol detectado o por nombre)
        diagnosis = state.get("diagnosis", {})
        files_diag = diagnosis.get("files", {})

        gl_file = None
        coa_file = None
        terr_file = None
        cal_file = None

        for fname, diag in files_diag.items():
            role = diag.get("role", {}).get("id", "")
            if role == "GL":
                gl_file = fname
            elif role == "chart_of_accounts":
                coa_file = fname
            elif role == "territory":
                terr_file = fname
            elif role == "calendar":
                cal_file = fname

        # Si no se detectó por columnas, intentar por nombre
        if not gl_file:
            for fname in raw:
                if "gl" in fname.lower() or "general" in fname.lower():
                    gl_file = fname
                    break
        if not gl_file:
            gl_file = list(raw.keys())[0]  # primer archivo como GL

        gl_raw = raw[gl_file]
        gl_clean, etl_stats = clean_gl(gl_raw)

        # Si hay COA, territory, calendar, mergearlos
        df = gl_clean
        merges = []
        dfs = {"GL": gl_clean}

        if coa_file:
            coa_df = raw[coa_file]
            dfs["chart_of_accounts"] = coa_df
            df, merges = merge_tables(
                gl_clean, coa_df,
                raw.get(terr_file, pd.DataFrame()),
                raw.get(cal_file, pd.DataFrame()),
            )
            etl_stats["merges"] = merges

        state.update(df=df, etl_stats=etl_stats, merges=merges, data_source="upload", raw_files={}, dashboard_cache={})

        return {
            "status": "ok",
            "rows": len(df),
            "columns": list(df.columns),
            "etl_summary": {
                "original_rows": etl_stats.get("filas_originales", 0),
                "final_rows": etl_stats.get("filas_finales", 0),
                "duplicates_removed": etl_stats.get("duplicados_eliminados", 0),
                "nulls_removed": etl_stats.get("nulos_eliminados", 0),
            },
        }
    except Exception as e:
        logger.error(f"Error en /apply: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al aplicar ETL.")

def _safe_query(df, fn, *args, **kwargs) -> dict:
    """Envuelve queries para capturar KeyError por columnas faltantes."""
    try:
        return fn(df, *args, **kwargs)
    except KeyError as e:
        col = str(e).strip("'\"")
        logger.warning(f"Columna faltante '{col}' en consulta")
        return {
            "answer": f"⚠️ Los datos cargados no tienen la columna '{col}'. Asegurate de aplicar ETL con el Plan de Cuentas (chart_of_accounts) para habilitar esta consulta.",
            "labels": [],
            "values": [],
        }


@app.post("/chat", response_model=ChatResponse)
def chat(request: QueryRequest):
    try:
        question = request.question
        intent = detectar_intencion(question)
        year = extract_year(question)
        df = state.get("df")

        if df is None:
            return ChatResponse(
                answer="No hay datos cargados. Subí archivos CSV desde la página principal para comenzar.",
                labels=[], values=[],
            )

        extra = {}

        if intent == "ventas":
            result = _safe_query(df, get_total_ventas, year)
        elif intent == "gastos":
            result = _safe_query(df, get_total_gastos, year)
        elif intent == "neto":
            result = _safe_query(df, get_resultado_neto, year)
        elif intent == "pais":
            result = _safe_query(df, get_pais_mayor_movimiento)
        elif intent == "cuenta":
            result = _safe_query(df, get_cuenta_mayor_monto)
        elif intent == "pais_menor":
            result = _safe_query(df, get_pais_menor_movimiento)
        elif intent == "cuenta_menor":
            result = _safe_query(df, get_cuenta_menor_monto)
        elif intent == "etl":
            result = get_info_etl(df, state.get("etl_stats", {}))
        elif intent == "modelo":
            rels = state.get("modelo", {}).get("relaciones", [])
            texto = "Relaciones detectadas entre tablas:\n\n"
            for r in rels:
                texto += f"  {r['from']} ──🔗── {r['to']} (por {r['column']}, tipo: {r['type']})\n"
            texto += f"\nTablas: {', '.join(state.get('modelo', {}).get('tablas', []))}"
            texto += "\n\nMirá el diagrama en la sección 'Modelo de Datos' debajo del área de carga."
            result = {"answer": texto, "labels": [], "values": []}
        elif intent == "mensual":
            month_num, month_name = extract_month(question)
            if month_num:
                if "gasto" in question.lower():
                    result = _safe_query(df, get_total_por_mes, month_num, year, "Operating Expenses")
                elif "venta" in question.lower() or "ingreso" in question.lower():
                    result = _safe_query(df, get_total_por_mes, month_num, year, "Sales")
                else:
                    result = _safe_query(df, get_total_por_mes, month_num, year)
            else:
                result = {"answer": "No entendí qué mes consultar", "labels": [], "values": []}
        elif intent == "territorio":
            territorio = extract_territorio(question)
            if territorio:
                result = _safe_query(df, get_por_territorio, territorio, year)
            else:
                result = {"answer": "No entendí qué territorio consultar", "labels": [], "values": []}
        elif intent == "resumen":
            result = _safe_query(df, get_resumen_general)
        elif intent == "cuentas_mas_usadas":
            result = _safe_query(df, get_cuentas_mas_usadas)
        elif intent == "dashboard":
            dash = get_dashboard_data(df, year)
            kpis_text = "\n".join(f"  {k['icon']} **{k['label']}:** {k['value']}" for k in dash.get("kpis", []))
            answer = f"**📊 Dashboard**\n\n{kpis_text}" if kpis_text else "No hay datos para mostrar"
            result = {"answer": answer, "labels": [], "values": []}
            extra["dashboard"] = dash
        elif intent == "grafico":
            tipo = "bar"
            if "torta" in question or "pie" in question:
                tipo = "pie"
            elif "linea" in question or "tendencia" in question:
                tipo = "line"
            gr = generar_grafico(tipo, df, titulo=f"Ventas por año" if tipo == "bar" else f"Distribución por categoría")
            if gr.get("chart_base64"):
                result = {"answer": "📊 Acá está el gráfico:", "labels": [], "values": []}
                extra["chart_base64"] = gr["chart_base64"]
                extra["chart_type"] = tipo
            else:
                result = {"answer": f"No se pudo generar el gráfico: {gr.get('error', 'error desconocido')}", "labels": [], "values": []}
        elif intent == "anomalia":
            anom = detectar_anomalias(df)
            if "error" in anom:
                result = {"answer": anom["error"], "labels": [], "values": []}
            else:
                texto = f"**🔍 Detección de anomalías**\n\n"
                texto += f"Total transacciones: {anom['total']:,}\n"
                texto += f"Media: ${anom['media']:,.2f} | Desvío std: ${anom['desvio_std']:,.2f}\n\n"
                texto += f"**Método Desvío Estándar (±2σ):** {anom['outliers_std']['cantidad']} outliers\n"
                texto += f"Rango normal: ${anom['rango_normal_std']['min']:,.2f} a ${anom['rango_normal_std']['max']:,.2f}\n"
                if anom['outliers_std']['lista']:
                    texto += "\n**Detalle:**\n"
                    for o in anom['outliers_std']['lista'][:5]:
                        fecha = o.get('Date', '')
                        cuenta = o.get('SubAccount', o.get('Account', ''))
                        pais = o.get('Country', '')
                        texto += f"  • {fecha} | {cuenta} | {pais} | ${o['Amount']:,.2f}\n"
                texto += f"\n**Método IQR:** {anom['outliers_iqr']['cantidad']} outliers"
                result = {"answer": texto, "labels": [], "values": []}
        elif intent == "prediccion":
            pred = predecir_tendencia(df)
            if "error" in pred:
                result = {"answer": pred["error"], "labels": [], "values": []}
            else:
                texto = f"**🔮 Predicción de tendencia**\n\n"
                texto += f"Tendencia: **{pred['tendencia'].upper()}**\n"
                texto += f"Coeficiente: {pred['coeficiente']:,.4f}\n\n"
                texto += "**Últimos períodos reales:**\n"
                for h in pred['historical'][-6:]:
                    texto += f"  • {h['label']}: ${h['value']:,.2f}\n"
                texto += f"\n**Predicción ({pred['periodos']} períodos):**\n"
                for f in pred['prediction']:
                    texto += f"  • {f['label']}: ${f['value']:,.2f}\n"
                # Generar gráfico de línea con predicción
                all_labels = [h['label'] for h in pred['historical']] + [p['label'] for p in pred['prediction']]
                all_values = [h['value'] for h in pred['historical']] + [p['value'] for p in pred['prediction']]
                result = {"answer": texto, "labels": all_labels, "values": all_values}
        elif intent == "comparativa":
            anos_encontrados = sorted(set(re.findall(r"\b20\d{2}\b", question)))
            if len(anos_encontrados) >= 2:
                partes = []
                for a in anos_encontrados[:2]:
                    v = _safe_query(df, get_total_ventas, int(a))
                    g = _safe_query(df, get_total_gastos, int(a))
                    partes.append(f"**{a}:** Ventas {v['answer'].split('$')[1] if '$' in v.get('answer','') else 'N/A'}, Gastos {g['answer'].split('$')[1] if '$' in g.get('answer','') else 'N/A'}")
                texto = "**⚖️ Comparativa**\n\n" + "\n\n".join(partes)
                result = {"answer": texto, "labels": [], "values": []}
            else:
                result = {"answer": "Decime qué dos años querés comparar (ej: 'comparar 2019 vs 2020')", "labels": [], "values": []}
        else:
            contexto = (
                f"Dataset contable con {len(df)} registros, "
                f"período {str(df['Date'].min().date()) if 'Date' in df.columns else 'N/A'} "
                f"a {str(df['Date'].max().date()) if 'Date' in df.columns else 'N/A'}, "
                f"{df['Country'].nunique() if 'Country' in df.columns else '?'} países, "
                f"{df['SubAccount'].nunique() if 'SubAccount' in df.columns else '?'} cuentas."
            )
            from app.ai_formatter import redactar_respuesta
            texto_ia, ia_used = redactar_respuesta(contexto, question, modo="free")
            if ia_used:
                result = {"answer": texto_ia + '\n\n<sup style="color:var(--accent)">✨ IA</sup>', "labels": [], "values": []}
            else:
                result = {"answer": (
                    "No entendí tu consulta. Podés preguntarme sobre:\n"
                    "  • Total de ventas (ej: '¿Cuánto se vendió en 2019?')\n"
                    "  • Total de gastos\n"
                    "  • Resultado neto (ganancia o pérdida)\n"
                    "  • País con mayor/menor movimiento\n"
                    "  • Cuenta con mayor/menor monto\n"
                    "  • Cuentas más utilizadas\n"
                    "  • Resumen general\n"
                    "  • Dashboard (ej: 'Mostrame el dashboard')\n"
                    "  • Gráficos (ej: 'Graficame ventas por año')\n"
                    "  • Anomalías (ej: 'Detectá anomalías')\n"
                    "  • Predicción (ej: 'Predecí la tendencia')\n"
                    "  • Movimientos por mes (ej: '¿cuánto se gastó en enero?')\n"
                    "  • Movimientos por territorio (ej: 'gastos del territorio norte')\n"
                    "  • Proceso de limpieza (ej: '¿Qué limpieza se hizo?')\n"
                    "  • Relaciones entre tablas (ej: '¿Cómo se conectan las tablas?')"
                ), "labels": [], "values": []}

        from app.ai_formatter import redactar_respuesta
        respuesta_ia, ia_used = redactar_respuesta(result["answer"], question)
        if ia_used:
            result["answer"] = respuesta_ia + '\n\n<sup style="color:var(--accent)">✨ IA</sup>'
        else:
            result["answer"] = respuesta_ia

        return ChatResponse(
            answer=result["answer"],
            labels=result.get("labels", []),
            values=result.get("values", []),
            dashboard=extra.get("dashboard"),
            chart_base64=extra.get("chart_base64"),
            chart_type=extra.get("chart_type"),
        )
    except Exception as e:
        logger.error(f"Error en /chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ocurrió un error al procesar la consulta.")

# ── Archivos estáticos ──────────────────────────────────

static_dir = Path(__file__).parent.parent / "static"
if not static_dir.exists():
    raise RuntimeError(f"El directorio estático no existe: {static_dir}")

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def root():
    return FileResponse(str(static_dir / "index.html"))
