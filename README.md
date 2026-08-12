<p align="center">
  <h1 align="center">📊 Chatbot de Libro Mayor (General Ledger)</h1>
</p>

<p align="center">
  <b>Chatbot web en lenguaje natural sobre contabilidad · FastAPI + Pandas</b>
  Podes probarlo directamente en https://chatbot-inteligente-contable.onrender.com
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-0.104%2B-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/pandas-2.1%2B-orange" alt="Pandas">
  <img src="https://img.shields.io/badge/tests-77%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="MIT License">
</p>

Chatbot web que responde preguntas en lenguaje natural sobre un libro mayor
contable (dataset [General Ledger de Kaggle](https://www.kaggle.com/datasets/irfansharif/generalledger)).
Los cálculos se hacen siempre con **Python/Pandas**; el chatbot interpreta la
pregunta y redacta la respuesta de forma natural.

---

## ✨ Características

### 🧹 Carga y diagnóstico de datos
- Subida múltiple de CSVs/Excel (.xlsx) via drag-and-drop
- Diagnóstico ETL detallado por archivo (columnas, tipos, nulos, duplicados, formato de fecha, montos, claves foráneas)
- Detección automática del rol de cada archivo (GL, plan de cuentas, territorios, calendario)
- Recarga de datos de ejemplo con un clic

### 🔗 Modelo de datos interactivo
- Tarjetas HTML con esquema de tablas (2×2 grid)
- 🔑 Claves primarias y foráneas destacadas
- Lista de relaciones con flechas ⟷ entre tablas
- Columnas detalladas por tabla

### 💬 Chatbot (15 intenciones)
| Intención | Ejemplo |
|---|---|
| Ventas | "¿Cuánto se vendió en 2019?" |
| Gastos | "¿Cuál fue el total de gastos?" |
| Resultado neto | "¿Hubo ganancia o pérdida?" |
| País | "¿Qué país tuvo más actividad?" |
| Cuenta | "¿Qué cuenta movió más dinero?" |
| Por mes | "¿Cuánto se gastó en enero?" |
| Por territorio | "Gastos del territorio norte" |
| Resumen general | "Generá un resumen general" |
| Cuentas más usadas | "¿Qué cuentas tienen más transacciones?" |
| Dashboard | "Mostrame el dashboard" |
| Gráficos | "Graficame ventas por año" |
| Anomalías | "Detectá anomalías en los datos" |
| Predicción | "Predecí la tendencia futura" |
| ETL | "¿Qué limpieza se hizo?" |
| Relaciones | "¿Cómo se conectan las tablas?" |
| Comparativa | "Compará ventas entre países" |

### 📊 Dashboard estilo Power BI
- KPIs interactivos con variación vs año anterior
- Gráficos Chart.js (barras, línea, dona)
- Filtros por año y territorio
- Tabla de Top 10 cuentas
- Chat sidebar integrado

### 🔍 Detección de intención
- **rapidfuzz** con token_sort_ratio (umbral 65%)
- Normalización Unicode NFKD (sin acentos/ñ)
- Keywords con word boundaries
- Orden por longitud descendente (prioriza "menor movimiento" sobre "país")

### ⚙️ ETL pipeline
- Parseo de formato contable `(884)` → `-884.0`
- Parseo de fechas con detección automática de formato
- Eliminación de columnas vacías (Unnamed)
- Conversión de tipos (Int64 nullable para claves)
- Eliminación de duplicados con tracking
- Manejo de nulos en columnas críticas
- **3 merges**: GL ⨝ chart_of_accounts, GL ⨝ territory, GL ⨝ calendar
- Columna calculada `Amount_abs = Amount.abs()`
- Trazabilidad completa del proceso ETL
- Manejo de signos contables (gastos negativos → display positivo)

### 📈 Anomalías y predicción
- Detección de outliers por desvío estándar (±2σ) y método IQR
- Predicción de tendencia con regresión lineal (scikit-learn)
- Generación de gráficos con matplotlib/seaborn

### 🎨 Frontend
- Tema dark/light con persistencia en localStorage
- Sistema de notificaciones toast
- Preguntas sugeridas dinámicas
- Diagrama de relaciones en vista Modelo (tarjetas HTML)
- Chart.js para visualizaciones
- Diseño responsive

---

## 🗂️ Estructura del proyecto

```
proyecto/
├── PROMPTS.md              
├── README.md
├── requirements.txt
├── data/
│   ├── GL.csv              # 27.909 movimientos contables
│   ├── chart_of_accounts.csv
│   ├── territory.csv
│   └── calendar.csv
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI, endpoints, AppState
│   ├── data_processing.py  # ETL, consultas, diagnóstico, dashboard
│   ├── intent.py           # Detección de intención + extracción
│   ├── constants.py        # Constantes compartidas
│   ├── graficos.py         # Generación de gráficos (matplotlib)
│   └── ai_formatter.py     # Bonus: IA para redactar respuestas
├── static/
│   ├── index.html          # Frontend completo (landing + dashboard + modelo)
│   ├── style.css           # Estilos (dark/light, grid, responsive)
│   └── script.js           # Lógica frontend (dashboard, chat, modelo)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_data_processing.py
│   └── test_intent.py
```

---

## 🚀 Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/chatbot-gl.git
cd chatbot-gl

# Crear entorno virtual
python -m venv venv

# Activar (Windows)
venv\Scripts\activate
# Activar (Mac / Linux)
# source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## ▶️ Ejecución

```bash
uvicorn app.main:app --reload
```

Abrir [http://127.0.0.1:8000](http://127.0.0.1:8000) en el navegador.

---

## 🧪 Tests

```bash
pytest tests/ -v
```

77 tests que cubren: parseo de montos, limpieza ETL, merges, funciones de consulta, detección de intención, extracción de año, endpoints de la API, despliegue de signos correctos y respuestas formateadas.

---

## 🔌 Endpoints de la API

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/` | Sirve el frontend |
| GET | `/health` | Estado del servidor |
| GET | `/resumen` | Resumen estadístico |
| GET | `/modelo` | Relaciones entre tablas (tarjetas HTML) |
| GET | `/dashboard` | Datos del dashboard (KPIs, charts) |
| GET | `/suggestions` | Preguntas sugeridas dinámicas |
| POST | `/chat` | Consulta en lenguaje natural |
| POST | `/upload` | Subir CSVs/Excel para diagnóstico |
| POST | `/apply` | Aplicar ETL a archivos subidos |
| POST | `/reset` | Recargar datos de ejemplo |

---

## 📊 Dataset

Fuente: Excel original de Kaggle exportado a 4 CSV.

| Archivo | Filas | Columnas |
|---|---|---|
| `GL.csv` | 27.909 | `EntryNo, Date, Territory_key, Account_key, Details, Amount` |
| `chart_of_accounts.csv` | 62 | `Account_key, Report, Class, SubClass, SubClass2, Account, SubAccount` |
| `territory.csv` | 7 | `Territory_key, Country, Region` |
| `calendar.csv` | 1.096 | `Date, Year, Quarter, Month, Day` |

> **Nota:** Los costos y gastos vienen con `Amount` negativo (contabilidad real, no un error). El sistema maneja automáticamente la conversión a display positivo.

---

## 🤖 Configuración de IA (bonus opcional)

El proyecto incluye un formateador opcional de respuestas usando IA (Gemini, Groq o OpenRouter).
No requiere configuración para funcionar: con `USE_AI_FORMATTER=false` (default) el chatbot responde
con texto generado por reglas.

Si se desea activar, crear `.env`:

```env
AI_API_KEY=AIzaSy...
USE_AI_FORMATTER=true
```

> **Nota:** la IA solo redacta respuestas en lenguaje natural. TODOS los cálculos son realizados por Python/Pandas. Sin API key funcional el chatbot opera completo sin IA.

---

## 🛠️ Tecnologías

| Backend | Frontend | Data | Tests |
|---|---|---|---|
| Python 3.11+ | HTML5 | Pandas | pytest |
| FastAPI | CSS3 (Custom Properties) | scikit-learn | httpx |
| Uvicorn | JavaScript vanilla | matplotlib | |
| | Chart.js | seaborn | |
| | | rapidfuzz | |
| | | openpyxl | |

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crear una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Hacer cambios y correr tests (`pytest tests/ -v`)
4. Commit (`git commit -m "Agrega nueva funcionalidad"`)
5. Push (`git push origin feature/nueva-funcionalidad`)
6. Abrir un Pull Request

---

## 📄 Licencia

Distribuido bajo licencia MIT. Ver `LICENSE` para más información.

---

## 👤 Créditos

- **Dataset:** [General Ledger — Kaggle, irfansharif](https://www.kaggle.com/datasets/irfansharif/generalledger)
- **Desarrollado con:** FastAPI + Pandas + Chart.js + OpenCode
- **Documentación de prompts:** [PROMPTS.md](./PROMPTS.md)
- **Presentación:** [Presentacion_Trabajo_Practico_Integrador.pptx](./Presentacion_Trabajo_Practico_Integrador.pptx)
